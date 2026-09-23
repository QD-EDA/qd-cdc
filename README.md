# qd-cdc

`qd-cdc` is a conservative structural triage tool for synthesized Yosys JSON. It follows supported combinational logic backward from single-bit DFF inputs and reports paths between clocks. It cannot prove CDC safety, replace Questa CDC or sign off a design; no report or candidate label is a waiver.

## Requirements and quick start

Python 3 is required. Yosys is optional unless you want to create a netlist from the included fixture.

```sh
yosys -Q -p 'read_verilog -sv fixtures/crossing.sv; hierarchy -top crossing; proc; opt; techmap; opt; write_json /tmp/qd-cdc.json'
./qd-cdc check /tmp/qd-cdc.json --top crossing --json || test "$?" -eq 1
python3 -m unittest -v
```

The example reports a `CROSSING` from `clk_a` to `clk_b`. Input is a Yosys `write_json` file and the selected top module. Text output gives one finding per line; `--json` emits a deterministically sorted array with top, source/destination cells and clocks, traced path, classification, and Yosys `src` metadata when available.

## Findings and limits

- `CROSSING`: a resolved path connects DFFs on different clock nets.
- `CANDIDATE_SYNCHRONIZER`: both flops in a directly connected, same-destination-clock two-flop chain have a truthy `async_reg` attribute. This is a review hint only.
- `UNKNOWN`: the path or clock cannot be conservatively resolved. Unsupported cells are not silently discarded.

Exit codes: `0` means there are no findings; `1` means any finding was reported, including `CROSSING`, `UNKNOWN`, or `CANDIDATE_SYNCHRONIZER`; `2` means invalid JSON/input or a missing top. Unsupported cells that affect a traced path are `UNKNOWN`, so they also produce exit `1`.

Only single-bit `$_DFF_P_` and `$_DFF_N_` and the combinational cells `$_AND_`, `$_OR_`, `$_XOR_`, `$_XNOR_`, `$_NOT_`, `$_BUF_`, `$_MUX_`, `$_NAND_`, `$_NOR_`, `$_AOI3_`, `$_OAI3_`, `$_AOI4_`, and `$_OAI4_` are traced. Generic `$dff`, latches, memories, black boxes, other sequential/combinational cells, multi-bit flops, and unresolved, gated, or derived clocks can produce `UNKNOWN`. Clock pins must be driven directly by top-level inputs. Related/generated clocks are treated as unrelated. There is no clock map, waiver system, timing analysis, or signoff claim.

Licensed under Apache-2.0; see [LICENSE](LICENSE).

See [the staged qualification roadmap](ROADMAP.md) for named pilots, unsupported
cases, independent oracles, performance targets and release gates.
