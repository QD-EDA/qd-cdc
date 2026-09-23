# QD-CDC: explainable clock and reset analysis

## Current capability

Baseline `024e784b4e04f3587f8de2761e129427b94bdf2e`: six Python tests;
CI runs `python3 -m unittest -v` without Yosys. The checker traces selected
single-bit Yosys DFFs through a small combinational set in one module, records
source metadata, and labels annotated two-stage chains as candidates only.
It neither elaborates RTL nor reasons about resets. Generated clocks and other
cells become UNKNOWN; primary-input paths have no domain evidence. A lack of
findings is not evidence that all crossings were examined.

## Stages and interfaces

1. **Next useful slice:** inventory all sequential cells and clock/reset endpoints
   before traversal; support a documented asynchronous-reset DFF mapping and
   external clock/reset declarations. Input: Yosys JSON, top, cell map, clock/reset
   assumptions. Output: deterministic JSON inventory, source/destination paths,
   reset polarity/deassertion relationships, and per-path UNKNOWN reasons.
   Validate cell ports/widths before assigning semantics; never infer safety from
   `async_reg`. Preserve the existing CLI and exit behavior.
2. **Pinned pilot:** Caliptra `src/libs/rtl/caliptra_2ff_sync.sv` and OpenTitan
   `hw/ip/prim/rtl/prim_sync_reqack.sv` plus generic flop dependencies. Produce
   elaboration/netlist evidence with source maps; explicitly inventory discarded
   attributes and unmodeled cells. Compare direct crossings and reset release
   paths with manually traced schematics and a separate CDC engine. A missing
   dependency or unsupported synthesis result blocks the pilot, not the report.
3. **Broaden one class at a time:** establish parser-backed RTL/netlist identity;
   classify pulse/data crossings, multi-bit synchronizers, asynchronous FIFO
   Gray pointers, handshakes, and reconvergence. Each class needs protocol
   assumptions, timing constraints, counterexamples, and an independent oracle.
   Generated clocks need explicit master/ratio/phase/gating relations and reset
   interaction; unresolved relations remain UNKNOWN. Add evidence-backed waiver
   review after stable finding IDs exist.
4. **Production qualification:** first qualify only the named mapped single-bit
   synchronizer/reset-release triage configurations. Include clock/reset mode
   matrices and design-owner review. FIFO/handshake/reconvergence claims require
   their own subsequent qualification. Analog metastability probability, MTBF,
   placement, timing exceptions, and silicon behavior remain outside this scope.

## Evidence and release criteria

- Regression corpus: existing six cases plus opposite clock edges, reset
  polarity/asynchronous assertion/synchronous release, constants, primary inputs,
  multiple drivers, loops, black boxes, reconvergent fanout, fake annotations,
  generated/gated clocks, width mismatches, and missing source metadata.
- Independent oracles: manual cell-level path inventory for tiny circuits;
  Yosys-generated netlists compared with another elaborator; a separately
  implemented CDC tool and formal protocol properties for pilot classifications.
  Synthesis agreement alone does not establish CDC safety.
- Version matrix: Python 3.9 and 3.14; record baseline local Yosys 0.68+80
  `621d943ac-dirty`, but qualify an immutable clean Yosys build before release;
  pin the chosen SV frontend and independent engine. Test every mapped cell type.
- Targets: 100k mapped flops/1M combinational cells within 60 s and 4 GiB;
  diagnostic caps must retain total counts and explicit truncation. The current
  recursive path enumeration has no such demonstrated scale.
- Release: no missed planted crossing/reset fault; 100% of state inventory
  accounted for as analyzed or UNKNOWN; stable source traces; two repeat runs;
  all disagreements reviewed. Timeout or incomplete enumeration cannot pass.

## Qualification contract

This is a staged plan, not a production qualification claim. No stage is earned
by a green unit suite alone. Keep existing passing behavior and raw diagnostics.
Do not change application RTL/DV, disable assertions, or introduce dummy VIP to
make a pilot pass. A failed pilot is an artifact to retain, not a test to remove.

Named pilot pins (full SHAs, never floating branches):
- Caliptra RTL v2.1.2: `49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e`, generic simulation primitives;
  Adams Bridge v2.0.3: `b77e3d899e828d626cfc2a0d26a6b5704cc121e0` when needed.
- OpenTitan: `7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19`; select the named IP fileset, generic technology,
  and record all FuseSoC flags, parameters, generated files, and their digests.
  The later configuration-blocker evidence at `a78922f14a8cc20c7ee569f322a04626f2ac6127`
  is a separate revision, not interchangeable qualification evidence.

Every release candidate needs an immutable evidence bundle: tool Git SHA and
binary hashes; OS/architecture, Python/compiler/simulator/solver versions;
design and submodule SHAs; top, parameters, defines, ordered files/includes,
constraints, libraries, seeds; input/output hashes; exact argv, raw stdout/stderr,
exit codes, wall time and peak RSS. Repeat twice in clean independent workspaces;
compare canonical findings and explain any nondeterminism. Archive the bundle
with the release and publish a supported/unsupported configuration table.

Review every expected finding and every oracle disagreement. Seed known defects
in separate test fixtures and require their detection; never mutate pilot RTL.
Unknowns and exclusions remain counted and visible. Waivers require a stable
finding/configuration identity, owner, independent reviewer, rationale, evidence
hash/link, expiry, and revalidation on any relevant input change. A waiver is a
review disposition, not a proof. No unreviewed waiver or unexplained oracle
mismatch is allowed in the qualified scope. Outside that scope report UNKNOWN
or a clear unsupported error. A version or dependency change reopens qualification.

Performance numbers below are acceptance targets, not measurements. Measure on
a named Linux x86-64 runner with 8 cores and 16 GiB RAM; record hardware and
median of five runs. No automatic threshold relaxation. macOS arm64 is a second
portability lane, not a substitute for the qualification runner.

## Portfolio priority and real-flow blockers

1. **QD-Lint first:** source/configuration fidelity is prerequisite evidence for
   every downstream analysis. OpenTitan pinmux's conditional `fileset_ip` versus
   `fileset_top` selects different register packages. A local pinned matrix probe
   at `a78922f...` reproduced an omitted-package failure from wrong setup flags;
   it was not an RTL defect. Caliptra's generic/technology primitive roots also
   select different sources. Audit these choices before caching or baselining.
2. **QD-BFM second:** Caliptra's README requires licensed Avery AXI and QVIP AHB
   dependencies in full UVMF flows. A bounded independent AXI adapter is useful,
   but cannot cure simulator/UVM/firmware dependencies or replace their APIs.
3. **QD-CDC, then QD-DFD:** real reset/synchronizer and lifecycle/debug cones are
   available; getting complete elaboration and constraints is the next blocker.
   VCD observations and cell annotations cannot establish safety on their own.
4. **QD-UPF and QD-DFT:** do standards/library/topology inventory now; owner-approved
   power intent and scan-mapped collateral are unverified. Do not invent these
   inputs or mistake lack of collateral for a demonstrated design failure.

Primary source anchors (review pinned source, not just current web documentation):
- [Caliptra dependency and configuration README](https://github.com/chipsalliance/caliptra-rtl/blob/49370266d12cb0c4a8f71b3a0ff7e54ba7d4866e/README.md).
- [OpenTitan pinmux fileset selection](https://github.com/lowRISC/opentitan/blob/a78922f14a8cc20c7ee569f322a04626f2ac6127/hw/ip/pinmux/pinmux_reg.core).
- [OpenTitan lifecycle architecture](https://github.com/lowRISC/opentitan/tree/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19/hw/ip/lc_ctrl/doc).
- [OpenTitan TL DV agent](https://github.com/lowRISC/opentitan/tree/7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19/hw/dv/sv/tl_agent).
