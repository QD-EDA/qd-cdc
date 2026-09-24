# OpenTitan two-stage structure audit

The pinned OpenTitan `prim_sync_reqack` source at
`7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19` instantiates
`prim_flop_2sync` for both request and acknowledge paths. The generic mapped
netlists have no `async_reg` attributes, so QD-CDC continues to report these
as `CROSSING`, not annotated candidates. The new field audits only the mapped
first-Q to second-D structure. It does not prove CDC, handshake, reset, or
metastability safety.

The unmodified source was elaborated with native Yosys and `read_slang` in NRZ
and RZ modes. The existing pilot runner now independently reads raw JSON cell
pins, unique Q drivers, top-level output taps, and consumer lists, comparing
the two exact stage pairs in each successful
configuration with QD's output. Source endpoint aliases still identify request
and acknowledge. Findings stay unchanged:

| Configuration | CROSSING | UNKNOWN | Structure |
| --- | ---: | ---: | --- |
| native NRZ | 2 | 14 | both exact two-stage |
| native RZ | unavailable | whole mode | native frontend rejects logic cast |
| slang NRZ | 2 | 8 | both exact two-stage |
| slang RZ | 2 | 7 | both exact two-stage |

The new unit cases cover exact unannotated chains, side logic, clock/edge/reset mismatch,
unsupported/ambiguous/zero/multiple second stages, and exported first Q. All
existing tests remain passing. Reproduce with:

```sh
python3 -m unittest -q
python3 run_opentitan_reqack_pilot.py /path/to/clean/pinned/opentitan /tmp/new-cdc-sync-evidence
```

The pilot intentionally exits 2 after collecting evidence because qualification
is UNKNOWN. Raw commands, hashes, netlists, stdout/stderr, results, and timings
are under `../evidence/cdc-sync-structure-20260924-final3/`. Local tools are
Python 3.14.7, macOS arm64, and Yosys 0.68+80 `621d943ac-dirty` with bundled
`read_slang`; this dirty build is not a release pin. The current tiny audit
needs under 0.04 s per checker process including Python startup. The target
for this bounded pilot is under 1 s per report. The roadmap's Linux 100k-flop,
1M-gate, 60 s/4 GiB full-design target remains unmeasured.

Upstream source requires coordinated reset for NRZ; RZ has a different partial
reset contract. Neither is checked here. The synth configuration defines
`SYNTHESIS`, so source assertions and metastability-delay simulation are absent.
No application RTL or DV sources were changed. A separate CDC engine, an
assertion-enabled or formal protocol oracle, full hierarchy, and clean pinned
toolchain are still needed for qualification.
