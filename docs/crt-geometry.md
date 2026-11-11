# CRT geometry integration

This branch adds Cabinet vertical resizing & independent RGB edge masking to
integration base `735c777be2ec859afe3dc37cc448d49440447add` on
`feature/analog-triggers`. Existing position controls, horizontal scaling,
controller mappings, trigger snapshots & streaming remain in that lineage.

## OSD controls

| Status bits | Setting | Encoding |
|---|---|---|
| 21:17 | Existing CRT H offset | Retained |
| 26:22 | Existing CRT V offset | Retained |
| 47, 51:48 | Existing CRT scale enable/factor | Retained horizontal algorithm |
| 63:60 | CRT V-Size | 0..7 means 0..+7; 8..14 means -7..-1; 15 means zero |
| 67:64 | Mask horizontal | 0..30 source pixels per side, in steps of two |
| 71:68 | Mask vertical | 0..15 physical scanlines per side, per field |
| 72 | Overscan mask | Off/On; amounts hide while Off |

V-Size is independent of horizontal scale enable. Positive values enlarge;
negative values reduce. One step is a physical scanline per field, including
480i. PVM mode is excluded because it generates another line cadence & lacks
field-aware half-line synchronization.

The mask changes RGB only. It neither crops DE nor changes sync. The existing
240p crop remains separate: `video_freak` changes the captured DE window &
HDMI aspect/scaling calculations, whereas the new mask blacks selected pixels
within that window. Position controls change sync-relative placement; size
controls resample the image.

## Reference basis

| Repository and path | Symbols and verified behavior | Use |
|---|---|---|
| `asdgdg355235/Groovy_MiSTer`, `Groovy.sv`, `rtl/vga.v`, integration base above | `vga`, six striped RGB FIFOs, `pixel_counter`, `field`, `H_pulse_start`, `V_total` | Retain source pixel consumption, frame feedback & interlace generator. Native field feedback still goes directly to `hps_ext`. |
| `psakhis/Groovy_MiSTer/main`, same paths; common ancestor `109908c9ddbd4397ba7aadb193de61fdb8cb34e6` | `vga` & `setSwitchres` in `hps_linux/src/support/groovy/groovy.cpp` | Confirm timing semantics & native CE ratios 4/6/8/12/16. Scandoubled source ratios can be lower. |
| `rmonic79/MiSTer-CRT-Adjust`, `rtl/crt_vsize.sv`, `docs/vsize-integration.md`, `docs/v-size-design.md`, `docs/v-size-desync-roadmap.md` | Cabinet `t_pos`, two-row light blend, `isqrt_h/isqrt_l`; PVM line retimer; `vs_del` | Derive `crt_vsize_fixed`; remove the eight-subphase dependency & preserve raw field sync. Keep the PVM engine outside this integration. |
| Corrected `asdgdg355235/MiSTer-CRT-Adjust`, `rtl/crt_vsize_fixed.sv`, `rtl/crt_edge_mask.sv` | Field-local row tags, parallel gamma-2 interpolation, RGB-only mask | Vendored RTL; see `rtl/CRT/README.md` for the source revision. |
| `jotego/jtcores`, `modules/jtframe/hdl/video/jtframe_hsize.v`, `jtframe_hretime.v`; target `rtl/JTFRAME/jtframe_hsize.v` | `summand`, fractional source addresses, ping-pong line storage; `jtframe_hretime` FIFO, CE accumulator & sync delay | Retain Groovy's existing horizontal algorithm. Expose its address-width parameter for wide rasters. A read-rate/FIFO replacement supplies no required vertical function. |
| CRT Adjust upstream, `rtl/crt_adjust.sv`, `rtl/crt_adjust_sys.sv` | `hoff_s`, `rdcnt`, `hs_read_ref`, `hshift_tap`, `vshift_tap` | Repair signed offsets & capacity in the fork; do not replace Groovy's existing position or horizontal engines. Their generic VSync shift is line-sampled. |
| `MiSTer-devel/NES_MiSTer`, `NES.sv`, `rtl/video.sv`, `rtl/composite_crop.sv` | `video_freak`, `en216p`, `voff`, `hide_overscan`, `composite_crop` | Distinguish HDMI crop from source blanking: 216-line crop with offset; native modes expose 224/240-line windows & optional borders. |
| `MiSTer-devel/Genesis_MiSTer`, `Genesis.sv`, `rtl/vdp.vhd` | `video_freak`, 216-line crop, `BORDER_EN`, `HBL/VBL` | Confirm that border blanking, crop & image scaling are separate operations. |
| `rmonic79/NeoGeo_MiSTer_Streamer`, now `rmonic79/rmNeoGeo_MiSTer`, branch `streamer`, `sys/sys_top.v` | `u_crt_vsize`, `u_crt_adjust_sys`, `ce_hpix/hr_out/hhs_fix/hvs_fix/hde_emu` | Confirm stage order, true VBlank & downstream CE wiring. Verify that its HDMI tap precedes analog CRT adjustment. |
| Target `sys/sys_top.v`, `sys/osd.v` | `VGA_scanlines`, `vga_osd`, `hdmi_osd`, HDMI tap assignments, `v_osd_start` | Insert the scaler core-side. Add a Groovy-only OSD centering sideband; other cores keep the original OSD interface. |
| `asdgdg355235/Main_MiSTer`, `user_io.cpp`, `menu.cpp`, HEAD `3bba2bced543db8523ab524f068a8710ea30516e` | `user_io_status_bits/get/set/save`, `cur_status[16]`, menu option parser | Existing 128-bit status & save format cover all new controls. No C++ menu or configuration change is required. |

## Pipeline and timing

The path is `vga` -> fixed Cabinet scaler -> existing `jtframe_resync` ->
existing `jtframe_hsize` -> RGB mask -> `video_mixer` -> `video_freak` ->
framework scanlines/OSD/output. Raw source counters & protocol feedback branch
before geometry. Audio & controller code are unchanged.

The Cabinet stage carries HS, VS, field ID & both CEs through four clock
periods. It does not reconstruct sync. Its VB output follows the resized
window & closes at native VSync. The native progressive/interlaced timing
generator remains byte-identical to the integration base. The height input
is the upcoming field's physical line count, including odd-height modes.

Enlargement starts two source lines late; a reduction of N lines starts N+2
lines late. The two-tap filter needs completed rows. Enlarged pixels beyond
native VSync are clipped, so a small front porch limits the visible bottom
edge. The module does not move VSync or change H frequency to hide that limit.
This is a source-availability limit of fixed-timing streaming resampling.
It is not an additional frame queue.

The OSD centers from DE dimensions. Its new, macro-guarded `anchor_vpos`
compensates for the resized window's measured height & delayed top. The
offset uses post-scandoubler row units. Scaled HDMI gets zero OSD offset;
Direct Video follows the analog OSD. When `GROOVY_CRT_GEOMETRY` is absent,
the original port list & menu rendering remain unchanged.

Core-side geometry reaches both analog & scaled HDMI. In this framework,
`ce_hpix/hr_out/hg_out/hb_out/hhs_fix/hvs_fix/hde_emu` tap `vga_*_sl` before
the analog OSD. A stage inserted after that tap would stay off scaled HDMI,
including its sync changes. Historical README claims to the contrary do not
describe this routing.

## Storage and latency

The twelve-line RGB ring holds 2560 active pixels per line:
`12 * 2560 * 24 = 737280` bits, plus 192 tag bits & completion registers.
Twelve is the smallest even ring satisfying the selected seven-line range
plus four lines of margin. The even/odd banks each have one read & one write
port. Generic Yosys collection confirms two 368640-bit RGB memories, without
duplicated RGB storage for interpolation reads.

The source FIFO VRAM consists of eighteen destructive byte FIFOs. It cannot
reread source rows. Reusing DDR would require another memory reader & a new
deadline schedule, so this change leaves both existing memory paths intact.
The reader's lead/lag is bounded by nine lines. No additional full frame is
stored or queued. Invalid dimensions bypass geometry; invalid row tags black
the output & raise an internal underrun flag until the next field/reset.

The horizontal line buffers now use 4096 samples per bank, instead of 512;
their algorithm & option encodings stay unchanged. Totals exceeding 4096
disable horizontal scaling. The position counters use twelve bits. The
second CE also remains live at the two-clock scandoubled ratio, where the
old subtraction produced an unreachable count.

These bit counts are source calculations & generic inference results.
Quartus fitting is required for M10K packing, ALMs, DSP allocation & timing
slack. The implementation has not been fitted or tested on a MiSTer here.

## Validation

```sh
# In the corrected CRT Adjust checkout, with Icarus, Verilator and C++:
python3 tests/run_tests.py

# In Groovy, with the two adjacent forks and upstream HPS headers:
python3 tests/run_geometry_tests.py --main ../Main_MiSTer --crt-adjust ../MiSTer-CRT-Adjust
python3 tests/run_controller_tests.py ../reference_main

# Quartus 17 project; sys/sys.tcl generates build_id.v:
quartus_sh --flow compile Groovy
```

The tests check all 97 CRT Adjust horizontal offsets, both RTL variants &
modes, all vertical option decodes, all enlargement/reduction steps, RGB
values, CE ratios, ring wrap, missing-row blacking & reset recovery. Wider
than configured sources & invalid requests must bypass unchanged. The
2560-pixel matrix checks horizontal pixel order through the vertical scaler.

Groovy tests run the original timing generator through 240p, 480i & an odd
interlaced height, with both measured VSync phases. They compare every
existing horizontal factor against the integration-base RTL, exercise OSD
anchoring & compare unrelated-core OSD rendering with the macro disabled.
Main's actual status functions pass the new fields, SPI width, saved-byte
round trip & NES/Genesis legacy-option cases. Vendor FIFOs/PLLs & the VHDL
debug overlay use explicit simulation models during host elaboration.

The existing controller suite passes trigger calibration/polarity, digital
trigger fallback, L3/R3, both controller slots, registration & packet lengths.
The complete modified `emu` elaborates with inherited Quartus syntax
normalization & the inherited `PROCASSWIRE/BLKANDNBLK` frontend waivers.

`quartus_sh --flow compile Groovy` was attempted; the executable is not
installed in this environment. No RBF, M10K/ALM/DSP fit result or TimeQuest
slack was produced. Audio/network hardware behavior & FIFO timing under
physical DDR/network load remain hardware checks; source identity is not a
hardware validation claim.

## Hardware check

Build with the project's Quartus configuration before loading the core.
Record fitted memory, logic, DSP counts & worst timing slack. Compare 240p
& 480i against the integration-base RBF, first with V-Size zero & masking
off, then every size step while streaming. Check field order, scrolling,
VSync lock, small-porch clipping, mask edges, OSD position, scandoubler modes,
modeline changes, underrun recovery, audio & both controllers. Save settings
& reboot to check persistence. No physical CRT test has been performed here.
