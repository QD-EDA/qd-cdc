# qd-cdc

Small structural CDC triage tool for synthesized Yosys JSON. It reports paths between different clock inputs as `CROSSING`, or as `CANDIDATE_SYNCHRONIZER` when both flops in a directly connected two-stage destination chain carry `async_reg`. The candidate label is not a safety waiver. `UNKNOWN` means the path or clock could not be resolved conservatively. A clean report does not establish CDC safety.

```sh
./qd-cdc check netlist.json --top TOP [--json]
python3 -m unittest -v
```

Exit status: 0 when no crossing or unknown is found (candidate synchronizers may be reported); 1 when any `CROSSING` or `UNKNOWN` is found; 2 for invalid input or missing top. JSON results are sorted deterministically and include source cell, destination cell, clocks, path, classification, and Yosys `src` attributes when present.

## Supported netlist cells

Supported sequential cells are single-bit `$_DFF_P_` and `$_DFF_N_`. Supported combinational cells are `$_AND_`, `$_OR_`, `$_XOR_`, `$_XNOR_`, `$_NOT_`, `$_BUF_`, `$_MUX_`, `$_NAND_`, `$_NOR_`, `$_AOI3_`, `$_OAI3_`, `$_AOI4_`, and `$_OAI4_`. These are the Yosys internal gate-level cell names; generic `$dff`, latches, memories, black boxes, other sequential cells, and other combinational cells remain `UNKNOWN` when they affect a traced path. Clock pins must be driven directly by top-level input ports. Gated, derived, and unresolved clocks are reported `UNKNOWN`.

For a real Yosys example, `fixtures/crossing.sv` can be lowered with:

```sh
yosys -Q -p 'read_verilog -sv fixtures/crossing.sv; hierarchy -top crossing; proc; opt; techmap; opt; write_json /tmp/qd-cdc.json'
./qd-cdc check /tmp/qd-cdc.json --top crossing
```

Generated or related clocks are treated as unrelated. This version has no clock map, waiver mechanism, timing analysis, or CDC signoff claim. It does not silently ignore unsupported cells; any encountered output path that cannot be traced is `UNKNOWN`.

Licensed under Apache-2.0; see [LICENSE](LICENSE).
