# Ambiguous data paths and candidate-chain evidence

The prior traversal could report resolved crossings or synchronizer candidates
for individual drivers of a multiply driven net. A same-clock driver could be
silently omitted. In addition, the second-stage dictionary retained one annotated
consumer per D net, so a fanout's candidate label could depend on cell ordering.

Traversal now marks every enumerated path through a net with multiple supported
and/or unsupported drivers UNKNOWN. Paths retain driver identity when resolved,
the cell trail, and the ambiguous net number. This propagates through supported
combinational fan-in. A primary-input net that also has an internal driver is
UNKNOWN even in legacy mode; ordinary legacy input-only paths remain omitted.
The opt-in input-domain audit retains its existing assumptions and alias evidence.

A candidate requires exactly one mapped-flop D consumer of the first stage Q,
and that Q must have only the first stage as its internal driver and not also be
a primary input. Existing annotation, clock-edge and reset checks remain. This
is still only a hint: arbitrary combinational/output fanout, protocol, reconvergence
and physical synchronizer suitability are not proved by this restriction.

## Verification

Five added regressions failed before implementation. All 31 tests now pass under
Python 3.14.7 and Apple Python 3.9.6, preserving all previous tests. New cases cover
multiple flop drivers including same-clock sources, a known/unsupported driver
mix, a conflicting primary input in legacy mode, second-stage fanout and Q-driver
ambiguity, dictionary reversal, and conflict propagation through combinational logic.
The clean annotated two-stage chain still receives a candidate hint.

```sh
python3 -m unittest -v
/usr/bin/python3 -m unittest -v
yosys -Q -p 'read_verilog -sv fixtures/multiple_drivers.sv; hierarchy -top multiple_drivers; proc; opt; techmap; opt; write_json /tmp/multiple.json; check -assert'
# Expected exit 1: Yosys independently reports multiple conflicting drivers.
./qd-cdc check /tmp/multiple.json --top multiple_drivers --json
# Expected exit 1: two UNKNOWN driver paths, no candidate label.
```

The negative fixture is QD-owned RTL, not a fault injected into application sources.
Yosys 0.68+80 (`621d943ac-dirty`) emits the netlist before check -assert rejects it.
That structural check is an independent connectivity oracle, not an independent
CDC-safety tool. The source manually has two flops driving shared_data, which
feeds an annotated two-stage chain. QD-CDC must preserve both ambiguous paths.

The unchanged Caliptra synchronizer at commit
`49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e` was rechecked in the three configurations
of CLOCK_ENDPOINT_EVIDENCE.md. Mode 0 retains 1 CROSSING/3 UNKNOWN, gated-launch
mode 1 retains 5 UNKNOWN, and opposite-edge mode 2 retains 4 UNKNOWN. Two reports
per netlist are byte-identical. No application RTL/DV or warnings were altered.

Local raw logs, netlists, reports, commands, hashes and tests are retained in
`../evidence/cdc-ambiguous-paths/`. They are not published release artifacts.
The installed dirty Yosys build, incomplete input-schema validation, hierarchical
state inventory, generated-clock constraints, broad fanout/reconvergence analysis,
independent CDC comparison and performance targets remain qualification gaps.
