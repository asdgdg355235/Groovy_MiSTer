# Localized CRT RAM read-driver experiment

## Source & baseline

Base: `f930d43ee3e206859dafe7a6c287113a7a957585`.
RTL candidate: `4b13c81d70cf1c21d6ded07f16d1cf0c6f117eaf`.
The inherited six pixel memories are four MLAB & two M10K, each 3072x40;
this experiment preserves that mapping rather than converting all six to MLAB.

The recovered Experiment C reports were produced with Quartus Prime Lite
17.0.2 Build 602, revision `Groovy`, Cyclone V `5CSEBA6U23I7`, Slow 1100mV
100C corner, 12.081 ns video-clock domain. Their source tree matches the
published baseline. Report checksums match the saved archive. These are
historical physical measurements, not a fresh baseline compilation in this run.

| Measurement | Historical baseline | Localized candidate |
|---|---:|---:|
| Setup slack | -0.132 ns | Pending |
| Hold slack | +0.263 ns | Pending |
| Setup TNS | -0.267 ns | Pending |
| Worst read-address fanout | 15400 | Pending |
| Worst path cell/routing delay | 2.834 / 8.657 ns | Pending |
| Worst path logic levels | 6 | Pending |
| ALMs / fitted registers | 32947 / 31418 | Pending |
| M10K / MLAB bits | 553 / 491520 | Pending |

## Logic & reference basis

`rtl/CRT/crt_vsize_fixed.sv` retains line-start & current addresses separately.
Its generate block now contains a distinct final `line_begin` mux output for
each even/odd RAM instance. Only those outputs have `keep` attributes.
The expression on each RAM port equals the published shared address on the
same edge. No register, reset, clock enable or pixel-storage statement changes.
`rtl/CRT/crt_packed_ram.sv` remains byte-identical to the baseline.

Inspected target symbols include `line_begin`, `first_output`, `next_aslot`,
`slot_now`, `pair_ready`, `ra_even_line`, `ra_odd_current`, `read_lane` &
`packed_ram`; `Groovy.sv` retains `MLAB_PARTS=2`, native CE & field wiring.
The approved `psakhis/Groovy_MiSTer/rtl/vga.v` reference confirms CE-qualified
native counters & field-dependent half-line sync equations. No native timing,
protocol, audio, trigger, controller or LZ4 logic is modified.

Quartus documents `keep` as retaining combinational nodes through synthesis.
It does not prove physical localization. `tests/report_crt_local_drivers.tcl`
reads both `map` & `cmp` atom netlists, dumps driver fanout & RAM address
source IDs. The timing script exports each RAM hierarchy separately.
The completed map audit found 19 atoms with local address names, but each
of read bits 0..4 is still driven by one source shared across all six RAMs.
Each source has fanout 15440. `keep` alone has therefore failed localization.
Fitted results are still pending. The next candidate will test bank-specific
DUPLICATE_ATOM assignments, retaining all RTL cycles & memory dimensions.

## Functional checks

The unchanged source passed the existing 6698817-clock RTL comparison before
editing. The candidate passed the same matrix against published `f930d43`,
with additional capture-edge comparisons of the actual address, enable & data
ports of all six RAMs, including blanking & CE gaps. Existing synchronous
RAM data & registered RGB/CE/sync/field comparisons retain exact cycle alignment.
The matrix covers all -7..+7 settings, partial five-pixel groups, widths through
2560, 0/1/2 source-row advances, wrap, progressive/interlaced half-line sync,
resets, runtime geometry changes & inactive bypass. This is simulation coverage,
not exhaustive formal equivalence or a hardware test.

```sh
python3 tests/run_crt_read_address_rtl.py
python3 tests/test_crt_group_address.py
bash tests/run_crt_group_address_rtl.sh
python3 tests/run_geometry_tests.py
bash tests/run_crt_read_address_quartus.sh
```

Counter RTL comparisons pass 57000 clocks each for MLAB_PARTS 0 & 2.
The independent counter model passes 210000 modeled clocks. Geometry,
240p/480i, odd-height fields, OSD & complete emu elaboration pass.
Yosys retains six 3072x40 synchronous pixel memories with four MLAB & two
M10K attributes. This inference check does not establish Quartus mapping.

## Physical build & LZ4 gate

Candidate A completed synthesis in a new directory without earlier DBs. Its
Fitter process stopped before producing completed fit or timing reports.
Existing QSF/SDCs, PLLs, seed & clock target were unchanged.
The previous three state[0]-to-lz4_compressed_bytes endpoints at -0.004 ns
have not been modified. Reassess them only after candidate placement/routing.
No LZ4 improvement or new timing closure is claimed before new reports exist.

## Candidate B: targeted atom duplication

This candidate adds `rtl/CRT/crt_address_duplication.qsf`, sourced at the end
of `Groovy.qsf`. It expands to 31 assignments: five final address bits for
six RAM hierarchies, plus the confirmed `wa[3]` input to read mux bit 3.
Only that upstream connection was traced in the saved fan-in audit; no
upstream duplication is requested for the other four bits.

The prepared template's `*|u_vsize|` pattern would not match the observed
entity-qualified `|crt_vsize_fixed:u_vsize|` hierarchy. The applied patterns
include the observed entity names, `~*` synthesized suffixes and single-character
wildcards for array brackets. RAM destination patterns include
`crt_packed_ram:packed_ram[part].even_ram` / `odd_ram`. They select distinct
fanout groups; they do not create pixel memories.

Reference basis: Candidate A's `crt_local_drivers_map.tsv` shows bits 0..4
as `emu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[bit]~bit`,
shared by all six RAMs with fanout 15440. Its `local_fanins.log` confirms
`wa[3]~3` feeding DATAA of read mux bit 3. Quartus 17.0.2's installed
`libdb_acf.so` includes `DUPLICATE_ATOM`, and the shipped help index maps it
to `logicops/logicops/def_duplicate_atom.htm`. The vendor setting reference
specifies a string duplicate-node name, `-from` source, `-to` destination and
Fitter wildcard support:
https://docs.altera.com/r/docs/683296/26.3/quartus-prime-pro-edition-settings-file-reference-manual/duplicate_atom
That current manual supports the syntax; it does not prove acceptance or
ordering of these particular assignments in 17.0.2.

No Quartus executable was run for Candidate B. Its RTL, RAM helper, SDCs,
clock target, device and other project options are unchanged from Candidate A.
LZ4 RTL is unchanged. The atom reporter now includes `crt_read_` duplicate
names even if their fanout falls below 1000; TimeQuest also exports LZ4
capture endpoints separately. These reporting scripts require local Quartus
verification, including the endpoint filters.

`tests/test_crt_address_duplication.tcl` runs in ordinary Tcl, expands all 31
assignments, checks unique names, matches observed source naming and checks
six disjoint destination hierarchies. This validates Tcl expansion and pattern
intent, not Quartus's interpretation of Fitter wildcards. The optimizer can
rename nodes, ignore assignments, or process upstream/final duplication in an
unexpected order. Read assignment warnings and compare actual map/cmp source
IDs before claiming successful duplication. Post-map sharing is not decisive
for a Fitter assignment: the post-fit `cmp` audit determines the final drivers.

## User-run Quartus 17.0.2 verification

Use a fresh worktree at the pushed commit to avoid reusing a compilation DB.
Project and revision are both `Groovy`. With Quartus 17.0.2 on PATH, run:

```bash
set -euo pipefail
mkdir -p output_files
quartus_sh --version | tee output_files/crt_read_address_tool_version.txt
quartus_sh -t sys/build_id.tcl pre_flow Groovy Groovy 2>&1 | tee output_files/crt_read_address_pre_flow.log
quartus_map Groovy -c Groovy 2>&1 | tee output_files/duplicate_map.log
quartus_cdb -t tests/report_crt_local_drivers.tcl map 2>&1 | tee output_files/crt_local_drivers_map.log
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_map.tsv > output_files/crt_local_drivers_map.json
# Review warnings here, then continue through fitting to evaluate Fitter assignments.
rg -ni 'duplicate|ignored|unmatched|not found|Warning|Error' output_files/duplicate_map.log || true
python3 tests/run_crt_duplicate_fit.py
quartus_cdb -t tests/report_crt_local_drivers.tcl cmp 2>&1 | tee output_files/crt_local_drivers_cmp.log
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_cmp.tsv > output_files/crt_local_drivers_cmp.json
quartus_asm Groovy -c Groovy 2>&1 | tee output_files/duplicate_asm.log
quartus_sta Groovy -c Groovy 2>&1 | tee output_files/duplicate_sta.log
quartus_sta -t tests/report_crt_read_address_timing.tcl 2>&1 | tee output_files/crt_read_address_sta.log
rg -ni 'duplicate|ignored|unmatched|not found|Warning|Error' output_files/duplicate_{map,fit,sta}.log > output_files/duplicate_warnings.txt || true
tar -czf crt-duplicate-reports.tar.gz output_files
```

Compare worst setup/hold and setup TNS with -0.132/+0.263/-0.267 ns.
Baseline worst path cell/routing delay was 2.834/8.657 ns, six logic levels;
address fanout was approximately 15400. Baseline fitted ALMs/registers were
32947/31418, M10Ks 553, MLAB storage 491520 bits. Confirm four MLAB and two
M10K 3072x40 banks, unchanged 12.081 ns video clock and the Slow 1100mV/100C
corner for comparisons. Retain all corner summaries as well.

In `crt_local_drivers_cmp.json`, inspect `low_read_address_bits`: each RAM's
source IDs should be distinct from the other banks for bits 0..4, with lower
fanout. In the TSV, check the duplicate names and their connected RAM address
pins. Multiple RTL names or a `LOCAL_NODE_COUNT` alone do not prove separation.
Confirm the new path delay/routing and setup TNS in routed TimeQuest reports;
driver duplication alone does not establish timing improvement.

Return `crt-duplicate-reports.tar.gz`, especially `Groovy.map.rpt`,
`Groovy.fit.rpt`, `Groovy.sta.rpt`, their summaries, the map/cmp TSV and JSON
audits, `duplicate_warnings.txt`, `crt_read_address_worst_setup.txt`,
`crt_read_address_worst_hold.txt`, `crt_read_address_ce_to_ram.txt`, all six
`crt_local_bank_*_setup.txt`, `crt_lz4_setup.txt` and the unconstrained report.
The LZ4 export tests whether the three historical -0.004 ns endpoints remain;
any transport correction must follow this measurement as a separate experiment.

## Candidate B non-Quartus validation

Executed after applying the assignments:

- `tclsh tests/test_crt_address_duplication.tcl`: 31 unique assignments pass
  expansion, observed-name matching and disjoint bank-target checks.
- `python3 tests/run_crt_read_address_rtl.py`: 6698817 simulated clocks pass
  against published `f930d43`, including all six RAM ports, synchronous data
  and registered video/control at corresponding cycles.
- `python3 tests/test_crt_group_address.py`: three tests pass, 210000 modeled clocks.
- `bash tests/run_crt_group_address_rtl.sh`: 57000 clocks pass for each of
  MLAB_PARTS=0 and MLAB_PARTS=2.
- `python3 tests/run_geometry_tests.py`: geometry, native progressive/interlace,
  OSD and complete emu elaboration checks pass.
- Plain Tcl `info complete` checks pass for both report scripts; `bash -n`
  passes for the existing fresh-build runner. `git diff --check` passes.

No `.sv`, `.v`, `.sdc`, device, speed grade or clock definition changed in B.
The expected lack of RTL behavior changes follows from that source comparison;
simulation is coverage, not exhaustive formal proof. Quartus acceptance,
assignment ordering, driver retention, fit/resources and timing remain untested.
The last verified physical results remain -0.132 ns setup and +0.263 ns hold.

## Correction after the user-run missing-source loop

The user-run 17.0.2 Fitter repeatedly emitted Warning 171070 for the source
patterns in Candidate B. The uploaded truncated log contains 548 repetitions;
the original log reached approximately 140 MiB according to the user. This
run is not evidence for driver retention, resource usage or timing improvement.

The supplied `crt_local_drivers_map.tsv` confirms that all five intended source
nodes exist, exactly as below, each with fanout 15440:

```
emu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[0]~0
emu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[1]~1
emu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[2]~2
emu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[3]~3
emu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[4]~4
```

The correction replaces patterned `-from` values with these exact names, and
uses literal entity/array names in destination prefixes with only a trailing
`*`. The upstream assignment uses exact `wa[3]~3` and exact read mux bit 3.
Tcl braces and `format` preserve the brackets as characters. No RTL, SDC,
project device or RAM mapping is changed. Quartus acceptance still requires a
local Fitter run; the prior plain Tcl glob test did not validate that behavior.

Reference basis: the uploaded map TSV and Fitter log, target
`rtl/CRT/crt_address_duplication.qsf`, `crt_vsize_fixed.sv:packed_ram`,
`crt_packed_ram.sv` and existing map/cmp reporter; approved receiver
`psakhis/Groovy_MiSTer/rtl/vga.v:ce_pix` counter/field update block remains
untouched. Altera's older Quartus handbook documents exact source nodes with
wildcard destination hierarchies for this assignment:
https://cdrdv2-public.intel.com/653790/quartusii_handbook_10_1_0.pdf
Its example supports the exact-source/hierarchy-destination approach; it does
not establish that these assignments have been accepted by this build.

`check_crt_duplicate_targets.py` sources the actual QSF in ordinary Tcl, then
checks all expanded assignments against the saved TSV. All 31 pass on the
user's audit. For each of the 30 final mux assignments, it verifies the exact
source and every selected low-bit read-address connection within the intended
bank. Each MLAB bank has 3840 RAM atoms; each M10K bank has 40. The upstream
assignment's node existence passes; its direct edge was established by the
previous fan-in audit and is not re-proved by this address-only TSV.

The fresh-build runner now executes map, map audit, preflight, guarded fit,
assembly and STA as explicit stages. The guarded fitter stops its process
group on the first Warning 171070 and returns failure. It does not suppress
warnings or claim timing success. It preserves ordinary process exit codes.
Use this runner for the next local build rather than the older unguarded
`quartus_fit` command:

```bash
export PATH="$HOME/intelFPGA_lite/17.0/quartus/bin:$PATH"
bash tests/run_crt_read_address_quartus.sh
```

The runner creates a new timestamped directory beside the checkout. Return
its `output_files` reports. If it stops, return `duplicate_fit.log` and
`crt_local_drivers_map.tsv` from that directory before attempting more fits.
If it completes, also return the cmp TSV, setup/hold, six per-bank paths,
LZ4, unconstrained report and `Groovy.map/fit/sta.rpt` plus summaries.

Validation executed for this correction: all 31 assignments against the
uploaded TSV; two subprocess tests of the fitter guard using Python stand-ins
(one repeated missing-source loop, one ordinary nonzero exit); three independent
counter model tests over 210000 clocks; Tcl assignment checks, Python syntax,
Bash syntax and `git diff --check`. No Quartus executable was invoked. No RTL
simulation was rerun because simulation tools are absent in the refreshed
workspace; the earlier 6698817-clock result belongs to the unchanged RTL from
the preceding experiment. It is not a new simulation result for this turn.

The M9K parameter belongs to `jtframe_hsize`'s inferred horizontal line buffer.
The uploaded map report emits Warning 287001 and states it uses available
memory blocks. Its RAM summary lists that buffer as AUTO; the geometry scaler
still has four MLAB and two M10K 3072x40 memories. No M9K-related change is
included in this correction. Last verified physical slack remains
-0.132 ns setup / +0.263 ns hold; LZ4 RTL remains unchanged.

## Clean-worktree build-ID correction

The user-run `crt-duplicate-972d027-reports.tar.gz` stops in Analysis &
Synthesis with Error 10054 at `Groovy.sv:211`: `build_id.v` cannot be opened.
The following undefined `BUILD_DATE` warning and ignored `emu` entity are
consequences of that missing generated include. No fitter or TimeQuest result
was produced by this run.

Diagnosis: changing the runner from `quartus_sh --flow compile` to individual
`quartus_map` / `quartus_fit` stages omitted the project's pre-flow callback.
`sys/sys.tcl` assigns `quartus_sh:sys/build_id.tcl` to PRE_FLOW_SCRIPT_FILE.
`build_id.v` is ignored by Git and therefore absent in the fresh worktree.
The old checkout could contain it from an earlier full-flow build.

Reference basis: target `Groovy.sv` include and `CONF_STR`, `.gitignore`,
`sys/sys.tcl:PRE_FLOW_SCRIPT_FILE` and `sys/build_id.tcl:generateBuildID_Verilog`
plus `generateCDF`; approved `psakhis/Groovy_MiSTer` uses the same callback
and pre-flow assignment in `sys/build_id.tcl` and `sys/sys.tcl`.

Correction: before mapping, the isolated runner explicitly executes
`quartus_sh -t sys/build_id.tcl pre_flow Groovy Groovy`, passing the callback's
stage/project/revision argument layout. It checks that both `build_id.v` and
`jtag.cdf` were generated and retains `crt_read_address_pre_flow.log`.
The existing callback, RTL, duplication assignments, memory architecture,
SDCs and Quartus options are unchanged.

Validation: `python3 tests/test_crt_pre_flow.py` runs the real callback with
plain Tcl project-API stand-ins in an empty temporary directory. It checks
the current BUILD_DATE macro, device/revision/path in the generated CDF and
that repeating the callback preserves the existing identical build-ID file.
The two fitter-guard tests, 31-assignment Tcl checks, Bash syntax and diff
checks also pass. No Quartus executable or RTL simulation was run for this
runner-only correction. Successful callback testing does not establish a
successful Quartus build or timing closure.

Use the fresh-build runner from the corrected commit, with a new output
directory. Return the output_files reports, including the pre-flow log if a
failure occurs. The last verified physical slack remains -0.132 ns setup and
+0.263 ns hold. This failed synthesis supplies no new timing measurement.
