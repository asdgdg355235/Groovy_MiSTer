# Integrated CRT timing candidate

This revision is a source candidate for the next user-run Quartus build. No
Quartus executable was run during its preparation. The last measured build is
still a145b92, with setup -0.449 ns, hold +0.247 ns & setup TNS -2.734 ns at its
reported corner. Production timing & CRT hardware acceptance remain pending.

The project/revision is `Groovy` / `Groovy`, from `Groovy.qpf`. The device remains
`5CSEBA6U23I7`. PLL source files, SDC periods, speed grade, seed, physical synthesis
options & output pipeline are unchanged. The reported video-clock requirement
remains 12.081 ns, approximately 82.77 MHz. Multicorner analysis is now ON.

**Reference basis**

- `asdgdg355235/Groovy_MiSTer`, commits 47ffb26, 42ec0b2 & a145b92:
  `rtl/CRT/crt_vsize_fixed.sv`, `crt_packed_ram.sv`,
  `crt_address_duplication.qsf`, `rtl/lz4.v`, `rtl/vga.v`, `Groovy.sv`,
  `sys/sys_top.v`, `sys/sys_top.sdc` & existing tests/report scripts.
- `psakhis/Groovy_MiSTer`, `rtl/lz4.v`: emitting-state counter updates,
  reset/run priority, partial final words & eight independent delta additions.
  `rtl/vga.v`: `V_total`, vertical terminal comparison & interlace adjustment.
  The inspected reference VGA blob is
  `c8f7f9a3cb2825a980dbe273f67b7bb4452c43a5`, also present in 47ffb26.
- The supplied 47ffb26, 42ec0b2 & a145b92 report archives: complete map/fit/STA
  reports, detailed paths & map/fitted atom audits. These supply the physical
  measurements below; source structure alone supplies no fitted timing result.
- Quartus 17.0 API documentation for
  [operating conditions](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sta_ver_1.0_cmd_get_available_operating_conditions.htm),
  [unlimited path queries](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sta_ver_1.0_cmd_get_timing_paths.htm),
  [pulse checks](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sta_ver_1.0_cmd_report_min_pulse_width.htm),
  [constraint checks](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sta_ver_1.0_cmd_check_timing.htm)
  & [clock transfers](https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sta_ver_1.0_cmd_report_clock_transfers.htm).

**Measured revisions**

| Metric | 47ffb26 | 42ec0b2 | a145b92 |
|---|---:|---:|---:|
| Setup slack, ns | -0.089 | -0.147 | -0.449 |
| Hold slack, ns | +0.245 | +0.256 | +0.247 |
| Setup TNS, ns | -0.199 | -0.397 | -2.734 |
| ALMs | 32,195 | 32,566 | 32,467 |
| Registers | 31,199 | 31,249 | 31,239 |
| M10Ks | 553 | 553 | 553 |
| MLAB bits | 491,520 | 491,520 | 491,520 |
| Final driver copies per bit 0..4 | 6 | 6 | 6 |

The CRT/VGA/LZ4 RTL is identical across those three measured revisions.
42ec0b2 changes the six upstream `wa[3]` duplication targets; a145b92 adds six
qualification copies. Those revisions also change tests & documentation. Their
physical reports show different placement, routing & critical-path ordering;
they don't demonstrate a new arithmetic RTL defect caused by either assignment.
47ffb26 remains the measured comparison baseline, retained in Git history.

The 47ffb26 worst CRT path has 6 logic levels, 3.297 ns cell delay & 8.321 ns
routing delay. Its launch/qualification is around X42/Y25, final bank-0 odd
driver X53/Y22 & capture X48/Y54. In a145b92 the worst endpoint is in bank-1 odd:
7 logic levels, 2.653 ns cell delay & 9.328 ns routing delay. Launch is X45/Y20,
qualification copy X45/Y33, final driver X45/Y33, accessed MLAB X25/Y45, mux
stages X56/Y30 & capture X50/Y45. Reducing one comparator's fanout didn't remove
this spread or the memory's own high-fanout address/read-mux routing. No placement
region is imposed without a complete device-floorplan analysis.

**Source corrections**

| Path family | Source correction | Physical confirmation required |
|---|---|---|
| wcol[14]/[15] to MLAB | A one-bit `column_in_range` invariant replaces the combinational `wcol < LINE_PX` read qualification & lane qualification. It tracks exactly the existing wcol assignments, including CE stalls, line starts & reset priority. | Flag retained; comparison absent from read cone; new launch/fanout/routing/slack. |
| hb to row arithmetic/RAM | Output-line comparisons use the next line number before the late line-start mux. Register assignments inside the established line-start branch use arithmetic directly. Row advance uses fractional carry plus integer step, eliminating the following subtraction. | Shorter fitted hb/advance_rows path; no replacement shared bottleneck. |
| LZ4 block_read_total to uncompressed_bytes | One early state/mode increment decode, one 32-bit sum & one final update enable replace scattered state-controlled assignments. Readiness gates the update rather than the increment arithmetic. | Final enable cone & carry placement; every counter endpoint's setup/hold. |
| Delta-index to r_vram_in2 | Byte delta addition computes upper-nibble sums for both carries in parallel, then selects using the low-nibble carry. Eight modulo-256 lanes remain independent. | Whether Quartus keeps this carry-select structure; index fanout & route cost remain to be measured. |
| PoC_V to retimed Add17 capture | Pairwise vertical-total addition & a counter-side terminal comparison remove the total-minus-one dependency. V_total==0 retains the original 32-bit-underflow behavior. | New retimed endpoint identities, carry mapping & all PoC_V path delays. |
| hb to dv_hs1 delay RAM | Delay RAM & its latency are preserved. No source defect in that independent RAM was established by the supplied reports. The complete hb launch report includes endpoints outside the scaler. | Full negative-endpoint export must establish whether this older violation returns. |
| lz4_compressed_bytes | Its RTL updates are preserved. Latest dedicated slack is +0.389 ns; the failing internal counter is a separate register. | Dedicated all-endpoint report & absence of new violations. |

The row calculation preserves 32-bit position wrap & the old 17-bit subtraction
result, including bit 16 when position wraps. No address, RAM-data or video
pipeline stage is added. The new predicate is redundant state, not a delayed
read address. Reset doesn't reset wcol in the reference, so it doesn't reset the
predicate independently either. All six memory instances & their inference
module are untouched: four 3072x40 MLAB banks plus two 3072x40 M10K banks in the
production `MLAB_PARTS=2` configuration. Extra M10K capacity is not assumed.

The later six wa copies & six comparator copies are removed from the active
assignment set, returning to the successful 30 final-driver assignments. Their
experiments remain buildable at their existing commits. New RTL can change
synthesis-generated names: the staged flow first exports actual map RAM input
connections, resolves each bank/bit source, validates it, then runs Fitter.
Fresh audit output-port types reject register-source duplication. Historical
fallback names are observed old names, not a claim that this candidate has been
synthesized. An ambiguous/missing/non-combinational source stops the flow.

After fitting, the audit requires six distinct source atom IDs per bit 0..4,
with each source reaching exactly one bank. Multiple RTL wire names alone don't
pass this test. Expected comparison fanout remains 3,840 per MLAB bank & 20 per
M10K bank; actual resource & memory inference must be checked in the fresh fit.

The older PoC_V failure traverses modeline total additions, the vertical end
comparison & v_cnt update, then top-level Add17 logic. Add17~5/~9 are retimed
capture registers, not source RTL register names. The measured RTL comparison
rules out a new PoC_V source edit between 47ffb26 & 42ec0b2; it doesn't attribute
the critical-path change to a particular fitter action. This candidate changes
only the verified upstream arithmetic, without guessing the retimed bit mapping.

**Timing coverage & inactive HDMI**

`TIMEQUEST_MULTICORNER_ANALYSIS` changes from OFF to ON. The new report script
also enumerates `get_available_operating_conditions -all`, selects each corner
& updates the timing netlist before reporting. It exports every negative setup,
hold, recovery & removal endpoint using `-npaths 0 -nworst 1`. Endpoint TNS is
the sum of each endpoint's worst negative slack. The standard `.sta.rpt` retains
Quartus's per-clock/per-corner summaries for comparison. Worst-path files are
diagnostic top lists; they aren't used as the complete failure inventory.
Pulse-width/period checks use a target/clock-count bound & summary rows to avoid
hundreds of megabytes of full clock-route repetition. A Tcl stand-in regression
checks three synthetic corners & 45 negative endpoints, including exports beyond
30; it doesn't establish Quartus acceptance.

The `hdmi_vs` warning comes from the internal ascal output consumed by the
palette edge detector. With `MISTER_DEBUG_NOHDMI=1`, ascal is absent. The new
conditional constant assigns the same zero previously chosen by synthesis,
without enabling HDMI or switching the palette detector to CRT VSync. Other
HDMI-prefixed ports aren't all inactive: direct-video outputs, I2S audio & the
HPS I2C peripheral still exist. They aren't blanket-exempted.

The last report has 3 unconstrained input ports/13 paths & 48 unconstrained
output ports/66 paths. No external delay or new false/multicycle path is added.
These remain explicit sign-off requirements:

| Interface/ports | Required verified timing information |
|---|---|
| IO_SDA / IO_SCL, MCP23009 | Actual bus rate; device SDA setup/hold & output-valid limits relative to SCL; board/pull-up rise/fall & trace delay. |
| HDMI_I2C_SDA/SCL, HPS I2C | Enabled board connection, bus rate & external device input/output timing, including open-drain board delays. |
| SDCD_SPDIF | Board/switch mode deciding SD-card detect versus SPDIF; asynchronous detection/synchronizer justification or the connected audio receiver's requirement. |
| SDIO_CLK/CMD/DAT[0..3], SD_SPI_CS | Selected SD/SPI versus analog low-bit/sync output mode; card setup/hold/tCO or actual DAC/receiver requirements plus board delay. |
| HDMI_MCLK/SCLK/LRCLK/I2S, USER_IO[2,4,5] | Selected audio pins/receiver, launch/sample clock edges, receiver setup/hold & board skew. |
| HDMI_TX_CLK/DE/D[0..23]/HS/VS | Whether direct video is used; external transmitter/receiver timing & board skew if relevant. |
| LED[2] | Confirm it is only a human-visible indicator & classify the path with a documented functional justification. |
| VGA outputs already cut by inherited SDC | Review connected analog/DAC interface requirements; a pre-existing false path isn't electrical sign-off. |

Inherited clock-group cuts & timing exceptions are unchanged. `clock_transfers`,
`constraints`, `ignored_constraints` & `check_timing` reports expose them for CDC
review. Passing the internal setup/hold checks alone doesn't clear relevant I/O
or CDC acceptance. External specifications & review of inherited exceptions are
still release blockers.

**Independent verification**

Install Verilator, Icarus Verilog, a C++ compiler, Tcl & Python `z3-solver`, then:

```bash
python3 tests/run_timing_candidate_tests.py
# Optional existing HPS tests require the real framework headers:
# psakhis/Main_MiSTer at 0272823a66cb7c601256406a2e80e8c6b2e93e13
python3 tests/run_controller_tests.py ../validation-main
```

The tests compare CRT RAM ports at every clock, all six synchronous RAM outputs,
packing, banks, registered RGB & metadata against earlier RTL. They cover CE
stalls, saturation/next-line boundaries, ring wrap, reset/restart, geometry 0 &
-7/+7, progressive & interlaced fields, supported runtime mode transitions &
half-line sync phases. The full video generator is compared with 47ffb26 during
those mode tests. Transport tests compare complete LZ4 output/control/counter
state with 47ffb26, decode golden literal/match packets, test all 65,536 byte
adder inputs & inject counter state/reset/readiness/rollover combinations.
State injection isn't a claim those combinations are reachable on the wire.
SMT proves the fixed-width arithmetic identities & predicate invariant, not the
complete sequential FPGA. Vendor-IP models & inherited lint waivers remain in
the complete emu elaboration test; no vendor synthesis was performed.

Executed checks passed with Verilator 5.032, Icarus 12.0, Z3 5.4.1 & g++:
10 SMT identity/invariant checks, 11 unit tests, 3 memory-preservation checks,
6,698,817 CRT reference-comparison clocks, 114,000 legacy group-address clocks,
74 golden LZ4 packets across both macro configurations, 65,536 byte-add input
pairs per configuration, native VGA mode/reference tests, OSD/JTFRAME tests,
complete emu elaboration & the existing ASan/UBSan HPS/controller harness.
Standalone lint returned no errors: LZ4 retains 17 width warnings versus 19 in
47ffb26; CRT retains the same 3 RAM-parameter width warnings. The HPS host build
retains its existing integer-to-pointer-size warning in menu.cpp. These warnings
aren't suppressed in place of FPGA timing constraints.

**User-run compilation**

Use a clean worktree at the exact pushed commit in the implementation reply.
From that worktree:

```bash
CANDIDATE_REV=$(git rev-parse HEAD)
export CRT_READ_BUILD_DIR="$(realpath ..)/Groovy-timing-build-${CANDIDATE_REV:0:7}"
bash tests/run_crt_read_address_quartus.sh
```

The destination must not exist. The script copies sources to that directory,
runs the inherited build-ID callback, then the exact stage commands below. The
script must be run by the user; it was syntax/control-flow checked without
launching these tools during candidate preparation.

```bash
quartus_sh --version
quartus_sh -t sys/build_id.tcl pre_flow Groovy Groovy
quartus_map Groovy -c Groovy
quartus_cdb -t tests/report_crt_local_drivers.tcl map
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_map.tsv
python3 tests/resolve_crt_duplicate_sources.py output_files/crt_local_drivers_map.tsv output_files/crt_address_duplication_resolved.qsf
python3 tests/run_crt_duplicate_fit.py
# The guarded wrapper above invokes: quartus_fit Groovy -c Groovy
quartus_asm Groovy -c Groovy
quartus_sta Groovy -c Groovy
quartus_sta -t tests/report_timing_closure.tcl
quartus_cdb -t tests/report_crt_local_drivers.tcl cmp
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_cmp.tsv --require-local
```

Do not fit against stale historical source names after changing RTL. The wrapper
stops on the first missing-duplicate-source warning (171070), addressing the
previous looping Fitter log. Inspect all assignment warnings even when the
wrapper & compilation exit successfully:

```bash
grep -nEi 'Warning|Critical Warning|DUPLICATE_ATOM|ignored|not found|171070' \
  "$CRT_READ_BUILD_DIR/output_files/crt_read_address_compile.log" \
  "$CRT_READ_BUILD_DIR/output_files/Groovy.map.rpt" \
  "$CRT_READ_BUILD_DIR/output_files/Groovy.fit.rpt"
cat "$CRT_READ_BUILD_DIR/output_files/timing_closure/corners.tsv"
cat "$CRT_READ_BUILD_DIR/output_files/timing_closure/endpoint_summary.tsv"
cat "$CRT_READ_BUILD_DIR/output_files/timing_closure/filters.tsv"
```

Keep the entire `output_files/timing_closure/` directory. Each `corner_NN/`
contains `negative_{setup,hold,recovery,removal}_endpoints.tsv`, matching full
`*_paths.txt`, `worst_*.txt`, `min_pulse_width.txt`, `clock_transfers.txt`,
`wcol_setup.txt`, `column_flag_setup.txt`, `hb_setup.txt`, `poc_v_setup.txt`,
`delta_index_setup.txt`, `lz4_compressed_setup.txt`, `lz4_counters_setup.txt` &
`bank_{0,1,2}_{even,odd}_setup.txt`. `corners.tsv` identifies actual conditions.
An UNMATCHED FILTER file needs netlist inspection; it isn't a passing result.

Return these plus `Groovy.map.rpt`, `Groovy.fit.rpt`, `Groovy.sta.rpt`,
`Groovy.sta.summary`, `Groovy.asm.rpt`, stage logs, both atom TSV/JSON audits,
`crt_address_duplication_resolved.qsf`, tool version & candidate commit stamp.
The fit report supplies RAM inference, memory placement & resources. Detailed
path files supply cell/routing delays, launch/capture names & locations. Package:

```bash
tar -czf "../crt-timing-${CANDIDATE_REV:0:7}-reports.tar.gz" \
  --exclude='*.sof' --exclude='*.rbf' \
  -C "$CRT_READ_BUILD_DIR" output_files
```

**Acceptance before release**

Require setup/hold/recovery/removal slack >=0 at every applicable supported
corner, setup/hold TNS=0 & zero failing endpoints. Require passing pulse-width
checks, no relevant unexplained unconstrained paths/clocks or unsafe CDC,
retained six-bank memory organization, M10Ks <=553 & unchanged video latency.
Compare final-driver fanout, column-predicate routes, CRT route delay, ALMs,
registers & MLAB storage with the measured revisions. No positive improvement
is inferred from the new RTL or from successful assembly.

For hardware acceptance, record the commit, bitstream checksum, board/output
adapter, CRT, sender build & each already-working monitor-safe modeline. Check
pixel-grid/color-bar order, blanking edges, cropping/centering at geometry 0 &
-7/+7, stable H/V sync lock, even/odd field progression, supported resolution &
refresh transitions, stream restart/reset recovery, raw/LZ4/delta modes & audio.
Run sustained streaming on the user's setup & record duration, underrun/error
indicators, visible shifts, artifacts & sync loss. Compare against 47ffb26 on
the same setup. These are acceptance procedures, not completed hardware tests.
