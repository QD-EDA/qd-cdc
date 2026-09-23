# Asynchronous-reset data mapping: bounded evidence

This slice extends data traversal through the eight Yosys scalar
`$_DFF_[PN][PN][01]_` cells. It does not establish reset-release safety or full
CDC qualification. The full-tool destination in ROADMAP.md remains unchanged.

## Mapping and oracles

The installed Yosys `share/yosys/simcells.v` defines each cell's clock event,
reset polarity and reset value. `fixtures/reset_cell_oracle.sv` independently
executes all eight models in Icarus: explicit reset assertion, positive edge,
negative edge and asynchronous reassertion. Expected vectors are written
directly in the testbench; they do not call QD-CDC's mapping code. The initial
oracle draft depended on declaration-time initialization events and failed;
the checked-in version uses explicit reset transitions.

Thirteen Python tests pass (six original, seven new) on Python 3.9.6 and 3.14.7.
The new tests cover eight mappings, source/destination reset metadata, same-clock
and primary-input paths, annotation candidates, mismatched clock edges/reset
semantics, missing/wide/wrong-direction/extra/invalid ports, constant reset,
generated clocks, unsupported enable cells and reordered input dictionaries.
Legacy resetless test results remain passing. Candidate matching is tightened
to reject stages with different clock edges or reset mappings.

## Named real-design pilot

Caliptra RTL v2.1.2 SHA `49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e`, unmodified
`src/libs/rtl/caliptra_2ff_sync.sv`, WIDTH=1, RST_VAL=0. The QD-owned harness
adds one source register clocked by clk_a and drives the actual synchronizer
clocked by clk_b. No application RTL/DV or attributes were changed.

Manual source/netlist inventory: source_q drives sync.din_ff, which drives dout.
The source flop is `$_DFF_P_`; both destination flops are `$_DFF_PN0_` and share
rst_b. clk_a and clk_b are distinct top-level clock nets; their timing relationship
is an unproven harness assumption. Source locations point to Caliptra's always_ff
block, lines 27–36. No async_reg attribute exists on these cells, so no candidate
label is inferred from the module name.

Expected result: **one CROSSING and three UNKNOWNs, CLI exit 1**. Two UNKNOWNs
identify the reset endpoints and unresolved assertion/deassertion relationships.
The third preserves the unmodeled Yosys `$scopeinfo` cell. The prior checker
reported three unsupported-cell UNKNOWNs without tracing the crossing; it did
not pass this pilot either. Standalone synchronizer input-domain declarations
remain future work; this harness supplies a real source flop for the data trace.

```sh
python3 -m unittest -v
yosys -Q -p 'read_verilog -sv /path/to/caliptra-rtl/src/libs/rtl/caliptra_2ff_sync.sv fixtures/caliptra_sync_pilot.sv; hierarchy -top caliptra_sync_pilot; proc; flatten; opt; techmap; opt; write_json /tmp/qd-cdc-pilot.json'
./qd-cdc check /tmp/qd-cdc-pilot.json --top caliptra_sync_pilot --json
# Expected exit 1, not a qualification pass.
iverilog -g2012 -s reset_cell_oracle -o /tmp/qd-reset-oracle.vvp \
  /path/to/yosys/share/yosys/simcells.v fixtures/reset_cell_oracle.sv
vvp /tmp/qd-reset-oracle.vvp
```

Version matrix observed: Yosys 0.68+80 (`621d943ac-dirty`), Icarus/vvp 13.0
stable (`v13_0`), Python 3.9.6 and 3.14.7, macOS arm64. This dirty Yosys build
is development evidence only, not the pinned clean release toolchain required
by the roadmap. Five pilot CLI runs produced byte-identical reports, taking
0.0279–0.0289 s including Python startup, median 0.0286 s. This tiny case does
not establish the 100k-flop performance target.

Raw synthesis/model-simulation/test logs, baseline/new reports, commands, versions
and hashes are retained locally under `../evidence/cdc-caliptra-reset/`. This is
not a published release bundle. The fixtures and commands above are reproducible.

## Unproven scope

No independent commercial CDC engine, reset-domain analysis, reset-release
protocol proof, exhaustive state inventory, full input-schema validation,
hierarchical clock constraints, reconvergence analysis or full-chip scale is
established here. Yosys model simulation checks cell semantics; it is not an
independent CDC safety oracle. Primary-input domains and matching clock-net
identity alone remain insufficient evidence of safety. Unknowns are not waived.
