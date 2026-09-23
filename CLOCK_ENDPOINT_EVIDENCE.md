# Clock endpoint resolution evidence

Previously, receiving clocks were checked but launch clocks were not. A launch
flop driven by a gate could produce CROSSING or CANDIDATE_SYNCHRONIZER at the
receiver even though its clock relationship was unresolved. Unsupported internal
drivers on top-level clock nets were also missed by the receiving-clock check.
Finally, opposite-edge transfers on the same clock net were silently omitted.

Both flop endpoints now require a top-level input clock net with no supported or
unsupported internal driver before classification as a crossing/candidate. An
unresolved launch clock retains its source cell and path as UNKNOWN. Opposite
edges on the same net produce UNKNOWN because half-cycle timing is not checked;
this is not a claim that every opposite-edge transfer is an asynchronous CDC.
Resolved same-edge same-net transfers retain their previous behavior.

Findings add `source_clock_bit` / `destination_clock_bit` and corresponding
`*_clock_edge` fields when that endpoint is a mapped flop. Thus an UNKNOWN source
clock still retains the actual net identity. Primary-input domain assumptions
have no declared launch edge and retain their prior explicitly bounded semantics.
The existing JSON array/wrapper structure and exit codes are unchanged.

## Checks and pinned pilot

Three new regressions failed before the fix: derived launch candidate, internally
driven top-level clock, and same-net opposite edges. Five new tests now pass,
including preserved positive/same-edge behavior and ordering. All 26 tests pass
under Python 3.14.7 and Apple Python 3.9.6; no existing tests were weakened.

`fixtures/caliptra_clock_pilot.sv` compiles the unchanged Caliptra RTL v2.1.2
synchronizer at commit `49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e`, WIDTH=1,
RST_VAL=0. The separate QD harness selects launch/capture configuration only.
Reproduce each mode (replace the paths and MODE with 0, 1 or 2):

```sh
python3 -m unittest -v
/usr/bin/python3 -m unittest -v
yosys -Q -p 'read_verilog -sv /path/to/caliptra-rtl/src/libs/rtl/caliptra_2ff_sync.sv fixtures/caliptra_clock_pilot.sv; chparam -set CLOCK_MODE MODE caliptra_clock_pilot; hierarchy -top caliptra_clock_pilot; proc; flatten; opt; techmap; opt; write_json /tmp/clock-pilot.json'
./qd-cdc check /tmp/clock-pilot.json --top caliptra_clock_pilot --json
# Each mode must exit 1: findings are unresolved work, not a qualification pass.
```

| Mode | Launch / capture | Expected findings |
|---|---|---|
| 0 | clk_a posedge / clk_b posedge | 1 CROSSING, 3 UNKNOWN |
| 1 | clk_a AND gate_en posedge / clk_b posedge | 5 UNKNOWN |
| 2 | clk_a negedge / clk_a posedge | 4 UNKNOWN |

Every mode retains two reset-relationship UNKNOWNs and one unsupported
`$scopeinfo` UNKNOWN. Mode 1 adds unresolved source-clock inventory and data-path
UNKNOWN. Mode 2 adds the previously omitted opposite-edge data path. Neither
mode introduces a synchronizer-safety claim. The unannotated real synchronizer
still has no annotation-only candidate label.

The independent manual inventory is source_q -> sync.din_ff -> dout. In mode 1
an AND cell drives the launch flop's C pin; in mode 2 the source maps to
`$_DFF_N_` while the first destination maps to `$_DFF_PN0_` on the same net.
The local pilot identifies source_q through Yosys netnames and checks its Q driver,
not unstable generated cell names. Two CLI runs per netlist were byte-identical.

Local evidence is in `../evidence/cdc-clock-endpoints/`: raw synthesis and checker
stdout/stderr, mapped netlists, input SHA256 hashes, exact argv, statuses, timings
and Yosys version. This is development evidence, not a published release bundle.
Yosys is 0.68+80 (`621d943ac-dirty`); the dirty build remains unsuitable as the
immutable release toolchain. Default CI runs only the Python regression suite.

## Still unknown

No generated-clock propagation, master/ratio/phase constraints, timing analysis,
reset-release proof, full-chip coverage or independent CDC-engine comparison is
implemented. Unknown clock endpoints block this classification; they do not
resolve the underlying relationship. Multiple data drivers, combinational schema
validation and scalable complete path enumeration remain separate qualification
work. The full CDC roadmap remains active.
