# Measured +0.177 ns baseline integration

This candidate restores the source snapshot in `Groovy_closure_plus0177_evidence.zip`.
It has not been compiled with Quartus here. Its objective is to recover the
measured timing advantage, then measure all eight corners without confusing a
reporting option with a fitter option. No timing improvement is claimed yet.

The measured archive is a single Slow 1100 mV 100°C result: setup +0.177 ns,
setup TNS 0, hold +0.247 ns. The
fit summary reports 32,472 ALMs, 31,246 registers, 553 M10Ks & 21 DSP blocks.
The new candidate still requires physical resource & memory verification.

**Source & configuration evidence**

`docs/evidence/measured_plus0177_comparison.json` records verification of all 866
included file hashes against the archive manifest. The extracted reference was
made read-only. Its original directory name ends in `5d28cda`, but its RTL is
byte-identical to `00136c5f03de63d80d8e78208bb6802cfe53c53d`.
Against that commit, the available tracked source/config/test differences are
only `Groovy.qsf` & `tests/check_crt_ram_extraction.py`. The latter is test-only.
There is no archive Git metadata or pre-build source-hash manifest, so matching
the snapshot doesn't independently prove every input consumed by the old build.

| Archived source versus 5d28cda | Classification | Candidate decision |
|---|---|---|
| `rtl/CRT/crt_vsize_fixed.sv` | Functional-equivalent arithmetic/state topology changes: 5d28 adds column predicate, fractional row advance & early line qualification | Restore archived bytes; keep the measured comparator/address implementation. |
| `rtl/lz4.v` | Counter enable/arithmetic factoring & carry-select delta additions in 5d28 | Restore archived bytes, including concurrent reset/run priority. |
| `rtl/vga.v` | Balanced total & rewritten vertical terminal comparison in 5d28 | Restore archived bytes, including unsized subtract/zero behavior. |
| `rtl/CRT/crt_packed_ram.sv` | Identical | Unchanged. |
| `sys/sys_top.v` | Inactive-HDMI tie-off added in 5d28 | Retain explicit zero, matching the old synthesized default. |
| `Groovy.qsf` & duplication QSF | Analysis/configuration & physical duplication | Preserve measured non-duplication assignment set; remove repeated/invalid patterns; resolve actual map sources once. |
| `sys/sys_top.sdc` | Archive & 5d28 identical | Only new exception is display-only onboard LED[2]. |
| Reporting/tests | No FPGA functional change | Keep complete corner exports, add provenance, coverage gates & archived-source checks. |

The 356-line archived QSF contains expanded pin/device/file assignments already
supplied by `sys/sys.tcl`, `sys/sys_analog.tcl` & `files.qip`. The offline capture
recursively evaluates QIP assignment scripts for Quartus 17.0.2 and preserves
raw order, repeated calls & normalized paths. It models explicit assignments,
not vendor defaults or Quartus wildcard precedence. The comparison retains
those limits rather than calling a text comparison a synthesis result.

There are 62 duplication calls but 31 unique full assignment tuples: the sourced
31 are repeated explicitly in the main QSF. Apart from duplication, the archived
assignment set adds only three `set_hps_location_assignment` aliases versus
00136c5. Versus 5d28 it also changes `TIMEQUEST_MULTICORNER_ANALYSIS` to OFF.
The candidate's explicit/source-expanded non-duplication set includes every
measured call, plus explicit `OPTIMIZE_MULTI_CORNER_TIMING ON`. The latter
matches the archived Fitter excerpt's On setting. This is regression-tested,
including recursive QIP coverage; a short QSF isn't assumed equivalent merely
because it uses the same device name.

The candidate keeps the three HPS aliases in `rtl/CRT/crt_measured_hps.qsf`.
Pin locations, drive strengths, I/O standards, macros, clock/SDC inputs, seed 1
& the other measured physical options remain supplied by the same sourced files.
`MISTER_DEBUG_NOHDMI=1` is unchanged. The six 3072x40 synchronous banks remain
four MLAB/two M10K in the production configuration, with the same read/RGB latency.
PLL files & the 12.081 ns / 82.77 MHz requirement are unchanged.

**What the reports establish**

The passing fit has six distinct final address sources for each bit 0..4.
Each source drives one bank: 3,840 fanout for the four MLAB banks, 20 for the two
M10K banks. Its map/fitted identities & bank connections are in the JSON
comparison. Detailed bank path reports provide only the placement/path samples
actually exported; they don't locate every address-driver bit.

The included oversized-log excerpts contain five distinct missing-source forms:
`packed_ram?1?.local_ra_odd?0?~*` through `...odd?4?~*`. The approximately
3,879,896 repeated warnings do not mean that many distinct source nodes failed.
Named fitted `crt_read_*` drivers demonstrate the intended final topology,
consistent with at least partial assignment processing. The reports do not
isolate which repeated invocation was honored or whether later retries saw a
source removed/renamed by an earlier duplication/optimization pass. Repeated
assignments/source invalidation are hypotheses; warning volume isn't a timing
mechanism or proof that all duplication calls were ignored.

The candidate uses no wildcard source names or old synthesis-name fallback.
Mapping exports the real RAM input sources; Python generates 30 unique exact
bank/bit assignments, rejects missing/ambiguous/register outputs, validates their
connections, then fits. The original speculative upstream wa[3] assignment is
not restored. Fitter warning 171070 terminates the guarded process immediately.
A fitted audit verifies six disjoint source IDs per bit. The `dup-off` diagnostic
records topology without requiring separation, so its result isn't confused
with a qualifying candidate.

The old `hdmi_vs` net belongs to absent ascal but feeds the palette edge detector.
Explicit zero preserves the value the old mapper selected. Equivalence of the
active RTL value doesn't prove an identical placement; `hdmi-old` isolates that
physical question. HDMI-prefixed I2S/I2C/direct-video pins aren't blanket-disabled.

Clean 5d28 failed slow 100°C at -1.715 ns with TNS -256.066 ns & 705 endpoints,
504 in the scaler. Its worst path is group_col[2] to bank-1 odd output[23],
13.188 ns data delay & five levels. The passing image instead has delta-index[5]
to r_vram_in2[6] at +0.177 ns and block_write_total[3] to state[2] at +0.197 ns.
Simultaneous RTL, duplication & configuration changes prevent assigning the
regression to one edit. This candidate restores measured RTL because it has
physical evidence, not because an isolated causal experiment has been completed.

Quartus's [17.x settings reference](https://docs.altera.com/r/docs/d815780/17.1/quartus-prime-standard-edition-settings-file-reference-manual/timequest_multicorner_analysis?contentId=FGmzVdOMsWiK8o96aUQqSg)
states that `TIMEQUEST_MULTICORNER_ANALYSIS` controls analysis, not multicorner
fitter optimization. [OPTIMIZE_MULTI_CORNER_TIMING](https://docs.altera.com/r/docs/d815780/17.1/quartus-prime-standard-edition-settings-file-reference-manual/optimize_multi_corner_timing?contentId=uxx6_VslYhDYUlPyYAuDeg)
is the separate fitter option. Both measured Fitter reports record optimization
On. Thus the OFF/ON TimeQuest switch alone is not an established explanation for
the routing regression. The candidate retains TimeQuest OFF to match the archive,
while the independent STA script explicitly analyzes all eight conditions.

**Controlled builds**

All variants use Quartus 17.0.2 Build 602, seed 1, the same device, pin assignments,
clock requirements, clean databases & eight-corner reporting. Candidate is the
reference for each one-factor comparison; none restores invalid duplication.

| Variant argument | Only factor changed from candidate | Run when |
|---|---|---|
| `candidate` | Measured RTL + valid duplication + HDMI zero + measured analysis option | First build. |
| `crt-new` | CRT RTL from 5d28 | Isolate the scaler rewrite's physical effect. |
| `transport-new` | LZ4 & VGA RTL from 5d28, grouped | Test the independent arithmetic bundle; split further only if its result warrants it. |
| `dup-off` | No DUPLICATE_ATOMs | Candidate fails to reproduce advantage, or driver-placement causality needs testing. |
| `hdmi-old` | Remove only explicit inactive-HDMI zero | Isolate cleanup's physical effect if needed; intentional old warning is diagnostic. |
| `analysis-on` | TIMEQUEST_MULTICORNER_ANALYSIS ON | Check analysis-only equivalence with identical physical inputs. |
| `fitter-slow` | OPTIMIZE_MULTI_CORNER_TIMING OFF | Test actual multicorner fitter optimization; still report all eight corners. |

Do not run seven builds automatically. Start with candidate; choose the relevant
one-factor comparison from its failed launch/capture families. The existing clean
5d28 result is a combined-change reference, not a replacement for controlled tests.

**I/O status & constraints**

Pin routing is traced through `sys/sys.tcl`, `sys/sys_analog.tcl` & `sys/sys_top.v`.
The DE10-Nano's onboard ADV7513 is described in the [ADI board guide](https://developer.analog.com/docs/system-level/solutions/reference-designs/adv7513/user-guide.html).
Its [Rev. B datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ADV7513.pdf)
specifies video setup/hold 1.8/1.3 ns, audio setup/hold 2/2 ns & I2C SDA setup/hold
100/100 ns. These are device-pin requirements, not complete FPGA output delays:
board skew, selected clock edges & programmable input-clock phase remain inputs.
No missing board delays are replaced with zero.

| Ports | Actual role & status |
|---|---|
| LED[2], PIN_V16 | Onboard status display, no clocked external receiver. Added one output false path, matching existing display-only treatment of LED_* pins. |
| IO_SCL/IO_SDA, PIN_U14/AG9 | External MCP23009 I2C. SDA is sampled directly by the CLK-qualified engine, not an entry synchronizer. Source requests 500 kHz. The [MCP23009 datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/20002121C.pdf) gives mode-specific limits, including 400-kHz SDA setup 100 ns & output-valid max 900 ns. Verify actual bus mode, adapter supply, pull-ups/load & rise/fall; don't apply 400-kHz limits to 500 kHz without justification. Unresolved. |
| HDMI_I2C_SCL/SDA | HPS I2C to ADV7513. Need programmed HPS SCL, input sampling relation, device response limits & board rise/fall. Unresolved. |
| HDMI_TX_CLK/DE/D[0..23]/HS/VS | Direct-video outputs remain in the NOHDMI source. Need active transmitter/clock configuration & verified trace skew before generated clocks/min/max delays. Unresolved. |
| HDMI_MCLK/SCLK/LRCLK/I2S | Audio remains active. Need sample edges & board skew for the connected receiver. Unresolved. |
| USER_IO[2,4,5] | Runtime mux between I2S & open-drain GPIO. Need selected adapter/device & electrical timing for both used modes. Unresolved. |
| SDCD_SPDIF, PIN_AH7 | Runtime card-detect input/SPDIF output. Direct detect influences SD_CD/output selection before an entry synchronizer. Need board mode, CDC review & receiver timing; no asynchronous blanket cut. Unresolved. |
| SDIO_CLK/CMD/DAT[0..3], SD_SPI_CS | Runtime SD/SPI or analog low-bit/sync routing. Need card/DAC/adapter identity, active switch mode & external timing/skew. Unresolved. |
| VGA_* & inherited clock-group/multicycle exclusions | Existing cuts retained, not treated as proof of board or CDC sign-off. Review `constraints`, `ignored_constraints`, `clock_transfers` & `check_timing`. |

`report_io_coverage.py` emits one record per remaining input/output port, including
partial constraints, available pin mappings, role, blocking reason & known device
limits. Unknown newly appearing ports remain blockers. If LED[2] is still reported,
its exception is marked ineffective rather than automatically waived. All other
unresolved active/mode-dependent paths remain release blockers.

**Non-Quartus verification**

```bash
python3 tests/run_timing_candidate_tests.py --main ../validation-main
python3 tests/compare_measured_reference.py ../measured-plus0177-reference comparison.json
```

The optional HPS test needs psakhis/Main_MiSTer at
0272823a66cb7c601256406a2e80e8c6b2e93e13. The main suite needs Verilator, Icarus,
Tcl, Python & g++; it doesn't invoke Quartus. Z3 identities are retained separately
for optional newer-RTL variants, not claimed as proofs of the restored candidate.

Executed non-Quartus checks passed: 19 Python unit tests; Tcl assignment/matching
checks; 6,698,817 reference-comparison clocks across all six RAM ports, synchronous
data & registered RGB/sync; 114,000 legacy bank-address RTL cycles; 74 golden LZ4
packets across both macro configurations, counter reset/stall/rollover tests &
65,536 delta-byte pairs in each configuration; seven VGA progressive/interlaced
mode cases with geometry 0/-7/+7, runtime changes, CE/reset & half-line fields;
H-size/OSD regressions; complete emu elaboration using explicit vendor/VHDL models;
HPS/controller tests & host syntax checks. The existing HPS `menu.cpp` integer-to-
pointer cast warning remains. The restored RTL retains historical trailing
whitespace intentionally so archived input hashes remain exact.

The export validator also correctly rejects the actual clean 5d28 timing results
(four slow-corner failures), while its resource/clock checks pass. Synthetic tests
cover incomplete exports, endpoint-count mismatches, pulse failures, memory changes,
unmatched ports & preservation of actual A/B source inputs. These checks establish
report handling, not vendor acceptance of the new project or fitted timing.

Reference basis: the measured manifest/source/reports; `00136c5` & `5d28cda` source;
psakhis/Groovy_MiSTer `rtl/lz4.v` emitting states, reset/run priority & delta output;
s3gfaultx/mistercast-linux `src/stream/GroovyMister.cpp::sendFrame` standard LZ4 block
compression & exact payload byte count. No sender or packet-format change is made.

**User-run compilation & evidence**

From the fresh worktree at the pushed candidate commit:

```bash
export CRT_READ_BUILD_DIR="$(realpath ..)/Groovy-measured-candidate-build"
bash tests/run_crt_read_address_quartus.sh candidate
```

The output directory must not exist. The runner copies committed files using
`git archive HEAD`, never the current working directory or an old database.
It checks the tool version, runs the real build-ID callback, performs map,
exports map inputs, resolves/validates duplication, then fits/assembles/analyzes:

```bash
quartus_sh -t sys/build_id.tcl pre_flow Groovy Groovy
quartus_map Groovy -c Groovy
quartus_cdb -t tests/report_crt_local_drivers.tcl map
python3 tests/resolve_crt_duplicate_sources.py output_files/crt_local_drivers_map.tsv output_files/crt_address_duplication_resolved.qsf
python3 tests/run_crt_duplicate_fit.py  # guarded quartus_fit Groovy -c Groovy
quartus_asm Groovy -c Groovy
quartus_sta Groovy -c Groovy
quartus_sta -t tests/report_timing_closure.tcl
quartus_cdb -t tests/report_crt_local_drivers.tcl cmp
```

The shell runner also writes source manifests & source-input copies before map
and fit, records exact project calls/QIP dependencies, checks post-fit driver
separation, writes I/O coverage, timing & resource/clock gates, and packages
`${CRT_READ_BUILD_DIR}-reports.tar.gz`. Bitstreams are excluded from the report
archive but remain in output_files. Each A/B output records its base commit,
variant & actual overridden source hashes, so the commit alone isn't mistaken
for the experiment's complete identity. Only the staged runner is supported;
a direct --flow/GUI compile doesn't perform fresh-map target resolution.

Eight conditions must be present: slow/fast at -40, 0, 85 & 100°C, 1100 mV.
The validator rejects missing/duplicate corner summaries, missing endpoint/path
files, inconsistent negative endpoint counts, unparsed pulse reports & missing
path-family/constraint exports. `timing_gate.json` records negative WNS/TNS,
endpoint or pulse failures; successful tool exit isn't qualification.
`resource_clock_gate.json` checks the device, <=553 M10Ks, 491,520 MLAB bits,
four MLAB/two M10K bank hierarchies & the 12.081 ns video-clock report. Detailed
LZ4 exports include both counter-capture & counter-launch paths, including
block_write_total to state. Global failure inventories remain complete even if
a named path-family filter is unmatched; such a filter needs review.

For one necessary A/B build, use a separate fresh destination, for example:

```bash
export CRT_READ_BUILD_DIR="$(realpath ..)/Groovy-measured-crt-new-build"
bash tests/run_crt_read_address_quartus.sh crt-new
```

Return the generated report archive(s), including `source_manifest_*`,
`project_calls_*`, `source_inputs/`, resolved QSF, both driver TSV/JSON audits,
full map/fit/STA/assembly reports, logs & all of `timing_closure/`. Check all
setup/hold endpoint inventories & TNS, recovery/removal, pulse width, ignored SDC,
unconstrained clocks/ports, driver fanout, memory inference & resources.

Production timing acceptance still requires nonnegative setup/hold at all eight
corners, zero negative TNS/endpoints, passing recovery/removal/pulse checks,
no unexplained active I/O or CDC gaps, valid driver assignments, six-bank RAM
retention & <=553 M10Ks at the unchanged clock. Hardware CRT testing remains a
separate acceptance step after physical results; use the existing geometry,
field, sync, restart & sustained-stream checks on known-working modelines.
