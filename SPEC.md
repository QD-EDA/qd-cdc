# QD-CDC v0 scope

Build a conservative structural clock-domain-crossing triage tool for synthesized Yosys JSON, not a substitute for Questa CDC signoff. This tool exists to find concrete Caliptra/OpenTitan candidate crossings with an auditable path. Do not claim that an unreported crossing is safe.

CLI: `qd-cdc check netlist.json --top TOP [--json]`. Read Yosys `write_json` modules, cells, connections, and attributes. Identify supported edge-triggered DFFs and their clock nets. For each receiving DFF D input, traverse supported combinational cells backwards to source DFF Q nets and primary inputs, report source-clock to destination-clock paths when clocks differ. Recognize an explicit `async_reg` attribute on a two-flop destination chain as a candidate synchronizer and report it separately; do not blanket-waive it as proven safe. Report black boxes, unknown sequential cells, unsupported combinational cells, gated/derived clocks, and paths that cannot be resolved as UNKNOWN.

Diagnostics must include top, source/destination cell and clock, path, classification, source file/line if present, and a deterministic exit code. Optional JSON output. Treat related generated clocks as unrelated unless an explicit user map is supplied and documented. No implicit waivers and no parser that silently drops cells.

Tests: direct crossing flagged; same-clock path not flagged; two-flop annotated candidate; unannotated two-flop still flagged; combinational crossing; unknown/blackbox path preserved as UNKNOWN; reproducible JSON ordering. Use Python standard library. If feasible, add one tiny Verilog fixture and invoke installed Yosys to generate a real JSON input, but keep pure JSON tests so the repo works without Yosys. Add README with exact supported Yosys cell types, limits, Apache-2.0 license, and local test command. Do not edit Caliptra or Icarus sources. Do not commit/push/create remote; coordinator handles publication.

## Asynchronous-reset mapping slice

Support scalar Yosys `$_DFF_[PN][PN][01]_` data traversal using documented cell
semantics, validating D/Q/C/R ports first. Inventory each mapped reset endpoint
as an UNKNOWN relationship, with bit/polarity/value/clock-edge metadata. Do not
infer safe reset release, CDC safety or waivers from mapping or async_reg. Require
matching clock edges and reset mappings for the existing candidate-chain hint.
Preserve CLI/report-list structure and original passing tests. Validate all eight
types, malformed mappings, constants, generated clocks and candidate boundaries;
pilot the unmodified pinned Caliptra WIDTH=1/RST_VAL=0 synchronizer in a QD harness.

## Input-domain audit slice

`--input-domains FILE` opts into primary-input data analysis, using a JSON object
of port names mapped to clock/evidence strings. Validate top-level input names,
scalar clock inputs, legal input bits and alias consistency. Undeclared paths
remain UNKNOWN. Preserve source ports, bit offsets and assumptions. JSON in this
mode wraps findings with all declarations, including when findings are empty.
This is not a waiver system or verified external timing. Legacy mode remains
compatible and explicitly omits primary-input domains from findings.

## Clock endpoint resolution correction

Validate both source and destination clock origins against supported and unknown
internal drivers. Preserve unresolved launch paths as UNKNOWN with source identity.
Report same-net opposite-edge mapped-flop transfers as UNKNOWN rather than dropping
them. Include endpoint clock bits/edges without changing report containers or exit
codes. Preserve resolved same-edge behavior and primary-input assumption semantics;
do not infer generated-clock relationships or half-cycle timing safety.

## Ambiguous data connectivity

Propagate multiple-driver uncertainty through supported combinational traversal,
preserving all enumerated driver paths as UNKNOWN instead of resolved crossing
or candidate labels. Conflicting internal drivers on primary-input nets must be
visible even in legacy mode. Candidate hints require one mapped-flop D consumer
and an unambiguous first-stage Q driver; cell ordering must not change results.
Preserve ordinary single-driver and existing Caliptra pilot behavior.

## Scalar DFF mapping validation

Apply the existing scalar port/direction/bit validation to resetless as well as
resettable supported DFFs. Reject malformed port containers without crashing.
Do not assign clock/data semantics or candidate hints to malformed mappings;
inventory them as UNKNOWN and conservatively propagate uncertainty onto every
recoverable connected net. Preserve reports for valid netlists and Caliptra
pilots. Full module/combinational schema validation remains separate work.
