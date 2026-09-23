# Scalar combinational mapping integrity

A reproduced false-clean case connected clock-11 data to an AND gate feeding
clock 10, but declared the AND's B pin as output in JSON metadata. The previous
checker trusted that direction, never traversed B, and returned no findings.
All supported gate types now require exact scalar mappings before traversal;
malformed gates and their recoverable connections remain UNKNOWN.

A second boundary exposed integer net IDs 0/1 colliding with string constants
"0"/"1". Internal keys now distinguish them, so a literal cannot borrow an input
port's clock/domain identity or match a different reset net in a candidate chain.
Existing nested reset metadata remains compatible; additive reset-bit fields
quote constants explicitly. Quoted constant references can also appear in paths
and clock-bit fields. Constant propagation and reset safety are not inferred.

## Evidence

Commands from the repository root:

```sh
python3 -m unittest -v
/usr/bin/python3 -m unittest -v
python3 run_opentitan_reqack_pilot.py /path/to/clean/opentitan /tmp/new-gate-pilot
```

46 tests pass on Python 3.14.7 and 3.9.6, macOS arm64. Six new tests exercise
all inputs of all 13 gate types (including MUX select and AOI/OAI inputs), 130
malformed mappings, ordering, same-clock and constant boundaries, the false-clean
regression, and literal/net clock/reset collisions. The negative tests failed
before the fixes. Existing tests were not changed.

The independent pin inventory is
[Yosys simcells.v at 80ba43d26264738c93900129dc0aab7fab36c53f](https://github.com/YosysHQ/yosys/blob/80ba43d26264738c93900129dc0aab7fab36c53f/techlibs/common/simcells.v).
All 13 input lists were compared directly with these definitions. As a separate
oracle, `yosys -p 'read_json bad-direction.json; check -assert; write_json roundtrip.json'`
re-derives B as an input from the cell type, independently of the bad metadata;
QD-CDC then finds the crossing in the round-trip fixture. This is schema/connectivity
evidence, not a separate CDC safety engine. The malformed file is QD test data,
not modified application RTL or DV.

The pinned OpenTitan pilot repeats NRZ/RZ crossing identities and all prior
classification counts, retaining its native RZ parser failure and UNKNOWN
status. Caliptra's three clock-mode configurations also preserve their prior
classification counts. Reset-bit fields are additive; the OpenTitan RZ unresolved
constant path now distinguishes its literal explicitly. Yosys is 0.68+80
`621d943ac-dirty`, with bundled read_slang; this remains a development toolchain.
Raw tests, the independent round-trip fixture/logs, and pilot artifacts are in
`../evidence/cdc-combinational-ports/`.

Full JSON-schema coverage, scalable complete traversal, protocol proofs,
reset-release analysis and production qualification remain incomplete. A malformed
mapping is uncertainty about the input model, not proof of a hardware defect.
