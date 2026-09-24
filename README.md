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

Supported cells include single-bit `$_DFF_P_` and `$_DFF_N_`, the asynchronous-reset types below, and the combinational cells `$_AND_`, `$_OR_`, `$_XOR_`, `$_XNOR_`, `$_NOT_`, `$_BUF_`, `$_MUX_`, `$_NAND_`, `$_NOR_`, `$_AOI3_`, `$_OAI3_`, `$_AOI4_`, and `$_OAI4_` are traced. Generic `$dff`, latches, memories, black boxes, other sequential/combinational cells, multi-bit flops, and unresolved, gated, or derived clocks can produce `UNKNOWN`. Clock pins must be driven directly by top-level inputs. Related/generated clocks are treated as unrelated. There is no clock map, waiver system, timing analysis, or signoff claim.

### Asynchronous-reset DFF mapping

Data paths now also trace all eight single-bit Yosys `$_DFF_[PN][PN][01]_`
types. The three characters encode clock edge, active reset level and reset
value. These cells require exactly scalar D/Q/C/R connections with declared
input/output directions; malformed mappings remain UNKNOWN.

Every mapped reset endpoint emits an UNKNOWN finding: assertion/deassertion
relationships, reset-domain crossings and release timing are not verified yet.
JSON findings carry `source_reset` / `destination_reset` when applicable, with
bit, active level, reset value and clock edge. Constants do not waive this check.
They also list `source_reset_input_ports` / `destination_reset_input_ports`
with port names and bit-array offsets. `*_reset_origin` is
`direct_primary_input` only when that reset net has an input port and no
internal driver; otherwise it is `UNKNOWN`. A named input is an identity trace,
not a reset timing or release guarantee.
Candidate chains additionally require equal destination-stage clock edges and
reset mappings; annotations still provide no proof. Other reset/enable/latch
families remain unsupported. [Pilot evidence](ASYNC_RESET_EVIDENCE.md) documents
the real Caliptra mapping and its remaining unknowns.

Licensed under Apache-2.0; see [LICENSE](LICENSE).

See [the staged qualification roadmap](ROADMAP.md) for named pilots, unsupported
cases, independent oracles, performance targets and release gates.

## Primary-input domain audit

Legacy mode omits primary-input data paths from findings. Use
`--input-domains domains.json` to include them. An empty object `{}` leaves every
primary-input data path UNKNOWN. A declaration assigns a whole input port to a
scalar top-level clock input and must include a nonempty evidence description:

```json
{"din": {"clock": "clk_a", "evidence": "Integration contract reference; unverified assumption"}}
```

The clock association is an assumption, not checked timing or a reviewed waiver.
Same-clock associations produce no crossing finding; differing clocks produce
CROSSING or the existing annotation-only candidate hint. Unmapped inputs and
internally driven input/clock nets stay UNKNOWN. Conflicting aliases, absent
ports, nonscalar clocks and malformed declarations fail with exit 2. Vector
ports share one declared domain; reported offsets are positions in the Yosys
bit array, not necessarily HDL subscripts. All aliases remain visible.

With this option, JSON is an object containing `schema_version`, `scope`,
`input_domains`, and `findings`, so assumptions survive even a zero-finding run.
Input findings include `source_ports`, `source_bit`, and
`input_domain_assumptions`. Text output also prints the declarations. Exit codes
remain 0/1/2; zero means no findings within this bounded audit, not CDC safety.
Without the option, the existing JSON array and behavior are unchanged.

This covers top-level input fan-in of supported DFFs, not output timing, inout
boundaries, external clocks absent from the top, generated-clock relationships,
per-bit domain specifications, edge relationships or full design coverage.
See [input-domain evidence](INPUT_DOMAIN_EVIDENCE.md).

## Launch and capture clock boundaries

Both mapped flop clocks must resolve directly to top-level inputs without any
internal driver before a data path receives a crossing/candidate classification.
Unresolved launch clocks and opposite-edge transfers on the same net remain
UNKNOWN. Same-net opposite edges need timing evidence; their visibility is not
an assertion of asynchronous CDC. Findings include mapped endpoint clock bits
and edges. Input-domain declarations still do not specify launch edges.
See [clock endpoint evidence](CLOCK_ENDPOINT_EVIDENCE.md) for the Caliptra pilot
and supported limits.

Mapped endpoints also carry `*_clock_origin`. A directly driven input has its
top-level port aliases. A uniquely driven one-hop `$_AND_` or `$_BUF_` clock net
lists the gate cell/type/source annotation and each input pin's direct input
aliases. Any internal/ambiguous/constant/unsupported input yields `UNKNOWN`.
The two `$_AND_` inputs are symmetric: this trace does not identify a clock
master or gate control, validate glitch freedom, or change any CDC classification.
See [one-hop pilot evidence](CLOCK_ORIGIN_EVIDENCE.md).

## Ambiguous connectivity

Data nets with multiple supported/unsupported drivers remain UNKNOWN for every
traced driver path, including same-clock sources. This also applies when a
primary input has an internal driver, even in legacy mode. Candidate synchronizer
hints require one mapped-flop second-stage consumer and an unambiguous first-stage
Q driver. This does not prove arbitrary fanout or reconvergence safe. See
[ambiguity evidence](AMBIGUOUS_PATH_EVIDENCE.md) for the independent Yosys negative
fixture and preserved Caliptra results.

## Scalar flop input validation

All ten supported DFF types require exact scalar ports and matching declared
port directions before receiving clock/data semantics. Plain DFFs require
D/Q/C; asynchronous-reset DFFs additionally require R. Each connection must be
a one-element list containing a nonnegative integer net ID or Yosys constant
`0`, `1`, `x`, `z`; booleans and other strings are invalid. Malformed cells are
inventoried as UNKNOWN. Every recoverable integer connection on such a cell is
conservatively treated as possibly driven, because its port metadata cannot be
trusted; connected data and clock paths may therefore also become UNKNOWN.
This is not full JSON-schema validation. See [validation evidence](SCALAR_PORT_EVIDENCE.md).

## Endpoint source traces

JSON findings now retain both mapped endpoints' original `src` annotations as
`source_location` / `destination_location`. `source_q_aliases` and
`destination_d_aliases` list every Yosys netname for those pins, with `name` and
`offset` (position in the bit array, not an HDL subscript). Empty strings/lists
mean unavailable metadata. Names and locations are supplied by the netlist;
they are not independently verified file contents, unique identities or waivers.
The existing `source` field and text output remain unchanged. Malformed netname
metadata fails input validation rather than producing misleading traces.

The pinned OpenTitan request/acknowledge pilot exercises these traces:

```sh
python3 run_opentitan_reqack_pilot.py /path/to/clean/opentitan /tmp/new-reqack-evidence
```

It requires Yosys with `read_slang`, the documented OpenTitan pin, and simple paths
without spaces/metacharacters. It returns 2 (UNKNOWN) after collecting structural
evidence, or 1 on an unmet required check. See [pilot evidence](OPENTITAN_REQACK_EVIDENCE.md).

## Combinational mappings and constant identity

All 13 supported scalar gate types require their exact Yosys input pins and Y
output, scalar connection lists and matching directions. A malformed gate is
inventoried as UNKNOWN; every recoverable connected net is conservatively
possibly driven, just as for malformed DFFs. This prevents incorrect input
metadata from pruning a crossing and producing a false-clean report.

Integer net IDs and string constants remain distinct. In diagnostic bit references,
constants are quoted (`'0'`, `'1'`, `'x'`, `'z'`), while integer IDs remain decimal
strings. New `source_reset_bit` / `destination_reset_bit` fields preserve that
distinction; the existing nested reset `bit` value retains its legacy format.
Constants do not prove clock or reset safety. See [mapping evidence](COMBINATIONAL_PORT_EVIDENCE.md).

## Bounded traversal

Fan-in traversal is iterative. `--max-traversal-work N` sets a positive global
budget (default 1,000,000): one unit per visited net and per emitted path label.
If the next operation cannot fit, that destination gets an UNKNOWN finding with
`analysis_incomplete: true` and `max_traversal_work`; previously enumerated
findings remain visible. Unexamined path counts are unknown, not zero. Exit 1
prevents an incomplete traversal from appearing clean. Invalid budgets exit 2.
This is not a wall-time or total-memory cap: loading, inventory, sorting and
metadata are outside this budget. See [traversal evidence](TRAVERSAL_EVIDENCE.md).
