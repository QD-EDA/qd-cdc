# Scalar DFF validation correction

The checker previously validated resettable DFF ports but accepted an ordinary
DFF with Q declared as an input, extra connections, or malformed bit values.
Null connections could raise an uncaught exception. This could give malformed
input resolved crossing/candidate semantics. One shared validation block now
covers both clock edges and all eight asynchronous-reset variants.

The pin oracle is the pinned Yosys
[simcells.v definitions](https://github.com/YosysHQ/yosys/blob/80ba43d26264738c93900129dc0aab7fab36c53f/techlibs/common/simcells.v):
ordinary DFFs have scalar D/C inputs and Q output; resettable variants add R.
Malformed mappings remain UNKNOWN. Because their direction metadata is invalid,
all recoverable connected integer nets are treated as potentially driven. This
can increase uncertainty on shared clock/data nets; it does not infer a new
real hardware driver or repair the netlist.

## Regression evidence

```sh
python3 -m unittest -v
/usr/bin/python3 -m unittest -v
```

All 35 tests pass on macOS arm64 with Python 3.14.7 and 3.9.6. Four new tests
exercise 54 plain-flop pin mutations (two edges, three pins, nine malformed
values), seven metadata/port mutations, malformed extra-output connectivity,
reordered cells, valid edges/same-clock behavior and four legal scalar constants.
The malformed tests failed before the fix. Previous tests remain unchanged.
Legal constants are syntax support, not clock/domain evidence.

The three actual Caliptra clock-mode pilots in CLOCK_ENDPOINT_EVIDENCE.md were
resynthesized from unchanged v2.1.2 `49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e`.
With Yosys 0.68+80 `621d943ac-dirty`, reports are byte-identical to the pre-change
checker: mode 0 has one CROSSING and three UNKNOWN; mode 1 has five UNKNOWN;
mode 2 has four UNKNOWN. Every CLI exits 1. The QD-generated malformed extra-port
JSON is independently rejected by `yosys -p 'read_json malformed.json; check -assert'`.
Raw commands, versions, netlists, baseline/new reports and statuses are in the
local development bundle `../evidence/cdc-scalar-ports/`.

This closes a mapped-flop input-validation gap. It does not establish general
schema validation, reset-release proof, generated-clock relationships, scalable
path enumeration or full CDC qualification. The local dirty Yosys build is not
a qualified release toolchain. No application RTL/DV or existing tests changed.
