# CRT read-address timing experiment

## Diagnosis & reference basis

Baseline: `fa4c2cd5c3e6772d6da99b8e9ed0dde533de0fd0` on
`experimental/crt-geometry-mlab-timing`. The supplied counter reports show
`ce_pix` feeding `line_now`, the first-output comparison, source-slot/bank
selection & an address adder before the distributed RAM read mux. The adder
output has fanout 1301. Worst setup is -0.921 ns at a 12.081 ns period.
The report lists 3.473 ns cell delay & 8.855 ns routing, with a -0.002 ns
interconnect correction, for 12.326 ns data delay.

Reference basis:

- Target `rtl/CRT/crt_vsize_fixed.sv`: `line_begin`, `first_source`, `line_now`,
  `first_output`, `position_next`, `advance_rows`, `next_aslot`, `slot_now`,
  `bslot`, `pair_ready`, `address_word`, `group_col` & `read_lane`.
- Target `rtl/CRT/crt_packed_ram.sv`: synchronous `q <= mem[ra]` & independent
  write enable; six 3072x40 instances, four MLAB & two M10K in `Groovy.sv`.
- Target `Groovy.sv`: `ce_pix`, the scaler inputs & native field feedback;
  `rtl/vga.v`: CE-qualified counters, `field`, `H_pulse_start`, `V_total` &
  half-line VSync. The reference `psakhis/Groovy_MiSTer/rtl/vga.v`, blob
  `c8f7f9a3cb2825a980dbe273f67b7bb4452c43a5`, confirms those native semantics.
  No receiver-visible timing or protocol change is intended or made.
- Target `Groovy.qsf`, `Groovy.sdc` & `sys/sys_top.sdc`: unchanged device,
  `MISTER_DEBUG_NOHDMI=1`, PLL timing, clock groups & existing exceptions.
- Uploaded `Groovy.fit(6).rpt`, `Groovy.map(6).rpt`, `Groovy.sta(2).rpt` &
  `crt_counter_worst_setup(1).txt` / `crt_counter_worst_hold(1).txt` provide
  the measured counter baseline below.

## Experiment A

Only the RAM read-address combinational logic changes. Calculate a line's
first-output decision, next read bank & complete line-start addresses before
the final `line_begin` mux. Calculate steady-state read addresses separately.
The immediate CE-qualified decision selects between those two addresses.

When `line_begin=1`, the original `line_now` is zero for `first_source`, or
the 16-bit `line_no+1` otherwise. Its original read word is zero on that same
edge. When `line_begin=0`, the original source slot is `aslot` & the read
word is the registered group counter, or zero after column saturation.
The revised expressions implement those same cases, including slot wrap,
blanking, field transitions & reset. No register, CE assumption or pipeline
cycle is added. `slot_now`, tag checking, writes, RGB interpolation & the
RAM helper are unchanged.

## Functional verification

```sh
python3 tests/run_crt_read_address_rtl.py
python3 tests/test_crt_group_address.py
bash tests/run_crt_group_address_rtl.sh
python3 tests/run_geometry_tests.py
python3 tests/run_controller_tests.py ../reference_main
```

The new RTL comparison extracts the exact fitted counter source from Git.
It checks both RAM addresses, write enables/data, synchronous RAM outputs,
source-row/tag state, packed lanes & every video/control output. The matrix
covers widths 1..6, 16, 31/32, 2559/2560 & over-capacity bypass; all -7..+7
steps; CE ratios 1/2/4/6/8/12/16 with gaps; first/last pixels & partial
groups; consecutive lines; both fields with half-line VSync; resets during
active video; geometry changes without reset; and 0/1/2 source-row advances.
Coverage assertions require active pixels, RAM writes & source-slot wrap.

The two matrices passed 2111136 + 4587681 clocks, with 2622026 active output
pixels & 522505 RAM writes. Existing counter RTL comparisons passed 57000
clocks for each of `MLAB_PARTS=0` & `2`. The independent counter model passed
210000 clocks. Geometry, OSD, full `emu` elaboration & controller/trigger
regressions passed. The geometry runner now includes the extracted RAM module;
the counter runner now names committed pre-counter parent `9c27398` rather
than the unavailable local reference `81490f1`.

Generic Yosys inference retains six unreplicated 3072x40 memories with clocked
read ports, four marked MLAB & two M10K. This is separate from Quartus mapping.

## FPGA measurements

Experiments A & C ran fresh synthesis, fitting, assembly & TimeQuest with Quartus
17.0.2 Lite, the existing seed/options & 12.081 ns clock. Every stage executed;
both runners completed successfully. Compilation success does not imply
setup timing closure. The supplied four-second counter compile
log used smart recompilation, so the counter baseline comes from its full fit
& STA reports rather than that log's elapsed time.

| Revision | Worst setup | Worst hold | Setup TNS | Critical path | Memory | Functional result | Fit |
|---|---:|---:|---:|---|---|---|---|
| Original divider, request history | -9.197 ns | +0.250 ns | Not supplied | Divider to MLAB address | Earlier report | Historical result | Reported passed |
| Counter, supplied reports | -0.921 ns | +0.247 ns | -23.800 ns | `ce_pix` to MLAB read mux | 553 M10Ks / 491520 MLAB bits | Rerun passed | Passed |
| Read-address Experiment A, `3d63b96` | -0.380 ns | +0.254 ns | -60.463 ns | `hb_d` to MLAB write decoder | 553 M10Ks / 491520 MLAB bits | Passed | Passed |
| Write-address Experiment C, `4390a9c` | -0.132 ns | +0.263 ns | -0.267 ns | `vga|hb` to MLAB read mux | 553 M10Ks / 491520 MLAB bits | Passed | Passed |

The original `ce_pix`-to-RAM cone now passes with +0.012 ns slack, 11.383 ns
data delay & six logic levels. Its reported cell/routing delays are
2.475/8.909 ns, with a -0.001 ns interconnect correction. The read cone is
shorter, but the complete design still fails setup. Worst-path setup improved
by 0.541 ns while global setup TNS worsened; it is not a timing-clean build.

All 30 worst A paths reach MLAB write endpoints. The worst is
`hb_d~0_OTERM3604DUPLICATE` through `line_begin` (fanout 393), `comb~5`
(232), `write_slot[0]`, `write_slot[2]`, `Add22` & the write decoder into
`packed_ram[1].odd_ram/.../lutrama2315~OBSERVABLEVIRTUALREGOUT0`.
Data delay is 11.286 ns: 2.922 ns cell, 8.360 ns routing & 0.004 ns
interconnect correction, with eight logic levels. Hold is +0.254 ns on
`vga|m_vcnt[2]~DUPLICATE` to `vga|m_vcnt[1]`. Fmax is 80.25 MHz.

Experiment A fits 33257 ALMs, 31281 registers, 21 DSPs, 553 M10Ks & 491520
MLAB bits. Synthesis retains 29111 registers, matching the counter baseline;
fitter duplication accounts for the different fitted register counts.
Quartus confirms all six 3072x40 RAMs with the original storage types.

Experiment B is skipped: the measured remaining top paths are writes.
Experiment C precomputes the two write-address cases before the same final
`line_begin` mux. It preserves the original write address even on blanking &
saturated non-writing columns. It changes neither write enables/data nor
storage, and adds no register. The same cycle-by-cycle RTL comparison runs
against the fitted counter baseline before a separate fresh C build.

## Experiment C results & remaining constraint

C retains the read change from A & passes the same 6698817-clock comparison,
including registered RAM data & every video output. The fitted RTL revision
is `4390a9c7707ae645289ba4c9777e5c55a859e8e0`. Fresh compilation finishes
with 32947 ALMs, 31418 fitted registers, 21 DSPs, 553 M10Ks & 491520 MLAB
bits. All six 3072x40 RAMs retain their original four-MLAB/two-M10K mapping;
the RAM helper, QSF, SDCs, native VGA, controllers & transport are unchanged.

Worst setup is -0.132 ns, hold +0.263 ns & setup TNS -0.267 ns. Fmax is
81.88 MHz against the unchanged 82.77 MHz target. The worst path has six
logic levels & 11.493 ns data delay: 2.834 ns cell, 8.657 ns routing &
0.002 ns interconnect correction. Clock skew is -0.520 ns. The exact path is:

- Launch: `emu:emu|vga:vga|hb`.
- Logic: `u_vsize|line_begin~0_Duplicate` (fanout 375), `wa[3]~3`
  (15401), `ra_odd[3]~3` (15400), MLAB LUTRAM output & two read-mux levels.
- Capture: `emu:emu|crt_vsize_fixed:u_vsize|crt_packed_ram:packed_ram[1].odd_ram|altdpram:distributed.mem_rtl_0|dpram_rro1:auto_generated|dataout_reg[39]_OTERM2535`.

The generated `wa[3]` name is synthesis naming within a shared address cone;
the endpoint & LUTRAM read-mux chain identify this as a read path. The old
source-slot selection/adder chain no longer appears on this worst path.
The remaining constraint is address broadcast & MLAB read-mux routing, with
15400 fanout on the address bit. The targeted `ce_pix`-to-RAM path is
-0.021 ns, with 11.382 ns data delay, six levels & 2.718/8.663 ns cell/routing
delay plus 0.001 ns interconnect correction. It passed narrowly in A but
fails in C's different physical placement; the CE path has shortened, not
been eliminated.

The 30-path report contains five failing endpoints: two odd-bank read
registers at -0.132/-0.123 ns & three `state[0]` to
`lz4_compressed_bytes[29]`, `[30]` & `[29]~DUPLICATE` paths at -0.004 ns.
The first LZ4 path has six levels, 11.522 ns data delay, 3.060 ns cell delay,
8.463 ns routing & -0.001 ns interconnect correction. This transport logic
has not been changed. Worst hold is `u_edge_mask|x[10]~DUPLICATE` to
`u_edge_mask|x[10]`, +0.263 ns.

This revision does not close setup. The next measured candidate is bank-local
copies of the final address mux/control, followed by inspection that Quartus
has retained separate drivers instead of merging the address broadcast.
Such a trial must preserve the same clock-edge addresses & synchronous RAM
latency, repeat these RTL tests & obtain another full physical build.
No local-driver duplication has been implemented or measured in this revision.
The -0.004 ns transport paths must also pass before declaring closure.

## Constraints & inherited warnings

TimeQuest reports zero unconstrained or illegal clocks. It still reports
three unconstrained input ports / 13 paths & 48 output ports / 66 paths,
matching the supplied baseline. Inputs are `HDMI_I2C_SDA`, `IO_SDA` &
`SDCD_SPDIF`; outputs include HDMI, shared audio & expansion pins. These
board I/O paths need interface-specific review; internal clock coverage does
not prove those external interfaces meet timing.

Unmatched filters include removed HDMI PLL clocks, `spi|sclk_out`, `VSET`,
`hcalc`, `wcalc`, HDMI dimensions & scaler fields absent from this CRT-only
netlist. These warnings do not exempt the active CRT clock: its setup paths
are constrained & reported as failing. No false paths, multicycle exceptions,
clock periods or SDC assignments were added or weakened.

`hdmi_vs` remains undriven in the HDMI-disabled build (map warnings 10858 &
10030 at `sys_top.v:679`). Ignored fitter assignments include unused HDMI /
SDRAM fast I/O registers, removed HDMI PLL settings & the absent SPI HPS
location. These inherited warnings are separate from the RTL timing change.

## Reproduction

Run `bash tests/run_crt_read_address_quartus.sh` with Quartus 17.0.2 on PATH.
The runner copies the source into a new build directory without prior DBs,
then runs the full compile & exports 30 setup / 10 hold paths with routing.
It checks that synthesis, fitting, assembly & TimeQuest actually succeeded.
It also exports unconstrained paths. It never changes project constraints.

## Hardware check

After internal setup/hold verification, compare CRT VGA against the counter
build in 240p & alternating 480i. Exercise resizing while streaming, both
field parities, horizontal size/position, vertical position, masks, OSD,
runtime modeline changes, stream/reset recovery, audio & both controllers.
Confirm analog triggers still work. This experiment retains the CRT-only
HDMI-disabled configuration; physical CRT validation has not occurred here.
