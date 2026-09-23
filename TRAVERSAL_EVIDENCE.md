# Bounded traversal evidence

A valid 1,500-buffer chain previously raised Python RecursionError. Explicit
depth-first traversal now retains the complete source trace without Python
recursion. Reconvergent graphs can still contain exponentially many paths; a
global work budget stops enumeration visibly as UNKNOWN. No safety classifier
or synchronizer proof was added.

## Reproduction and results

On macOS arm64, Python 3.14.7 and 3.9.6 each passed all 52 tests:

```sh
python3 -m unittest -v
/usr/bin/python3 -m unittest -v
python3 -m unittest -v test_traversal
python3 run_opentitan_reqack_pilot.py /path/to/clean/opentitan /tmp/new-pilot
```

The six new tests cover a 1,500-gate path, all 256 paths through an eight-level
reconvergent fixture, bounded 20-level reconvergence, permutation invariance,
exact budget boundaries and invalid values, cycles with multiple drivers, and
CLI exit/JSON semantics. These synthetic graphs have manually specified
structural expectations; they do not model analog metastability.

A separate deterministic comparison (seed 20260923) matched the previous
implementation on 100 small generated graphs, including loops and multiple
drivers. This checks preservation, not an independent CDC safety oracle.

A single local 100,000-buffer chain measurement using `test_traversal.chain`
and `qd_cdc.check` took 0.256 seconds for analysis, with 167,706,624 bytes process
peak RSS (including fixture creation), and retained 100,001 path labels. This
is a synthetic single-path measurement, not the roadmap's Linux multi-flop
performance qualification or a bound on process memory.

All three elaborated OpenTitan request/acknowledge reports and all three
Caliptra scalar-port pilot reports were byte-identical to the preceding gate
mapping slice. Pins and configurations are in
[OpenTitan evidence](OPENTITAN_REQACK_EVIDENCE.md) and
[scalar-port evidence](SCALAR_PORT_EVIDENCE.md). The local Yosys was
0.68+80 `621d943ac-dirty`; its bundled read_slang revision is unestablished.
The OpenTitan runner still returns 2 (UNKNOWN): native return-to-zero
elaboration fails, and reset/protocol behavior remains unproved.

## Limits

The default 1,000,000 units count net visits plus materialized path labels,
including paths later omitted under legacy primary-input/same-clock behavior.
A destination whose next operation does not fit receives an UNKNOWN marker;
remaining budget can still serve another destination. The marker does not
claim a count of unexamined paths. Already enumerated findings are retained.
Loading, inventory, metadata, sorting and output serialization are outside
the budget. This is not a complete resource limiter or whole-design coverage
metric. Full-chip scaling, protocol correctness, generated-clock relations,
reset release and independent CDC-engine agreement remain unqualified.
