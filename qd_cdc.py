#!/usr/bin/env python3
"""Conservative structural CDC triage for Yosys JSON."""
import argparse
import json
import sys
from collections import defaultdict


FFS = {"$_DFF_P_", "$_DFF_N_"}
RESET_FFS = {f"$_DFF_{clock}{reset}{value}_": (clock, reset, int(value))
             for clock in "PN" for reset in "PN" for value in "01"}
COMB = {"$_BUF_": "A", "$_NOT_": "A", "$_AND_": "AB", "$_OR_": "AB",
        "$_XOR_": "AB", "$_XNOR_": "AB", "$_NAND_": "AB", "$_NOR_": "AB",
        "$_MUX_": "ABS", "$_AOI3_": "ABC", "$_OAI3_": "ABC",
        "$_AOI4_": "ABCD", "$_OAI4_": "ABCD"}


def bitkey(bit):
    # Yosys JSON distinguishes integer net IDs from string-valued constants.
    return f"'{bit}'" if isinstance(bit, str) else str(bit)


def marked(value):
    value = str(value).lower()
    if value in {"true", "yes"}: return True
    try: return int(value, 2) != 0
    except ValueError: return False


def input_domain_sources(ports, domains):
    """Resolve explicit port assumptions to net bits, retaining all aliases."""
    if not isinstance(domains, dict):
        raise ValueError('input domains must be an object')
    if not isinstance(ports, dict) or any(not isinstance(p, dict) for p in ports.values()):
        raise ValueError('input-domain audit requires port objects')
    aliases, bindings = defaultdict(list), defaultdict(list)
    for name, port in sorted(ports.items()):
        if port.get('direction') != 'input':
            continue
        bits = port.get('bits')
        if not isinstance(bits, list) or not bits or any(type(b) is not int or b < 0 for b in bits):
            raise ValueError(f'{name}: input-domain audit requires input net bits')
        for offset, bit in enumerate(bits):
            aliases[bitkey(bit)].append({'port': name, 'offset': offset})
    for name, spec in sorted(domains.items()):
        port = ports.get(name, {})
        if port.get('direction') != 'input':
            raise ValueError(f'{name}: domain target must be an input port')
        if (not isinstance(spec, dict) or set(spec) != {'clock', 'evidence'} or
                any(not isinstance(spec[k], str) or not spec[k].strip() for k in spec)):
            raise ValueError(f'{name}: domain requires clock and nonempty evidence strings')
        clock = ports.get(spec['clock'], {})
        if clock.get('direction') != 'input' or len(clock.get('bits', [])) != 1:
            raise ValueError(f'{name}: clock must name a scalar input port')
        clock_bit = bitkey(clock['bits'][0])
        for bit in port['bits']:
            bindings[bitkey(bit)].append((clock_bit, dict(port=name, **spec)))
    result = {}
    for bit, names in aliases.items():
        clocks = {clock for clock, _ in bindings[bit]}
        if len(clocks) > 1:
            raise ValueError(f'conflicting input-domain assumptions for net {bit}')
        result[bit] = {'name': 'PRIMARY_INPUT', 'clk': next(iter(clocks), 'UNKNOWN'), 'src': '',
                       'source_ports': names, 'source_bit': bit,
                       'input_domain_assumptions': [spec for _, spec in bindings[bit]]}
    return result


def check(data, top, input_domains=None, max_traversal_work=1_000_000):
    if type(max_traversal_work) is not int or max_traversal_work <= 0:
        raise ValueError('max traversal work must be a positive integer')
    modules = data.get("modules", {})
    if top not in modules:
        raise ValueError(f"top module {top!r} not found")
    mod = modules[top]
    cells = mod.get("cells", {})
    aliases = defaultdict(list)
    netnames = mod.get("netnames", {})
    if not isinstance(netnames, dict):
        raise ValueError('netnames must be an object')
    for name, net in netnames.items():
        if (not isinstance(name, str) or not isinstance(net, dict) or
                not isinstance(net.get('bits'), list)):
            raise ValueError('netnames entries require names and bit lists')
        for offset, bit in enumerate(net['bits']):
            if type(bit) is int and bit >= 0:
                aliases[bitkey(bit)].append({'name': name, 'offset': offset})
            elif not (isinstance(bit, str) and bit in {'0', '1', 'x', 'z'}):
                raise ValueError(f'{name}: invalid netname bit')
    for names in aliases.values():
        names.sort(key=lambda item: (item['name'], item['offset']))
    primary = input_domain_sources(mod.get('ports', {}), input_domains) if input_domains is not None else None
    drivers, unknowns, ffs, inputs = defaultdict(list), defaultdict(list), {}, set()
    reset_input_ports = defaultdict(list)
    unknown_cells = []
    for name, p in sorted(mod.get("ports", {}).items()):
        if p.get("direction") == "input":
            inputs.update(map(bitkey, p.get("bits", [])))
            for offset, bit in enumerate(p.get("bits", [])):
                if type(bit) is int and bit >= 0:
                    reset_input_ports[bitkey(bit)].append({'port': name, 'offset': offset})
    for name, c in cells.items():
        typ, conns = c.get("type", ""), c.get("connections", {})
        dirs = c.get("port_directions", {})
        expected_dirs = None
        if typ in COMB:
            expected_dirs = {**{p: "input" for p in COMB[typ]}, "Y": "output"}
        elif typ in FFS or typ in RESET_FFS:
            expected_dirs = {"D": "input", "Q": "output", "C": "input"}
            if typ in RESET_FFS:
                expected_dirs["R"] = "input"
        if expected_dirs is not None:
            ports_valid = (isinstance(conns, dict) and set(conns) == set(expected_dirs) and
                           dirs == expected_dirs and
                           all(isinstance(bits, list) and len(bits) == 1 and
                               (type(bits[0]) is int and bits[0] >= 0 or
                                isinstance(bits[0], str) and bits[0] in {"0", "1", "x", "z"})
                               for bits in conns.values()))
            if not ports_valid:
                unknown_cells.append((name, typ, c.get("attributes", {}).get("src", "")))
                # Invalid port metadata cannot establish which pins drive nets.
                for bits in (conns.values() if isinstance(conns, dict) else []):
                    for bit in (bits if isinstance(bits, list) else []):
                        if type(bit) is int and bit >= 0:
                            kind = "combinational" if typ in COMB else "sequential"
                            unknowns[bitkey(bit)].append((name, f"unsupported {kind} ports or width"))
                continue
        if typ in FFS or typ in RESET_FFS:
            ds, qs, cs = conns["D"], conns["Q"], conns["C"]
            ff = {"name": name, "d": bitkey(ds[0]), "q": bitkey(qs[0]), "clk": bitkey(cs[0]),
                  "async": marked(c.get("attributes", {}).get("async_reg", "0")),
                  "src": c.get("attributes", {}).get("src", "")}
            ff["edge"] = "posedge" if typ[6] == "P" else "negedge"
            if typ in RESET_FFS:
                _, reset, value = RESET_FFS[typ]
                ff["reset_bit"] = bitkey(conns["R"][0])
                ff["reset"] = {"bit": str(conns["R"][0]), "active_level": int(reset == "P"),
                               "value": value, "clock_edge": ff["edge"]}
            ffs[name] = ff
            drivers[ff["q"]].append((name, "Q"))
        elif typ in COMB:
            for port, bits in conns.items():
                if dirs.get(port) == "output":
                    for b in bits: drivers[bitkey(b)].append((name, port))
        elif typ.startswith("$") and "mem" in typ.lower():
            unknown_cells.append((name, typ, c.get("attributes", {}).get("src", "")))
            for b in conns.get("RD_DATA", []): unknowns[bitkey(b)].append((name, "memory cell"))
        elif any(d == "output" for d in dirs.values()):
            unknown_cells.append((name, typ, c.get("attributes", {}).get("src", "")))
            for port, bits in conns.items():
                if dirs.get(port) == "output":
                    for b in bits: unknowns[bitkey(b)].append((name, f"unsupported cell {typ}"))
        else:
            unknown_cells.append((name, typ, c.get("attributes", {}).get("src", "")))
            for bits in conns.values():
                for b in bits: unknowns[bitkey(b)].append((name, f"unsupported cell with unknown ports {typ}"))
    def clock_resolved(bit):
        return bit in inputs and not drivers.get(bit) and not unknowns.get(bit)

    def clock_origin(bit):
        """Describe direct input or one mapped gate hop; never infer clock safety."""
        if clock_resolved(bit) and reset_input_ports[bit]:
            return {'kind': 'direct_primary_input', 'ports': reset_input_ports[bit]}
        if bit in inputs or unknowns.get(bit) or len(drivers.get(bit, [])) != 1:
            return {'kind': 'UNKNOWN'}
        name, pin = drivers[bit][0]
        cell = cells[name]
        if pin != 'Y' or cell.get('type') not in {'$_AND_', '$_BUF_'}:
            return {'kind': 'UNKNOWN'}
        origins = []
        for pin in COMB[cell['type']]:
            source_bit = bitkey(cell['connections'][pin][0])
            if not clock_resolved(source_bit) or not reset_input_ports[source_bit]:
                return {'kind': 'UNKNOWN'}
            origins.append({'pin': pin, 'bit': source_bit, 'ports': reset_input_ports[source_bit]})
        return {'kind': 'one_hop_combinational', 'cell': name, 'cell_type': cell['type'],
                'location': cell.get('attributes', {}).get('src', ''), 'inputs': origins}

    # Stable traversal order matters when a finite budget yields a partial report.
    for entries in drivers.values():
        entries.sort()
    for entries in unknowns.values():
        entries.sort()
    remaining_work = max_traversal_work
    limit_path = ("traversal work budget exhausted; unexamined path count unknown",)

    def sources(start):
        nonlocal remaining_work
        stack = [("visit", start)]
        trail, ambiguity, active = [], [], set()
        while stack:
            action, value = stack.pop()
            cost = 0
            if action == "visit":
                cost = 1
            elif action == "leaf":
                cost = len(trail) + len(ambiguity) + 1
            if cost > remaining_work:
                yield None, limit_path, True
                return
            remaining_work -= cost
            if action == "pop_path":
                trail.pop()
            elif action == "leave":
                bit, multiple = value
                active.remove(bit)
                if multiple:
                    ambiguity.pop()
            elif action == "descend":
                bit, label = value
                trail.append(label)
                stack.extend([("pop_path", None), ("visit", bit)])
            elif action == "leaf":
                src, label, unknown = value
                yield src, tuple(trail) + (label,) + tuple(reversed(ambiguity)), bool(unknown or ambiguity)
            else:
                bit = value
                if bit in active:
                    stack.append(("leaf", (None, "combinational loop", True)))
                    continue
                if bit in inputs:
                    ambiguous = drivers.get(bit) or unknowns.get(bit)
                    if primary is None:
                        label = (f"PRIMARY_INPUT net {bit}: input net also has internal driver"
                                 if ambiguous else "PRIMARY_INPUT")
                        stack.append(("leaf", (None, label, bool(ambiguous))))
                    else:
                        src = primary[bit]
                        clock_unresolved = drivers.get(src['clk']) or unknowns.get(src['clk'])
                        reason = ('input net also has internal driver' if ambiguous else
                                  'input-domain clock has internal driver' if clock_unresolved else
                                  'input domain undeclared' if src['clk'] == 'UNKNOWN' else 'declared input domain')
                        stack.append(("leaf", (src, f"PRIMARY_INPUT net {bit}: {reason}",
                                      bool(ambiguous or clock_unresolved or src['clk'] == 'UNKNOWN'))))
                    continue
                multiple = len(drivers.get(bit, [])) + len(unknowns.get(bit, [])) > 1
                active.add(bit)
                if multiple:
                    ambiguity.append(f"multiple drivers on net {bit}")
                stack.append(("leave", (bit, multiple)))
                actions = []
                for cell, port in drivers.get(bit, []):
                    if cell in ffs:
                        actions.append(("leaf", (ffs[cell], f"{cell}.Q", False)))
                        continue
                    c = cells[cell]
                    ins = [b for p, bs in sorted(c["connections"].items())
                           if c.get("port_directions", {}).get(p) == "input" for b in bs]
                    actions.extend(("descend", (bitkey(ib), f"{cell}.{port}")) for ib in ins)
                    if not ins:
                        actions.append(("leaf", (None, f"{cell}.{port}", True)))
                actions.extend(("leaf", (None, f"{cell}: {why}", True)) for cell, why in unknowns.get(bit, []))
                if not actions:
                    actions.append(("leaf", (None, f"unresolved net {bit}", True)))
                stack.extend(reversed(actions))

    # Candidate requires both destination stages explicitly annotated, same clock,
    # and a direct Q-to-D stage connection.
    second_stage = defaultdict(list)
    for ff in ffs.values():
        second_stage[ff['d']].append(ff)
    consumers = defaultdict(list)
    for name, cell in cells.items():
        conns = cell.get('connections')
        dirs = cell.get('port_directions')
        for port, bits in (conns.items() if isinstance(conns, dict) else []):
            if isinstance(dirs, dict) and dirs.get(port) == 'output':
                continue
            for bit in bits if isinstance(bits, list) else []:
                if type(bit) is int and bit >= 0:
                    consumers[bitkey(bit)].append({'cell': name, 'port': port})
    for name, port in mod.get('ports', {}).items():
        if port.get('direction') in {'output', 'inout'}:
            for bit in port.get('bits', []):
                if type(bit) is int and bit >= 0:
                    consumers[bitkey(bit)].append({'cell': 'TOP_OUTPUT', 'port': name})
    for uses in consumers.values():
        uses.sort(key=lambda use: (use['cell'], use['port']))

    def sync_structure(first):
        """Report mapped topology only; annotation and protocol safety are separate."""
        bit = first['q']
        uses = consumers[bit]
        stages = second_stage[bit]
        second = stages[0] if len(stages) == 1 else None
        if (bit.startswith("'") or drivers.get(bit) != [(first['name'], 'Q')] or
                unknowns.get(bit) or bit in inputs):
            reason = 'first-stage Q has ambiguous driver'
        elif second is None:
            reason = 'no unique mapped second stage'
        elif uses != [{'cell': second['name'], 'port': 'D'}]:
            reason = 'first-stage Q has other consumers'
        elif (first['clk'] != second['clk'] or first['edge'] != second['edge'] or
              first.get('reset') != second.get('reset') or
              first.get('reset_bit') != second.get('reset_bit')):
            reason = 'clock/edge/reset mismatch'
        else:
            reason = ''
        return {'status': 'UNKNOWN' if reason else 'two_stage_structure', 'safety': 'UNKNOWN',
                'first_stage': {'cell': first['name'], 'location': first['src'], 'q_bit': bit},
                'second_stage': ({'cell': second['name'], 'location': second['src']}
                                 if second else None),
                'first_q_consumers': uses, 'reason': reason}
    reports = []
    for name, typ, src in unknown_cells:
        reports.append({"top": top, "source_cell": name, "source_clock": "UNKNOWN", "destination_cell": name,
                        "destination_clock": "UNKNOWN", "path": [f"unsupported cell {typ}"],
                        "classification": "UNKNOWN", "source": src})
    for _, dst in sorted(ffs.items()):
        if "reset" in dst:
            reports.append({"top": top, "source_cell": "UNKNOWN", "source_clock": "UNKNOWN",
                            "destination_cell": dst["name"], "destination_clock": dst["clk"],
                            "path": [f"{dst['name']}.R={dst['reset']['bit']}",
                                     "reset assertion/deassertion relationship unverified"],
                            "classification": "UNKNOWN", "source": dst["src"]})
        if not clock_resolved(dst["clk"]):
            reports.append({"top": top, "source_cell": "UNKNOWN", "source_clock": "UNKNOWN", "destination_cell": dst["name"],
                            "destination_clock": dst["clk"], "path": ["gated/derived or unresolved clock"],
                            "classification": "UNKNOWN", "source": dst["src"]})
            continue
        for src, path, unknown in sources(dst["d"]):
            if src and not unknown and not clock_resolved(src['clk']):
                unknown = True
                path += ('source clock unresolved',)
            if (src and not unknown and src['clk'] == dst['clk'] and
                    'edge' in src and src['edge'] != dst['edge']):
                unknown = True
                path += ('same-net opposite-edge timing unverified',)
            if unknown:
                reports.append({"top": top, "source_cell": src['name'] if src else "UNKNOWN", "source_clock": "UNKNOWN", "destination_cell": dst["name"],
                                "destination_clock": dst["clk"], "path": list(path), "classification": "UNKNOWN", "source": dst["src"]})
            elif src is None or src["clk"] == dst["clk"]:
                continue
            else:
                stages = second_stage.get(dst['q'], [])
                following = stages[0] if len(stages) == 1 else None
                candidate = (following and drivers.get(dst['q']) == [(dst['name'], 'Q')] and
                             not unknowns.get(dst['q']) and dst['q'] not in inputs and
                             following["clk"] == dst["clk"] and
                             following["edge"] == dst["edge"] and
                             following.get("reset") == dst.get("reset") and
                             following.get("reset_bit") == dst.get("reset_bit") and
                             dst["async"] and following["async"])
                reports.append({"top": top, "source_cell": src["name"], "source_clock": src["clk"], "destination_cell": dst["name"],
                                "destination_clock": dst["clk"], "path": list(path),
                                "classification": "CANDIDATE_SYNCHRONIZER" if candidate else "CROSSING", "source": dst["src"] or src["src"],
                                "synchronizer_structure": sync_structure(dst)})
            if path == limit_path:
                reports[-1].update(analysis_incomplete=True, max_traversal_work=max_traversal_work)
            if src and 'source_ports' in src:
                reports[-1].update({key: src[key] for key in
                                   ('source_ports', 'source_bit', 'input_domain_assumptions')})
    for report in reports:
        for role in ("source", "destination"):
            if role == 'source' and 'source_ports' in report:
                continue
            endpoint = ffs.get(report[f"{role}_cell"], {})
            if endpoint:
                report[f"{role}_location"] = endpoint['src']
                pin = 'q' if role == 'source' else 'd'
                report[f"{role}_{pin}_aliases"] = aliases.get(endpoint[pin], [])
                report[f"{role}_clock_bit"] = endpoint['clk']
                report[f"{role}_clock_edge"] = endpoint['edge']
                report[f"{role}_clock_origin"] = clock_origin(endpoint['clk'])
            if "reset" in endpoint:
                report[f"{role}_reset"] = endpoint["reset"]
                report[f"{role}_reset_bit"] = endpoint["reset_bit"]
                bit = endpoint["reset_bit"]
                ports = reset_input_ports[bit]
                report[f"{role}_reset_input_ports"] = ports
                report[f"{role}_reset_origin"] = ('direct_primary_input' if ports and not drivers.get(bit)
                                                  and not unknowns.get(bit) else 'UNKNOWN')
    reports.sort(key=lambda r: (r["destination_cell"], r["source_cell"], r["classification"], r["path"]))
    return reports


def main(argv=None):
    p = argparse.ArgumentParser(prog="qd-cdc")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("netlist")
    c.add_argument("--top", required=True)
    c.add_argument("--json", action="store_true")
    c.add_argument('--input-domains', help='JSON port-to-clock assumptions; {} audits all inputs as undeclared')
    c.add_argument('--max-traversal-work', type=int, default=1_000_000,
                   help='global budget for visited nets and emitted path labels (default: 1000000)')
    a = p.parse_args(argv)
    try:
        domains = None
        if a.input_domains:
            with open(a.input_domains) as f: domains = json.load(f)
            if not isinstance(domains, dict):
                raise ValueError('input domains must be an object')
        with open(a.netlist) as f: reports = check(json.load(f), a.top, input_domains=domains,
                                                  max_traversal_work=a.max_traversal_work)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"qd-cdc: {e}", file=sys.stderr)
        return 2
    if a.json:
        output = reports if domains is None else {
            'schema_version': 1, 'input_domains': domains, 'findings': reports,
            'scope': 'input-domain structural audit; not CDC safety proof'}
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        if domains is not None:
            print('Input-domain assumptions (unverified): ' + json.dumps(domains, sort_keys=True))
        for r in reports:
            print(f"{r['classification']}: {r['top']} {r['source_cell']}@{r['source_clock']} -> {r['destination_cell']}@{r['destination_clock']} path={' -> '.join(r['path'])} source={r['source'] or 'unknown'}")
    return 1 if reports else 0


if __name__ == "__main__":
    raise SystemExit(main())
