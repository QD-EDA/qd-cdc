#!/usr/bin/env python3
"""Conservative structural CDC triage for Yosys JSON."""
import argparse
import json
import sys
from collections import defaultdict, deque


FFS = {"$_DFF_P_", "$_DFF_N_"}
COMB = {"$_AND_", "$_OR_", "$_XOR_", "$_XNOR_", "$_NOT_", "$_BUF_",
        "$_MUX_", "$_NAND_", "$_NOR_", "$_AOI3_", "$_OAI3_", "$_AOI4_", "$_OAI4_"}


def bitkey(bit):
    return str(bit)


def marked(value):
    value = str(value).lower()
    if value in {"true", "yes"}: return True
    try: return int(value, 2) != 0
    except ValueError: return False


def check(data, top):
    modules = data.get("modules", {})
    if top not in modules:
        raise ValueError(f"top module {top!r} not found")
    mod = modules[top]
    cells = mod.get("cells", {})
    drivers, unknowns, ffs, inputs = defaultdict(list), defaultdict(list), {}, set()
    for name, p in mod.get("ports", {}).items():
        if p.get("direction") == "input":
            inputs.update(map(bitkey, p.get("bits", [])))
    for name, c in cells.items():
        typ, conns = c.get("type", ""), c.get("connections", {})
        dirs = c.get("port_directions", {})
        if typ in FFS:
            ds, qs, cs = conns.get("D", []), conns.get("Q", []), conns.get("C", [])
            if len(ds) != 1 or len(qs) != 1 or len(cs) != 1:
                for b in qs: unknowns[bitkey(b)].append((name, "unsupported sequential width"))
                continue
            ff = {"name": name, "d": bitkey(ds[0]), "q": bitkey(qs[0]), "clk": bitkey(cs[0]),
                  "async": marked(c.get("attributes", {}).get("async_reg", "0")),
                  "src": c.get("attributes", {}).get("src", "")}
            ffs[name] = ff
            drivers[ff["q"]].append((name, "Q"))
        elif typ in COMB:
            for port, bits in conns.items():
                if dirs.get(port) == "output":
                    for b in bits: drivers[bitkey(b)].append((name, port))
        elif typ.startswith("$") and "mem" in typ.lower():
            for b in conns.get("RD_DATA", []): unknowns[bitkey(b)].append((name, "memory cell"))
        elif any(d == "output" for d in dirs.values()):
            for port, bits in conns.items():
                if dirs.get(port) == "output":
                    for b in bits: unknowns[bitkey(b)].append((name, f"unsupported cell {typ}"))
        else:
            for bits in conns.values():
                for b in bits: unknowns[bitkey(b)].append((name, f"unsupported cell with unknown ports {typ}"))
    # Trace each D through supported combinational fan-in. Each path retains the
    # cell trail so a black box or unsupported primitive cannot disappear.
    def sources(bit, trail=(), seen=frozenset()):
        if bit in seen: return [(None, trail + ("combinational loop",), True)]
        if bit in inputs: return [(None, trail + ("PRIMARY_INPUT",), False)]
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
        return found or [(None, trail + (f"unresolved net {bit}",), True)]

    # Candidate requires both destination stages explicitly annotated, same clock,
    # and a direct Q-to-D stage connection.
    second_stage = {f["d"]: f for f in ffs.values() if f["async"]}
    reports = []
    for dst in ffs.values():
        if dst["clk"] not in inputs or drivers.get(dst["clk"]):
            reports.append({"top": top, "source_cell": "UNKNOWN", "source_clock": "UNKNOWN", "destination_cell": dst["name"],
                            "destination_clock": dst["clk"], "path": ["gated/derived or unresolved clock"],
                            "classification": "UNKNOWN", "source": dst["src"]})
            continue
        for src, path, unknown in sources(dst["d"]):
            if unknown:
                reports.append({"top": top, "source_cell": "UNKNOWN", "source_clock": "UNKNOWN", "destination_cell": dst["name"],
                                "destination_clock": dst["clk"], "path": list(path), "classification": "UNKNOWN", "source": dst["src"]})
            elif src is None or src["clk"] == dst["clk"]:
                continue
            else:
                following = second_stage.get(dst["q"])
                candidate = following and following["clk"] == dst["clk"] and dst["async"] and following["async"]
                reports.append({"top": top, "source_cell": src["name"], "source_clock": src["clk"], "destination_cell": dst["name"],
                                "destination_clock": dst["clk"], "path": list(path),
                                "classification": "CANDIDATE_SYNCHRONIZER" if candidate else "CROSSING", "source": dst["src"] or src["src"]})
    reports.sort(key=lambda r: (r["destination_cell"], r["source_cell"], r["classification"], r["path"]))
    return reports


def main(argv=None):
    p = argparse.ArgumentParser(prog="qd-cdc")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("netlist")
    c.add_argument("--top", required=True)
    c.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        with open(a.netlist) as f: reports = check(json.load(f), a.top)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"qd-cdc: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(reports, indent=2, sort_keys=True))
    else:
        for r in reports:
            print(f"{r['classification']}: {r['top']} {r['source_cell']}@{r['source_clock']} -> {r['destination_cell']}@{r['destination_clock']} path={' -> '.join(r['path'])} source={r['source'] or 'unknown'}")
    return 1 if any(r["classification"] in {"CROSSING", "UNKNOWN"} for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
