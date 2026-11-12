# CRT read-qualification experiment and release gates

Status: experimental. No production-readiness or timing-closure claim.
Hardware parent: `42ec0b2aefb662842b82203f8f8b7f11eabbcd2f`.
Best measured global build remains `47ffb265f7b9fa3358afb80048b70fa9bf093081`.
Both revisions remain in branch history; neither is replaced or discarded.

## Measured reference builds

These are user-run Quartus 17.0.2 results for revision Groovy, device
5CSEBA6U23I7, unchanged video clock 12.081 ns / 82.77 MHz. Detailed setup
comparisons use Slow 1100mV/100C. No Quartus executable was run by the agent.

| Measurement | 47ffb26 | 42ec0b2 | Qualification experiment |
|---|---:|---:|---|
| Setup slack | -0.089 ns | -0.147 ns | Pending user build |
| Hold slack | +0.245 ns | +0.256 ns | Pending |
| Setup TNS | -0.199 ns | -0.397 ns | Pending |
| LessThan13 output fanout | Not established here | 49 | Pending |
| Final MLAB driver fanout | 3840 | 3840 | Pending |
| ALMs | 32195 | 32566 | Pending |
| Registers | 31199 | 31249 | Pending |
| M10Ks | 553 | 553 | Pending |
| MLAB bits | 491520 | 491520 | Pending |

## Source and reference basis

Target `rtl/CRT/crt_vsize_fixed.sv:read_current_word` selects `group_col` when
`wcol < LINE_PX`, otherwise zero. LINE_PX is 2560 in Groovy.sv. This check
is independent of CE: RAM reads occur on every clock. line_begin bypasses
current addresses with precomputed line addresses on that same edge.
`ra_even_current`, `ra_odd_current`, `packed_ram` and `crt_packed_ram.sv`
retain the same six 3072x40 memories, banking and synchronous read latency.
The comparison uses wcol, not width_q or the requested visible width.

The 42ec0b2 detailed wcol path and READ_CONTROL_EDGE records identify
`emu:emu|crt_vsize_fixed:u_vsize|LessThan13~1` as the shared comparison output,
with fanout 49. Captured consumers include all 30 final drivers for bits 0..4
and five other named local address nodes. Other consumers remain shared.
`rtl/CRT/crt_address_duplication.qsf` already implements final-driver copies
and upstream wa isolation; the baseline fitted audit confirms both outcomes.
Approved receiver `psakhis/Groovy_MiSTer/rtl/vga.v` horizontal/vertical counter,
CE and field logic was inspected, including V_total and interlaced wrapping.
Native sync, transport, audio and compression RTL remain unchanged.

## Selected correction

Append six DUPLICATE_ATOM assignments from the exact LessThan13~1 source to
`crt_read_PART_BANK_bit*` destination groups. Each group selects the five
existing final drivers, not RAM storage. The new copy names are
`crt_read_qual_PART_BANK`. All 36 prior assignments are retained verbatim.
No RTL, register, clock, SDC, project option, memory or pipeline change occurs.
This builds on 42ec0b2 because its wa read-dependency separation is verified.
It does not assert that its global placement is better than 47ffb26.

Plain Tcl validates the 42 expanded assignments. The map preflight checks the
exact comparator node in the new input-edge records and checks five created
final-driver destinations for each bank. The six final groups already exist
in the parent's fitted netlist, but not in its mapped netlist. This dependency
is explicit; assignment ordering, Fitter wildcard interpretation and retained
copies still require the user's fitted audit. The guard stops on Warning 171070.

The summary JSON now includes qualification_drivers and read_control_inputs.
Inspect the actual input source IDs/names/fanouts for each final driver, not
just the count of named nodes. Check that each bank's final-driver qualification
comes from its own retained copy. Original LessThan13 may retain other loads.
No expected post-fit fanout or timing improvement is reported as measured.

## Independent PoC_V trace

Both 47ffb26 and 42ec0b2 have byte-identical Groovy.sv and rtl/vga.v, and no
clock/SDC changes between them. PoC_V is a 16-bit modeline register, initialized
to 240 and written by the modeline-load path in Groovy.sv. Its V port feeds
`vga:V_total = V + VBP + VFP + VS`, with a one-line adjustment for the second
interlaced field. The counter wrap check is `v_cnt >= V_total-1`.
At an enabled horizontal-sync boundary, wrap selects 0/1 according to field;
otherwise the counter advances by 1/2. Reset and soft-reset paths have priority.

The 42ec0b2 routed path launches PoC_V[3]~DUPLICATE and traverses VGA Add1,
Add0 and Add54 carry/sum nodes, LessThan19 comparison, v_cnt[13] next-state
mux logic, then top-level Add17 carry/sum logic. It captures at compiler-created
retimed registers, not source registers named Add17:

| Capture node | Physical capture register | Slack |
|---|---|---:|
| Add17~5_OTERM2885 | Add17~5_NEW_REG2884, FF_X55_Y24_N49 | -0.147 ns |
| Add17~9_OTERM2883 | Add17~9_NEW_REG2882, FF_X55_Y24_N44 | -0.116 ns |

Groovy.fit.rpt explicitly lists both as Retimed Register / Physical Synthesis.
They also exist as retimed registers in 47ffb26. The worst path is eight logic
levels, 6.827 ns cell and 5.080 ns routing delay. Top-level RTL consumes
vga_vcount in next-line `+1+PoC_interlaced` comparisons and multiplication for
frameskip handling (Groovy.sv main flow and S_Blit_Auto_Skip). The reports
trace the physical Add17 capture but do not identify its exact original RTL
register bit after retiming. No exact source-bit mapping is invented here.

This is an unchanged sequential design under changed physical implementation;
the reports do not isolate placement, retiming, packing and routing as separate
causes. The 47ffb26 global top-30 export contains no matching PoC_V launch path,
so a precise before/after delay for those two endpoints is not available there.
No arithmetic correction is justified by that comparison alone. PoC_V RTL is
therefore deferred, with a dedicated crt_poc_v_setup.txt export in the next run.
LZ4 and the other timing paths are not modified.

## Functional evidence

Fresh commands executed with Verilator 5.032 and Icarus 12.0:

```
CRT_READ_BASELINE=42ec0b2aefb662842b82203f8f8b7f11eabbcd2f python3 tests/run_crt_read_address_rtl.py
python3 tests/run_geometry_tests.py
bash tests/run_crt_group_address_rtl.sh
python3 tests/test_crt_group_address.py
python3 tests/check_crt_ram_extraction.py
python3 tests/test_crt_qualification_targets.py
python3 tests/test_crt_duplicate_fit_guard.py
python3 tests/test_crt_pre_flow.py
tclsh tests/test_crt_address_duplication.tcl
```

The common-input test passes 6698817 clocks with zero mismatches at all six
RAM address/enable/data ports, synchronous RAM outputs and registered video/
CE/sync/field signals. It covers -7..+7 geometry, five-pixel group and bank
boundaries, 0/1/2-row advances, wrapping, reset/restart, blanking, field changes,
CE gaps and width limits. New non-vacuity counters require wcol=LINE_PX-1,
wcol=LINE_PX, CE stalls at saturation and next-line bypass after saturation.
Those counts are respectively 5354/871035/712674/4206 for LINE_PX=32 and
1009/222473/84047/550 for LINE_PX=2560. These are simulation counts, not hardware
measurements or exhaustive formal proof. The RTL is also identical to 47ffb26.

The actual native VGA suite passes progressive heights 240/288 and interlaced
480/481, runtime modes, reset and half-line fields using its existing timing
fixtures. Those small-width simulation fixtures are not CRT monitor modelines.
OSD and complete emu elaboration pass. The counter RTL comparison passes 57000
clocks each for MLAB_PARTS=0 and 2 against the earlier divider reference. The
independent model passes three tests over 210000 clocks. Qualification preflight
has three tests, including missing comparator and cross-bank rejection. Existing
RAM extraction assertions were updated from ra_even/odd to the already-present
local_ra_even/odd ports; its three tests then pass without changing RTL.
Fitter-guard and pre-flow tests pass. Standalone RTL lint completes with existing
USE_MLAB parameter-width warnings. Transport/compression files are verified
unchanged and the core elaborates; this is not a new end-to-end UDP/LZ4 test.

## User-run measurement

Use the pushed commit in a fresh worktree. With Quartus 17.0.2 on PATH:

```
CRT_READ_BUILD_DIR="$PWD/../crt-qualification-build" bash tests/run_crt_read_address_quartus.sh
```

The runner requires an unused output directory, executes pre-flow, map, audit,
preflight, guarded fit, assembly, STA, detailed timing export and cmp audit.
It writes map/cmp JSON summaries as well. Return the entire output_files
archive. Required evidence includes:

- Groovy.map/fit/sta.rpt and summaries; complete setup TNS is in the STA report.
- duplicate_fit.log and crt_read_address_compile.log for assignment warnings.
- crt_local_drivers_map/cmp.tsv and .json for copies, inputs and fanout.
- crt_read_address_worst_setup.txt / worst_hold.txt for path identities and delays.
- crt_upstream_wcol_setup.txt, crt_upstream_hb_setup.txt and all six per-bank paths.
- crt_poc_v_setup.txt, crt_lz4_setup.txt and crt_read_address_unconstrained.txt.

Verify all corners in Groovy.sta.rpt, not just a successful tool exit code.
Compare the table above; verify clock/device, four MLAB/two M10K pixel banks,
separate final drivers, comparator input connections and resource limits.
Check LZ4 remains nonnegative (42ec0b2 dedicated report worst +0.744 ns).

## Release acceptance gates

All remain pending until measured and recorded for the release candidate:

- Full clean Quartus 17.0.2 flow at 82.77 MHz; setup and hold >=0, setup TNS=0
  across required corners; no new exceptions used to hide failures.
- Six 3072x40 memories with four MLAB/two M10K storage; total M10Ks <=553,
  unchanged synchronous read and video latency; archive source SHA and reports.
- Audit relevant clock-domain paths and active I/O timing. The 42ec0b2 report
  has zero unconstrained clocks but 3 input ports/13 paths and 48 output
  ports/66 paths unconstrained for setup and hold. Identify active paths and
  resolve missing constraints from actual board/interface requirements before
  release. Unmatched disabled-HDMI filters do not justify ignoring active I/O.
- Re-run simulation and preserve boundary coverage, RAM/video equivalence,
  native sync/field/mode-change results and any accepted lint waivers.
- On the user's actual CRT, record core SHA, MiSTerCast SHA, monitor, connection,
  exact known-working modelines, progressive/interlace modes and signal source.
  Use existing supported modelines; no new monitor limits are specified here.
- Display a labelled grid, edge markers, alternating rows and a moving pattern.
  Check pixel/line placement, cropping, centering, size -7/0/+7 and intermediate
  adjustments, stable sync lock and undisturbed horizontal/vertical timing.
- Verify alternating interlace fields using a field-identifiable pattern;
  distinguish expected interlace flicker from stuck/repeated or displaced fields.
- Exercise supported resolution/refresh changes, geometry changes, stream
  stop/restart, reconnect, reset and cold boot. Record recovery behavior and
  check for stale imagery, shifts, color/pixel errors, loss of sync or underruns.
- Proposed initial endurance gate: two hours per selected progressive and
  interlaced mode, with duration and defects logged. Repeat transport/compression,
  audio and controller acceptance on hardware; simulation does not replace it.

No hardware gate has been performed by the agent. MISTER_DEBUG_NOHDMI=1 remains
an experimental CRT-only configuration; this iteration does not establish HDMI
readiness or convert this branch into a production release.
