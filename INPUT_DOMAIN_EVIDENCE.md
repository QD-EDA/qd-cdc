# Primary-input domains: bounded evidence

The former trace terminated at every primary input without a finding. The new
opt-in audit exposes undeclared input data paths as UNKNOWN and permits explicit
clock-domain assumptions. It does not establish a timing constraint or CDC proof.

## Tests and independent checks

All 21 tests pass on Python 3.14.7 and Apple Python 3.9.6: 13 existing and eight
new tests. New cases cover undeclared inputs, explicit cross/same-clock domains,
combinational fan-in, malformed/conflicting declarations, vector offsets and
aliases, deterministic ordering, candidate hints, internal drivers and CLI
preservation of assumptions even with zero findings. Existing tests are unchanged.

```sh
python3 -m unittest -v
/usr/bin/python3 -m unittest -v
```

The tiny test graph independently specifies input din bit 2, launch clock bit 11,
and capture clock bit 10. It must report a crossing under that declared launch
clock, UNKNOWN without a declaration, and no input crossing when assigned clock
10. The declaration is not inferred from the desired result. The checker retains
it in the CLI report so users can audit or reject the assumption. This truth-table
oracle checks structural bookkeeping, not analog timing or metastability.

## Pinned Caliptra pilot

Caliptra v2.1.2 `49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e` remained clean before
and after synthesis. The existing QD harness instantiates the unchanged real
`caliptra_2ff_sync`, WIDTH=1/RST_VAL=0, with a source flop on clk_a and two capture
flops on clk_b. Manual RTL/netlist inspection establishes din -> source flop D,
source flop Q -> synchronizer stage 1 D -> stage 2 D. The external din timing is
not established by the harness: its checked-in domain declaration explicitly
labels this as an integration assumption.

| Mode | CROSSING | UNKNOWN | CLI exit |
|---|---:|---:|---:|
| Legacy | 1 | 3 | 1 |
| Input audit, empty declarations | 1 | 4 | 1 |
| Input audit, din assigned clk_a | 1 | 3 | 1 |

The extra UNKNOWN is the previously omitted external din -> source register path.
Declaring its domain removes only that domain ambiguity. Both reset relationships
and the unsupported Yosys `$scopeinfo` remain UNKNOWN; no waiver is added.

```sh
# CALIPTRA_ROOT must refer to the clean pin above.
yosys -Q -p "read_verilog -sv $CALIPTRA_ROOT/src/libs/rtl/caliptra_2ff_sync.sv fixtures/caliptra_sync_pilot.sv; hierarchy -top caliptra_sync_pilot; proc; flatten; opt; techmap; opt; write_json /tmp/qd-cdc-inputs.json"
printf '{}\n' > /tmp/qd-empty-domains.json
./qd-cdc check /tmp/qd-cdc-inputs.json --top caliptra_sync_pilot --json
./qd-cdc check /tmp/qd-cdc-inputs.json --top caliptra_sync_pilot --json --input-domains /tmp/qd-empty-domains.json
./qd-cdc check /tmp/qd-cdc-inputs.json --top caliptra_sync_pilot --json --input-domains fixtures/caliptra_sync_input_domains.json
# Every check above is expected to exit 1.
```

Observed Yosys: 0.68+80, `621d943ac-dirty`, macOS arm64. This development build
is not a qualified toolchain. Five runs per mode produced byte-identical reports.
Median CLI wall times including Python startup were 0.0263 s legacy, 0.0271 s
empty audit, and 0.0261 s mapped audit. This does not establish full-chip scale.
Raw logs, netlist, timings, declarations and reports are local development
artifacts under `../evidence/cdc-input-domains/`, not published release evidence.

No independent commercial CDC oracle, timing model, external clock declaration,
output-domain analysis, exhaustive state coverage, generated-clock or reset
proof is established. An evidence string is retained provenance, not verified
truth or an approved waiver. Production qualification remains incomplete.
