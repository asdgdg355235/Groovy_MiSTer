# Quartus 25 core-side Cabinet integration

The branch starts at `feature/analog-triggers`, commit
`735c777be2ec859afe3dc37cc448d49440447add`. Its remote head matched that
commit when work started. The independent compatibility commit is
`a383702ba864471d97563cc7abdb1add1446e2ed`.

Quartus was not executed. These sources have software RTL verification;
Quartus compilation, physical timing, device fit & MiSTer hardware remain
unqualified. No RBF is presented as a verified Cabinet build.

## Reference basis

Both `rmonic79/MiSTer-CRT-Adjust` master &
`asdgdg355235/MiSTer-CRT-Adjust` master resolved to
`c682de9f4acc61d8f4c7779efb48149d3baa3a8e`. The fork's master has no diff
from the inspected upstream master. Exact reference-file SHA-256 values are
in `cabinet-sources.json`; frozen upstream RTL is in `tests/reference/`.

| Repository & source | Symbol or behavior used |
| --- | --- |
| [MiSTer-CRT-Adjust core guide](https://github.com/rmonic79/MiSTer-CRT-Adjust/blob/c682de9f4acc61d8f4c7779efb48149d3baa3a8e/docs/core-side-integration.md) & `examples/core_side_snippet.v` | Core-side placement; `hs_ref_out`; true VBlank; native OSD anchor |
| Same commit, `rtl/crt_adjust.sv` | `crt_adjust`, CONTENTSHIFT/SYNCSHIFT, ping-pong line RAM, internal V-Shift |
| Same commit, `rtl/crt_vsize.sv` | `crt_vsize`, `tube_on`, Q8 positioning, `t_slotA/B`, `t_mix_*`, `isqrt_h/l`, `vs_shreg` |
| Same commit, `docs/vsize-integration.md`, `docs/v-size-design.md`, `docs/v-size-desync-roadmap.md`, `examples/vsize_integration_snippet.v` | Cabinet/PVM distinction, three-line OSD steps, ring sizing & synchronization trade-offs |
| Groovy analog-triggers base, `Groovy.sv`, `rtl/vga.v` | Pixel divider, modeline commands, native blank/sync/field generation & video pipeline |
| Same base, `sys/video_mixer.sv`, `sys/gamma_corr.sv`, `sys/video_freak.sv`, `sys/hps_io.sv` | Mixer latency, true-blank sideband alignment, final DE, 128-bit status transport |
| Same base, `hps_linux/src/user_io.cpp`, `user_io_status_get/set` | Existing 16-byte status storage & byte-spanning options |
| Groovy `16b3d9a51d708e76f8ab37c1c4e8f2228e02b070`, `rtl/lz4.v` | Synchronous window prefetch, single write port & collision forwarding |
| Groovy `a692f4f6d75a79e67cb36f1065ff0d7c9a97ae92`, LZ4 tests | Golden decoder/state comparisons, overlap, rollover, stalls & delta tests |
| Groovy `3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a`, timing/pulse scripts | Supported targeted diagnostic APIs & complete endpoint exports |
| [psakhis/Groovy_MiSTer](https://github.com/psakhis/Groovy_MiSTer/tree/109908c9ddbd4397ba7aadb193de61fdb8cb34e6), `rtl/vga.v`, `rtl/lz4.v` | Receiver implementation reference; native timing/decoder remain inherited |

Upstream's actual Cabinet RTL uses squaring, weighted integer interpolation
& integer square-root reconstruction, approximately gamma 2. The roadmap's
gamma-2.4 LUT proposal wasn't substituted for that algorithm. Older text
claiming unchanged VSync or untouched HDMI doesn't describe this core-side
Cabinet configuration: the RTL's bounded VSync delay is retained, & HDMI
receives the processed stream.

The imported modules retain Umberto Parisi/rmonic79's attribution & GPL-3.0-or-later
notices. `rtl/CRT/LICENSE` preserves upstream's license text. No rejected
geometry branch was merged; native VGA arithmetic, framework RTL & controller
sources are unchanged from the analog-triggers base.

## Video path & controls

`Groovy.sv` chooses one geometry path. With CRT Adjust Off, or an unsupported
mode, the original `jtframe_resync` → `jtframe_hsize` → `video_mixer` →
`video_freak` path remains active. With CRT Adjust selected, the mixer receives
native RGB/sync/blank directly; its output feeds `crt_vsize` → `crt_adjust` →
`video_freak`. Legacy adjustments therefore aren't applied twice.

`groovy_crt.sv` is instantiated inside `emu`. The framework `sys/sys_top.v`
& all other existing `sys/` RTL files are unchanged. `sys/pll_q25.qip` is a
new build-configuration file, byte-identical to the original Q17 PLL QIP list.
It preserves the video PLL, HDMI/audio PLLs & dynamic reconfiguration path.
The original device, seed & three HPS location assignments already match the
required target; no geometry placement constraints or duplicate aliases were
added.

| Control | Status bits | Active CRT mapping |
| --- | --- | --- |
| CRT Adjust | 60 | New master switch, default Off; hidden for unsupported modelines |
| CRT H offset | 21:17 | Existing labels retained. CONTENTSHIFT negates the stored signed value; SYNCSHIFT uses it directly to retain the legacy physical direction |
| CRT V offset | 26:22 | Existing signed sync-delay convention; only `crt_adjust` applies it when selected |
| CRT scale enable | 47 | Existing H-Size enable |
| CRT scale factor | 51:48 | Existing labels retained. The stored signed value is negated for upstream's read-period convention; positive legacy factors narrow the picture |
| Cabinet V-Size | 64:61 | 0, +1…+7, -8…-1; one displayed step is three lines; positive enlarges |

The status connection is widened to the framework's existing 128-bit port.
No existing option or controller bit is reassigned. Only Cabinet mode is
exposed for vertical scaling; `tube_mode` is fixed to 1, so there is no PVM
runtime mode switch. V-Size 0 bypasses the vertical stage externally.

CONTENTSHIFT is the default build: Cabinet retains native horizontal cadence
& H-position moves content. Groovy supports arbitrary source placement, so
SYNCSHIFT is also available as a separate compile-time build using
`--hpos-mode sync`. It intentionally changes HSync phase. Both mechanisms have
independent read-enable/OSD regressions; neither has physical qualification.
Values that run content into the raster's sync interval remain bounded by the
modeline's physical porch space.

The read accumulator uses `4 * measured/configured clocks-per-pixel + hsize`
quarter clocks. It resets on the rising edge of `u_adjust.hs_ref_out`, including
the shifted reference in SYNCSHIFT. Uniform input CE is checked against the
configured divider; no fixed 96 MHz/6 MHz ratio is assumed.

The mixer has no true-VBlank output port. Core-side registers carry native
HBlank/VBlank through the same two native-CE stages as `gamma_corr`, followed
by the mixer's full-clock & CE-qualified output stages. The vertical stage
receives this true VBlank. Its regenerated `vb_out` feeds `crt_adjust.vb_in`;
the horizontal-window input is `~crt_vsize.de_out`, as in the V-Size integration
example. Combined inverse DE is never used as true VBlank.

`de_osd` opens only on the native HBlank falling edge, qualified with buffered
vertical visibility, & closes on the adjusted image window's end. A VB change
inside active pixels in SYNCSHIFT cannot create a second horizontal anchor.
The final `video_freak.VGA_DE_IN` selects this window only while CRT Adjust
is selected. Its ordinary mixer-DE connection remains the bypass source.

## Upstream adaptations

The photometric arithmetic, fractional precision, channel order, rounding,
slew, stable-frame logic & 24-line VSync delay mechanism are retained.
Source changes from frozen upstream are limited to:

* Parameterized horizontal RAM address width: two 1,024-sample banks instead
  of the upstream two 512-sample banks. Runtime H/V totals select signed
  shift-register taps within statically allocated maximum lengths.
* One HSync sample aligns true VB with Groovy's completed read bank. The
  extra upstream VB register lost source row 0 & admitted a blank row at the
  bottom in the native-raster regression. First/last-row tests cover the fix.
* A full Cabinet line now reports all `LINE_PX` pixels. The upstream saturated
  index reported `LINE_PX-1` at capacity. Writes & speculative idle reads are
  bounded so the final ring slot cannot address beyond the array.
* The source cursor clamps at the final active line during live size slews.
  The upstream divider/size transition can advance past that line. The last
  valid source row is held with zero neighbor weight.
* The line-base function is automatic & its write address is named before
  indexing RAM, avoiding a Verilator frontend failure without changing its
  address calculation or the registered RAM-read schedule.

Differential tests compare both frozen modules. Sync/control outputs remain
checked across size transitions. RGB/DE differences are permitted only at
the explicitly corrected VB/source-clamp boundaries; independent absolute
checks cover those boundaries. The Icarus path compiles the frozen references
verbatim. The optional Verilator path hoists the reference V-Size RAM-write
address into an identical wire to avoid its function-in-LHS compiler failure.

## Supported modes, latency & memory

| Eligibility condition | Implemented bound |
| --- | --- |
| Native pixel period | Uniform integer 8…16 FPGA clocks |
| Active width | 33…640 pixels |
| Active height | 64…288 lines, less than total lines |
| Horizontal total | Greater than active width, at most 800 pixels |
| Vertical total | 200…312 lines |
| Interlace | New CRT/Cabinet path bypassed; native field pipeline retained |
| Forced scandoubling or Scandoubler Fx | New path bypassed; original mixing/scandoubling retained |
| Reset/modeline change | Immediate bypass; six native frame boundaries required before re-entry |

The bounds keep the upstream 10-bit pixel counters & 22-bit frame-clock
measurement valid. At the maximum total/period, `800 * 312 * 16 = 3,993,600`
clocks fits below `2^22`. A detected nonuniform CE also revokes selection.
This implementation doesn't claim Cabinet resampling of interlaced fields:
480i retains the original path rather than mixing fields through a
progressive-only ring. New CRT controls are hidden when the mode is ineligible.

CRT Adjust adds its completed-line buffer, the upstream two read-CE register
stages & an output-alignment clock register. Cabinet additionally uses the
upstream causal two-line start & native-CE pixel pipeline; shrink/enlarge
anchoring changes the line offset. It slews by one line per native frame.
Its VSync delay remains bounded to 24 lines; changing that delay intentionally
changes VSync phase during adjustment. No claim of identical sync waveforms
is made. Off/unsupported bypass adds no pipeline latency to the original path.

| Logical storage | Dimensions | Bits verified by Yosys |
| --- | --- | ---: |
| Cabinet ring | 46 × 640 × 24 | 706,560 |
| CRT horizontal ping-pong RAM | 2,048 × 24 | 49,152 |
| LZ4 window | 8,192 × 64 | 524,288 |

Yosys retains each as one synchronous read/one synchronous write memory.
M10K attributes remain in the RTL. Logical bit counts aren't physical M10K
counts: block packing, metadata, MLABs, DSPs, ALMs & the complete device fit
must be read from the local Quartus reports. The 46-line ring covers the
exposed maximum 24-line Cabinet adjustment plus its causal margin. No packed
MLAB or six-bank CRT architecture was imported.

HDMI follows the processed core stream while CRT Adjust is selected. The
scaler therefore sees changed content, CE & active-window metadata; enabled
HDMI isn't bit-identical to the original. Off/unsupported video is compared
against the original pipeline cycle by cycle. Physical HDMI compatibility
still requires a MiSTer capture/display test.

## Software verification

Install Python 3, Icarus Verilog, Verilator, Yosys, a C++ compiler & make.
These commands never execute Quartus:

```sh
python3 tests/run_lz4_q25_differential.py
python3 -m unittest discover -s tests -p 'test_*.py'
CRT_SIMULATOR=verilator python3 tests/run_cabinet_tests.py
python3 tests/run_video_pipeline_tests.py
python3 tests/run_native_av_tests.py
python3 tests/check_cabinet_memories.py
python3 tests/check_q25_prepare.py
python3 tests/run_controller_tests.py /path/to/Main_MiSTer --mutation-check
```

Controller headers must come from `psakhis/Main_MiSTer` commit
`0272823a66cb7c601256406a2e80e8c6b2e93e13`, as required by the existing test.
Omit `CRT_SIMULATOR=verilator` to run the Cabinet suite with Icarus instead.
The pipeline comparison uses Verilator because the inherited framework has
array/port constructs Icarus 12 cannot elaborate. Its compatibility switches
cover existing `hq2x` wire/procedural declarations & mixed assignment forms;
no framework source is patched for simulation. Compiler warnings are retained
in the verification logs. FIFO models check functional behavior, not physical
CDC or memory-block timing.

The suite covers both H-position mechanisms, fractional read periods, H-size
enlarge/shrink, signed offsets, native OSD anchoring, true VB, edge rows,
dynamic modelines, reset/ratio rejection, gamma-2 blending, RGB gradients,
alternating horizontal lines, all 65,536 integer-square-root inputs, ring
wrap/clamp & VSync delay. LZ4 tests include full/byte-only decoding, all decoder
states, stalls, overlapping matches, complete window wrap & delta arithmetic.
Native 240p/480i tests observe alternating half-line VSync phases. Audio compares
the production module with the frozen base in mono/stereo at all rate selectors.
Controller tests retain the existing analog-trigger assertions & defect mutations.

## Local Quartus builds

Use the exact Quartus Prime Lite `25.1std.0 Build 1129` binaries on PATH.
The runner verifies each compiler tool's version before compilation. Each
command requires a new output directory & a clean committed source tree:

```sh
python3 tools/q25_build.py --variant BASE --run
python3 tools/q25_build.py --variant CABINET --run
```

The independent revisions are `Groovy_Q25_BASE` & `Groovy_Q25_CABINET`.
Both use device `5CSEBA6U23I7`, seed 1 & the original SDC files. CABINET adds
only the feature macro & its three source files to the BASE assignments.
There are no new clock exceptions, frequency relaxations or geometry placement
constraints. BASE includes the synchronous LZ4 compatibility port but no new
CRT hardware. To check preparation without launching a compiler:

```sh
python3 tools/q25_build.py --variant BASE --prepare-only --output /tmp/Groovy-Q25-BASE
python3 tools/q25_build.py --variant CABINET --prepare-only --output /tmp/Groovy-Q25-CABINET
```

The separate SYNCSHIFT experiment uses:

```sh
python3 tools/q25_build.py --variant CABINET --hpos-mode sync --run --output q25-builds/Q25-CABINET-SYNC
```

Expected archives are `q25-builds/Q25-BASE-reports.tar.gz` &
`q25-builds/Q25-CABINET-reports.tar.gz`. The runner retains compiler logs,
complete output reports, source/assignment hashes, source patch & provenance
even after build/report failure. Diagnostic Tcl uses targeted assignment
queries; unrestricted assignment-name enumeration is absent.

The timing exporter requires eight operating conditions & writes complete
endpoint tables for setup, hold, recovery & removal, full negative routed
paths, worst routed paths, pulse checks, clock transfers & constraint coverage.
Inspect complete resource/RAM/warning panels in `output_files/q25/report_panels.tsv`.
Check the exported timing tables with:

```sh
python3 tools/q25/check_timing.py q25-builds/Q25-BASE/output_files/q25/timing
python3 tools/q25/check_timing.py q25-builds/Q25-CABINET/output_files/q25/timing
```

Timing acceptance requires nonnegative setup WNS, zero setup TNS & failing
endpoints in every corner, passing hold/ancillary checks & complete constraints.
The table checker doesn't sign off RAM, resource fit, warnings or hardware.
Verify that LZ4 window & Cabinet ring map to embedded RAM, inspect actual
M10K/MLAB/DSP/ALM/register use, & reject missing/incomplete diagnostics.

On MiSTer, compare Off against the original core; test 240p & 288p color ramps,
alternating rows, every geometry direction, edge rows, OSD position, scrolls,
large V-Size transitions, reset & live modeline changes. Compare processed HDMI
with analog output, then verify 480i parity/cadence & scandoubler/scanline modes
through the unchanged fallback. Exercise raw/LZ4/delta video, audio & analog
L2/R2/L3/R3 inputs. Physical timing closure is unclaimed until both archives &
those hardware observations have been reviewed.
