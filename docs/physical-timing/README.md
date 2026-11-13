# Gated physical timing experiments

> This document describes the preserved Quartus 17 R0 investigation. The
> Quartus 25.1 compatibility port, Q25 hardware profile and local build
> invocation are in [QUARTUS25.md](QUARTUS25.md).

This implementation adds R0 diagnostics, fixed generated inputs, reviewed
assignment-only overlays & complete endpoint comparisons. Hardware remains
byte-identical to `c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17` across the 92
recorded RTL/IP/project/constraint files. Global retiming, seed 1, the device,
clock requirements, corrected HPS assignments & inactive HDMI remain unchanged.

R0 is executable. A1 & D1 are implemented as **gated experiment types**, with
unapproved recipes that the runner rejects. No physical target or legal site
has been invented. The existing textual reports don't establish the original
position-to-retimed correspondence or the full selector footprint. Those
require the new user-run R0 exports. There are no approved optimization
assignments in this source revision & no measured timing improvement.

The eight historical RTL variants remain available for history. All failed the
global comparison; this runner accepts only R0, A1 & D1. It never reapplies a
historical arithmetic/selector patch or combines physical factors.

## Reference basis

- Hardware: `c8d4b38`, `rtl/CRT/crt_vsize_fixed.sv` position/position_next/
  advance_rows, all six local_ra read ports & control[0..4]; `Groovy.sv`
  PoC_lz4_delta_FB/index & decode_pixel; `sys/sys_top.v` dv_hs1 capture.
- Existing harness: `d071948`, `tests/restart/prepare_build.py`, experiments.py,
  package_reports.py, finalize_build.py; the accepted mapped-driver resolver
  & `tests/report_timing_closure.tcl` eight-corner flow.
- Physical evidence: supplied baseline `corner_02/negative_setup_paths.txt`
  row path -0.161 ns, 7.341 ns cell, 4.226 ns routing; delta -0.148 ns;
  `corner_01` wcol routing 8.321 ns; baseline fitter/map reports & driver TSVs.
- [Quartus 17 project assignment discovery](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_project_ver_6.0_cmd_get_all_assignment_names.htm)
  & [assignment metadata](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_project_ver_6.0_cmd_get_assignment_name_info.htm).
  A TCL_OK unsupported-edition message is recorded as unavailable.
- [Quartus 17 name inventory](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_project_ver_6.0_cmd_get_names.htm),
  [name information](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_project_ver_6.0_cmd_get_name_info.htm),
  [STA node locations/edges](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sta_ver_1.0_cmd_get_node_info.htm),
  [edge endpoints](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sta_ver_1.0_cmd_get_edge_info.htm)
  & [report cells](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_report_ver_2.1_cmd_get_report_panel_row.htm).
  Atom port queries extend the API already used by this project's measured
  17.0.2 driver audit; installed long-help is exported too.

Later-version preservation documentation does not establish 17.0.2 Lite
register-level support. The runner exports installed metadata; a reviewed
source/physical correspondence & scope are required before A1. No LogicLock,
HyperFlex, Pro-only retiming API, ECO or netlist-modification command is used.

## Control identity & source guards

`tests/physical/hardware_baseline.json` inventories the recorded compilation
inputs from c8d4b38. Preparation requires clean committed source, checks those
hashes, rejects existing/nested build directories & excludes old databases.
It uses the original preparation code rather than describing a dirty working
tree as baseline. New reporter/test files aren't hardware modifications.

All supplied independent builds used the exact 27-byte generated input:

```verilog
`define BUILD_DATE "261112"
```

There is **no trailing newline**. The runner runs the original pre-flow script,
then restores those bytes & records their hash. Actual preparation, freeze &
host timestamps are separate UTC provenance fields. It verifies the bytes
again before mapping, before fitting & after STA. The system clock is never
changed. Changing this constant for release creates another source identity
that requires physical verification.

Prepared, pre-map & pre-fit source manifests remain separate. The generated
physical overlay & freshly resolved duplication QSF are explicit compilation
inputs in the phase manifests. Raw source-expanded assignment calls retain
their ordering. Before mapping, R0 must match its prepared calls. Candidates
must match the equivalent R0 pre-map/pre-fit calls after removing exactly their
reviewed additional assignments. Fresh DUPLICATE_ATOM names have separate
mandatory resolver & fitted-separation audits; they are not mistaken for a
new optimization policy. Vendor defaults still require the fitter reports.
Quartus map may serialize an approved sourced call into Groovy.qsf as well.
Repeated exact approved calls are counted & permitted; other calls/order
must still match R0. The measured control itself expanded from 92 to 330 QSF
lines during mapping, so phase records must not be substituted for each other.

## Run R0 with Quartus 17.0.2

All Quartus commands below are **user-run only**. Use a fresh source worktree
at the implementation commit, then a new build directory. Set QUARTUS_17_BIN
to the actual installed 17.0.2 Lite `quartus/bin` directory; it is required &
has no PATH-based fallback. The runner checks the version/edition of all six
selected executables. Quartus 25.1 fails preflight before synthesis.

```bash
git fetch origin refs/heads/work/physical-timing-r0:refs/remotes/origin/work/physical-timing-r0
git worktree add --detach ../Groovy-physical-source origin/work/physical-timing-r0
cd ../Groovy-physical-source

export QUARTUS_17_BIN=/path/to/installed/17.0/quartus/bin
CRT_READ_BUILD_DIR="$PWD/../Groovy-R0" bash tests/run_physical_timing_quartus.sh R0
```

The installation path is machine-specific. Project/revision is exactly
`Groovy -c Groovy`. The runner executes map, source resolution, guarded fit,
assembly, STA, eight-corner exports, fitted diagnostics & structural audits.
It never fits a copied database. Seed, global retiming & all timing requirements
remain controlled by the original project.

Exit 4 means compilation completed but the timing gate failed. That is expected
for the measured R0 baseline. Check `build_state.json`: a synthesis/preflight
failure has no timing result. Exit 0 after a physical build means the exported
timing checks passed; it does not qualify coverage or authorize CRT testing.
Both successful & failed builds produce `Groovy-R0-reports.tar.gz`.

A preparation-only check launches no Quartus executable:

```bash
CRT_READ_BUILD_DIR="$PWD/../Groovy-R0-prepared" bash tests/run_physical_timing_quartus.sh R0 --prepare-only
```

Its build_state records `prepared-only`, compilation incomplete & no timing
result. It is not an FPGA build. Unknown or ungated experiments are rejected.

## R0 return package

Return the complete lossless archive. Keep the fitted database locally for
follow-up inspection, but don't copy it into another fit.

| File under output_files/closure_diagnostics | Observations & explicit limits |
|---|---|
| assignment_support.txt, assignment_capabilities.tsv | Installed name/scope metadata, types/values when supplied by the tool; individual-register applicability still needs review |
| node_inventory.tsv | Full pre-synthesis, post-synthesis & post-fit names, creator, type & source location; IDs aren't cross-build identities |
| report_panels_map.tsv, report_panels_cmp.tsv | Native retiming, packing, mux, physical-synthesis, routing & fitter-setting report cells |
| retiming_correspondence.tsv | Same-name or generated physical registers with actual report references; unresolved original registers stay blank |
| atom_ports_map.tsv, atom_ports_cmp.tsv | Actual input/output port bits & connected nodes, including the packed delay memory |
| crt_logical_read_bits.tsv | Every bank/bit 0..11, observed physical ports or high-bit fanout; missing source correspondence is explicit |
| fanout_locations.tsv, fanout_seeds.tsv | Complete selected-root fanout through combinational logic to state, per-edge locations/types & expected fanout |
| driver_footprints.tsv | Per-driver coordinate bounds & counts of located/unlocated loads; bounds aren't routed wire length |
| metadata_bit_map.tsv | Separate actual packed-memory input/output bit edges & packing associations; no assumed DATAA-to-tap pairing |
| routing_footprint.txt, critical_path_metrics.tsv | Actual route/cell delays & coordinates plus native routing/congestion cells; absent hotspot data remains pending |
| video_requirements.json | Observed same-video-clock paths in every corner retain 12.081 ns & 0.200 ns setup uncertainty |
| coverage_disposition.tsv | Every observed no_clock/port finding & ignored-constraint review item; no false paths or guessed external delays |
| diagnostic_status.json | Completeness, unresolved mappings & pending gates; empty reports don't qualify coverage |
| evidence_manifest.json | Exact source/configuration identity & SHA-256 inventory of the exported evidence |

MLAB physical address ports expose only five low bits. High logical bits also
feed output-selection logic. The collector follows actual shared output ports
observed on RAM inputs into other banks' mapped mux inputs; it doesn't assign
bank ownership from a local_ra RTL prefix. The supplied baseline audit already
shows upper bit-9 drivers with fanouts 1224/1223; 1181 belongs to row-enable.
Full load locations remain required before C1/D1 placement.

The packed dv_hs1 memory includes CRT metadata & other sync/YC chains. Port
bit 7 isn't automatically HS. When native retiming origin fields are empty,
use RTL Viewer/Technology Map Viewer cross-probing of the original position
state, adjacent arithmetic & physical captures. Export the actual connectivity
or a reviewed native view into the diagnostic directory; don't strip NEW_REG
suffixes to manufacture correspondence. Add legal-site exports there too.
Reassemble/seal after adding those review exports:

```bash
python3 tests/physical/diagnostics.py ../Groovy-R0/output_files
python3 tests/restart/package_reports.py ../Groovy-R0/output_files ../Groovy-R0-complete-reports.tar.gz
python3 tests/restart/package_reports.py ../Groovy-R0-complete-reports.tar.gz --verify
```

For offline analysis without modifying a measured reference, pass
`--destination /new/diagnostic/directory` to diagnostics.py. Missing Quartus
exports remain pending. No Quartus process is started by that Python command.

## A1 & D1 evidence gates

The supplied `candidates/*.pending.json` files are intentionally rejected.
After R0 is returned, prepare ONE reviewed recipe from its actual exports.
The schema is enforced by `tests/physical/overlays.py`; synthetic examples in
unit tests are explicitly fixtures, never proposed hardware nodes/sites.

Every recipe needs: experiment, reviewed_by, rationale, the exact R0 evidence
manifest hash, all required mechanism-evidence file references/explanations,
observed original/fitted correspondence for every assignment & one assignment
factor. All referenced evidence must retain its sealed hash.

- A1 accepts one supported movement-control name across an exact CRT position
  register group: PHYSICAL_SYNTHESIS_REGISTER_RETIMING/OFF or the broader
  ADV_NETLIST_OPT_ALLOWED/NEVER_ALLOW. It requires installed instance metadata,
  the accepted value, reviewed register scope & observed original/fitted names.
  It never turns global retiming off or rewrites row arithmetic.
- D1 accepts only location assignments on the observed original delta cone.
  It requires a complete exported fanout graph, reviewed refill/decode paths
  & sealed native evidence for the exact legal site spelling. No arbitrary
  coordinates, selector groups, keep wires or new registers are generated.

These recipe paths refer to reviewed files prepared after the R0 inspection:

```bash
CRT_READ_BUILD_DIR="$PWD/../Groovy-A1" bash tests/run_physical_timing_quartus.sh A1 \
  --overlay ../reviewed-A1.json --evidence ../Groovy-R0/output_files/closure_diagnostics
CRT_READ_BUILD_DIR="$PWD/../Groovy-D1" bash tests/run_physical_timing_quartus.sh D1 \
  --overlay ../reviewed-D1.json --evidence ../Groovy-R0/output_files/closure_diagnostics
```

Each starts from unchanged hardware; they aren't stacked. Source/configuration
drift, unknown names, absent exact target matches or ignored required options
make the experiment invalid. Post-fit matching is necessary but doesn't prove
the intended boundary moved or routing improved. Keep that result pending
until graph/cycle/initialization review confirms the mechanism.

If A1/D1 can't pass their gates, C1 needs the full twelve-bit bank footprint;
V1 needs Add17's original capture; S1 needs packed bit/tap correspondence;
M1 needs locally supported instance scope & mapped mux evidence. None is
silently substituted or implemented as an extra candidate in this batch.

## Complete comparisons & acceptance

Every corner now retains complete compact endpoint distributions for setup,
hold, recovery & removal, alongside all negative endpoint/path inventories.
The validator rejects disagreements or missing members. Launch & capture
reports cover CRT, VGA/root Add17, packed metadata, delta refill/decode & LZ4.
Positive full-routing reports remain bounded; pulse failure evidence remains
complete. Lossless packaging uses <=200 MiB members & 8 MiB verbose-positive
parts, preserving every byte with original/part hashes.

Restore the original supplied archive into a new directory if needed:

```bash
python3 tests/restart/package_reports.py ../build-baseline-reports.tar.gz --restore ../Groovy-original-baseline
python3 tests/physical/compare.py ../Groovy-R0/output_files ../Groovy-A1/output_files \
  --published-control ../Groovy-original-baseline/output_files \
  --output ../Groovy-A1/output_files/comparison_to_R0.json
```

Repeat for D1. The comparator emits a summary JSON plus a complete endpoint
slack-difference TSV. It compares per-corner WNS/TNS/counts, endpoint identities,
new failure families, clock skew, cell/routing delays, fanout, placement & raw
fitter resources. The original published baseline remains an additional gate,
so a regressing new control can't hide a worse candidate. Historical archives
can use `--timing-only`; missing physical evidence never becomes acceptance.

Retain only a demonstrated mechanism with no worse required corner, at least
one targeted failing path improved, no new failing family, passing hold/
recovery/removal/pulse checks & unchanged source/resource/cycle architecture.
A rank change alone is not rejection. A cell-delay gain lost to routing is
rejection. Ignored targets are invalid experiments. Changes that work alone
need a fresh combined build before integration.

Post-fit mechanism review is tied to the candidate provenance hash. Its
`mechanism_review.json` records reviewed_by, mechanism_verified,
functional_cycles_verified, targeted_path_improved & a dictionary of actual
evidence paths/SHA-256 values. No such approval is supplied before measurement.
Repackage after comparisons or review so those files are included.

## Independent validation & remaining gates

```bash
python3 tests/run_timing_candidate_tests.py
python3 -m unittest discover -s tests -p test_physical_experiments.py -v
bash -n tests/run_physical_timing_quartus.sh
```

Requirements: Icarus, Verilator, g++, Tcl, Python 3 & z3-solver. The language
gate follows actual `.v`/`.sv` modes, retains the rejected sized-cast fixture
& uses declared IP/VHDL models. CRT comparisons check all six bank ports/data,
registered video/sync, geometry -7..+7, line/field boundaries, stalls, reset &
runtime changes. The flat delta wrapper tests the actual selector, byte adds
& decode task through refill/index wrap/stalls/reset/all modes. It doesn't
exhaust the entire DDR FSM. Tcl models test control flow & completeness;
they don't establish acceptance by installed Quartus.

The existing 2470 no_clock findings & 3 input/47 output-direction findings
remain model/interface/CDC review work. Coverage status stays unqualified
until those dispositions are supported. No constraint is relaxed or invented.
Eight-corner setup/hold closure, resource/driver checks, interface requirements
& real CRT validation are separate acceptance stages. No CRT test is authorized
by this source-only delivery.
