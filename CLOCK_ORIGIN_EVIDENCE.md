# One-hop clock-origin provenance

This change adds source-linked input/gate identity to mapped flop clock
endpoints. It changes no crossing, candidate, or UNKNOWN decisions. A direct
input lists all top-level aliases. A uniquely driven `$_AND_` or `$_BUF_`
lists its gate source annotation and each pin's direct input aliases. Otherwise
the origin is `UNKNOWN`. `$_AND_` pin names do not establish which input is a
master clock or control. No timing, glitch-free gating, or CDC safety follows.

The unchanged Caliptra RTL v2.1.2 `caliptra_2ff_sync.sv` at
`49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e` was compiled with the
QD-owned `fixtures/caliptra_clock_pilot.sv` in modes 0, 1, and 2. Results
remain respectively 1 CROSSING + 3 UNKNOWN, 5 UNKNOWN, and 4 UNKNOWN. In
mode 1, raw Yosys JSON independently shows the launch flop C pin on the
`$_AND_` Y net, with A on `clk_a` and B on `gate_en`; the reported gate source
matches the netlist annotation. This only proves mapped connectivity in this
small harness. The real Caliptra synchronizer is unmodified.

Reproduce the checks:

```sh
python3 -m unittest -q
/usr/bin/python3 -m unittest -q
# From the QD-EDA parent directory, with the pinned Caliptra checkout present:
python3 evidence/cdc-clock-origin-20260924/run.py
```

Local results: 59 tests pass with Python 3.14.7 and 3.9.6. Yosys is 0.68+80
`621d943ac-dirty` on macOS arm64. Two report runs per pilot mode matched
byte-for-byte; the six final report runs had a 0.0299 s median including Python
startup. The development Yosys build, tiny harness, and one host do not meet
the roadmap's immutable-tool, independent-engine, Linux, or full-chip scale
qualification gates. Raw commands, netlists, outputs, hashes and timings are
in the local `QD-EDA/evidence/cdc-clock-origin-20260924/` bundle.
