#!/usr/bin/env python3
"""Conservative structural CDC triage for Yosys JSON."""
import argparse
import json
import sys
from collections import defaultdict


FFS = {"$_DFF_P_", "$_DFF_N_"}
RESET_FFS = {f"$_DFF_{clock}{reset}{value}_": (clock, reset, int(value))
             for clock in "PN" for reset in "PN" for value in "01"}
COMB = {"$_AND_", "$_OR_", "$_XOR_", "$_XNOR_", "$_NOT_", "$_BUF_",
        "$_MUX_", "$_NAND_", "$_NOR_", "$_AOI3_", "$_OAI3_", "$_AOI4_", "$_OAI4_"}


def bitkey(bit):
    return str(bit)


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


def check(data, top, input_domains=None):
    modules = data.get("modules", {})
    if top not in modules:
        raise ValueError(f"top module {top!r} not found")
    mod = modules[top]
    cells = mod.get("cells", {})
    primary = input_domain_sources(mod.get('ports', {}), input_domains) if input_domains is not None else None
    drivers, unknowns, ffs, inputs = defaultdict(list), defaultdict(list), {}, set()
    unknown_cells = []
    for name, p in mod.get("ports", {}).items():
        if p.get("direction") == "input":
            inputs.update(map(bitkey, p.get("bits", [])))
    for name, c in cells.items():
        typ, conns = c.get("type", ""), c.get("connections", {})
        dirs = c.get("port_directions", {})
        if typ in FFS or typ in RESET_FFS:
            expected_dirs = {"D": "input", "Q": "output", "C": "input"}
            if typ in RESET_FFS:
                expected_dirs["R"] = "input"
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
                            unknowns[bitkey(bit)].append((name, "unsupported sequential ports or width"))
                continue
            ds, qs, cs = conns["D"], conns["Q"], conns["C"]
            ff = {"name": name, "d": bitkey(ds[0]), "q": bitkey(qs[0]), "clk": bitkey(cs[0]),
                  "async": marked(c.get("attributes", {}).get("async_reg", "0")),
                  "src": c.get("attributes", {}).get("src", "")}
            ff["edge"] = "posedge" if typ[6] == "P" else "negedge"
            if typ in RESET_FFS:
                _, reset, value = RESET_FFS[typ]
                ff["reset"] = {"bit": bitkey(conns["R"][0]), "active_level": int(reset == "P"),
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

    # Trace each D through supported combinational fan-in. Each path retains the
    # cell trail so a black box or unsupported primitive cannot disappear.
    def sources(bit, trail=(), seen=frozenset()):
        if bit in seen: return [(None, trail + ("combinational loop",), True)]
        if bit in inputs:
            if primary is None:
                if drivers.get(bit) or unknowns.get(bit):
                    return [(None, trail + (f"PRIMARY_INPUT net {bit}: input net also has internal driver",), True)]
                return [(None, trail + ("PRIMARY_INPUT",), False)]
            src = primary[bit]
            ambiguous = drivers.get(bit) or unknowns.get(bit)
            clock_unresolved = drivers.get(src['clk']) or unknowns.get(src['clk'])
            reason = ('input net also has internal driver' if ambiguous else
                      'input-domain clock has internal driver' if clock_unresolved else
                      'input domain undeclared' if src['clk'] == 'UNKNOWN' else 'declared input domain')
            return [(src, trail + (f"PRIMARY_INPUT net {bit}: {reason}",),
                     bool(ambiguous or clock_unresolved or src['clk'] == 'UNKNOWN'))]
        found = []
        for cell, port in drivers.get(bit, []):
            if cell in ffs:
                found.append((ffs[cell], trail + (f"{cell}.Q",), False))
                continue
            # Find all fan-in bits for a supported combinational driver.
            c = cells[cell]
            ins = [b for p, bs in c["connections"].items() if c.get("port_directions", {}).get(p) == "input" for b in bs]
            if ins:
                for ib in ins: found.extend(sources(bitkey(ib), trail + (f"{cell}.{port}",), seen | {bit}))
            else: found.append((None, trail + (f"{cell}.{port}",), True))
        for cell, why in unknowns.get(bit, []): found.append((None, trail + (f"{cell}: {why}",), True))
        if len(drivers.get(bit, [])) + len(unknowns.get(bit, [])) > 1:
            found = [(src, path + (f"multiple drivers on net {bit}",), True)
                     for src, path, _ in found]
        return found or [(None, trail + (f"unresolved net {bit}",), True)]

    # Candidate requires both destination stages explicitly annotated, same clock,
    # and a direct Q-to-D stage connection.
    second_stage = defaultdict(list)
    for ff in ffs.values():
        second_stage[ff['d']].append(ff)
    reports = []
    for name, typ, src in unknown_cells:
        reports.append({"top": top, "source_cell": name, "source_clock": "UNKNOWN", "destination_cell": name,
                        "destination_clock": "UNKNOWN", "path": [f"unsupported cell {typ}"],
                        "classification": "UNKNOWN", "source": src})
    for dst in ffs.values():
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
                             dst["async"] and following["async"])
                reports.append({"top": top, "source_cell": src["name"], "source_clock": src["clk"], "destination_cell": dst["name"],
                                "destination_clock": dst["clk"], "path": list(path),
                                "classification": "CANDIDATE_SYNCHRONIZER" if candidate else "CROSSING", "source": dst["src"] or src["src"]})
            if src and 'source_ports' in src:
                reports[-1].update({key: src[key] for key in
                                   ('source_ports', 'source_bit', 'input_domain_assumptions')})
    for report in reports:
        for role in ("source", "destination"):
            if role == 'source' and 'source_ports' in report:
                continue
            endpoint = ffs.get(report[f"{role}_cell"], {})
            if endpoint:
                report[f"{role}_clock_bit"] = endpoint['clk']
                report[f"{role}_clock_edge"] = endpoint['edge']
            if "reset" in endpoint:
                report[f"{role}_reset"] = endpoint["reset"]
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
    a = p.parse_args(argv)
    try:
        domains = None
        if a.input_domains:
            with open(a.input_domains) as f: domains = json.load(f)
            if not isinstance(domains, dict):
                raise ValueError('input domains must be an object')
        with open(a.netlist) as f: reports = check(json.load(f), a.top, input_domains=domains)
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
