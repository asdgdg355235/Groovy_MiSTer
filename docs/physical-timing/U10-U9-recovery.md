# U10/U9 recovery decisions

Control: 3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a.
Measured experiment source: 9b832f86c44ee4f43cb4eab63202eca77dda8b4b.
All five supplied files were read. Both archives passed complete manifest/part
hash verification, including their two partitioned files each. See
results/upper-regressions/integrity.txt & summary.json. The TSV retains every
negative setup endpoint: 210 U10 corner-endpoint records & 608 U9 records.
These are not counts of unique RTL registers across corners.

| Slow corner | R0 WNS / TNS / count | U10 | U9 |
| --- | --- | --- | --- |
| 100 C | -.077 / -.094 / 2 | -.594 / -13.314 / 76 | -.431 / -44.629 / 278 |
| -40 C | -.097 / -.302 / 4 | -.590 / -9.226 / 44 | -.320 / -6.011 / 81 |
| 85 C | -.001 / -.001 / 1 | -.562 / -8.600 / 59 | -.330 / -21.865 / 222 |
| 0 C | +.125 / 0 / 0 | -.451 / -4.659 / 31 | -.132 / -.668 / 27 |

All four fast corners pass. Ancillary timing checks pass in the exported
comparisons. These are valid applied physical experiments, rejected for timing;
V3 has no compilation or timing result. Its archive contains only the blocked
result & control evidence manifest, not additional register ancestry.

## Physical changes established by the reports

U10's original driver moved from LABCELL_X35_Y22_N57 to
LABCELL_X50_Y22_N33; the copy is LABCELL_X50_Y22_N30. They occupy the same LAB.
The original retains 662 loads; the copy has 641, including 640 mux pins.
U9's copy is LABCELL_X57_Y32_N9 & its remaining driver is
LABCELL_X57_Y32_N6, also the same LAB. The copy has 642 loads, including
640 mux pins; the original retains 662. Logical bank splitting did not establish
physical separation from the shared source region.

Both use a whole-bank destination wildcard, but the mapped resolver establishes
that the selected source's bank-specific consumers are upper read-mux pins.
There is no observed evidence of accidentally duplicating the whole address
network. Both copies still depend on shared next_aslot/control LUTs. Their six
input connections are retained in the native application_cmp.json. Their
presence proves upstream dependencies remain; it does not prove congestion.

The worst hot U10 path is hb_d~0_OTERM4228 to bank-1 even l6_w18 output capture:
3.198 ns cell, 8.835 ns routing, -.445 ns skew, seven levels, -.594 ns slack.
The hot R0 worst path instead has 2.590 ns cell, 8.892 ns routing, -.475 ns skew,
six levels & -.077 ns slack. Those are different physical launch/capture pairs;
subtracting them is a worst-path comparison, not a matched-path improvement.

U9's worst hot path is hb_d~0_OTERM4228 to bank-0 EVEN l6_w4 output capture:
2.862 ns cell, 8.958 ns routing, -.493 ns skew, seven levels, -.431 ns slack.
Another U9 path into a bank-1 even observable memory register has -.865 ns skew.
It is therefore incorrect to attribute every lost picosecond to data routing.

At 100 C, 49/76 U10 negative endpoints launch from hb_d~0_OTERM4228; U9 has
266/278 from that launch. At -40 C, U10 also has ten hb~DUPLICATE launches;
U9 has 71/81 hb_d launches & nine VGA Add1~97 launches. Repeated endpoints
share launch/control & read-selection structures. The full TSV preserves DDR,
RGB, pixel-decode, row-arithmetic & generated arithmetic captures as well.
Physical generated-register names are not original RTL ancestry.

R0/U10/U9 use 32750/32676/32773 ALMs & 31206/31131/31174 registers. Native
retiming report rows are 2504/2505/2505. A one-row difference is not proof that
one specific boundary moved. U10's ALM count decreased while timing worsened;
there is no defensible inference of routing congestion from resource totals.
All retain 489 M10Ks, 491520 MLAB bits & the four-MLAB/two-M10K bank mixture.

## Target-path outcome & evidence boundary

The full negative detail contains a U10 cold copy-to-l6_w12 mux segment of
3.491 ns (3.471 ns at 0 C). R0's motivating 3.629 ns segment is at 100 C &
not the same destination. This is not a measured gain. U9's copy does not
occur in the exported negative detailed paths. That absence does not establish
positive slack through the copy: the inventories choose the worst launch for
each capture & do not enumerate every alternate through-path.

The complete hot endpoint distribution retains the bank-1 even l6_w5_n0~20
mux family: R0 -.017 ns / 11.464 ns data / -.434 ns skew; U10 -.017 ns /
11.508 ns data / -.390 ns skew. Its worst launch changed from advance_rows
into retimed hb_d. This endpoint-family observation shows unchanged slack,
not the intended gain. U9 reports +.416 ns for that EVEN-bank mux family,
launched by aslot[0]; it is not U9's ODD-bank bit-9 target. Renamed register
ancestry still prevents treating these as formally matched physical registers.

The first observable changes are selector/source placement, hb/hb_d launch
packing & capture footprint changes. The original complete R0 native graph is
not in these five attachments. Embedded comparison data provides original
critical metrics & selected driver locations, but not full R0 load geometry.
Exact causal register movement, cell displacement, routed wire topology &
matched original-target slack therefore need read-only native queries.
Do not equate bounding-box distance with routed delay or infer ancestry from
OTERM suffixes. No coordinate is approved as a placement assignment.

## Decisions & next work

U10: REDESIGN, evidence-gated. R0 has a real failing upper-selection path
(-.017 ns at 100 C), but the present whole-bank duplicate has no demonstrated
matched-path timing gain. Do not repeat or integrate it. A narrower mux-layer
partition or legal placement factor is conditional on complete through-path
and upstream/downstream geometry evidence, not ready to fit.

U9: ABANDON THIS DUPLICATION MECHANISM for the present closure sequence.
R0's negative inventory does not establish an odd-bank bit-9 target failure;
its motivating negative path came from rejected V2. Current results provide
no demonstrated target gain & introduce hundreds of even-bank failures.
Retain the mechanism as experimental evidence, not as a prerequisite to closure.

Priority 1: V3 read-only counter/root correspondence & native option evidence.
Priority 2: paired R0/U10 through-bit-10 path queries, before choosing any new
CRT assignment. Priority 3: one evidence-supported CRT mux/capture boundary
factor. Defer U9 unless an accepted control exposes an actual bit-9 bottleneck.
No new optimization build is justified by these archives alone. Use strategy
A (R0 hardware) plus independent strategy C (V3); strategy B remains gated.

The new report_upper_recovery.tcl queries all endpoint slacks through actual
upper selector pins, including positive paths, plus both VGA/root directions
& CRT hb/advance launches. It retains bounded full-routing detail separately.
Native support remains pending execution by the user; unmatched queries are
recorded, never interpreted as passing. It performs no synthesis or fitting.

V3's source is rtl/vga.v vertical counter (reset, later soft-reset priority,
ce_pix & h_cnt qualification), feeding Groovy.sv S_Blit_Auto_Skip line 1078.
Root Add17 belongs to the frame-skip product, not field-height arithmetic.
The reviewed fixture establishes source family & observed D/CLK/Q, not original
v_cnt-to-retimed-register ancestry. Do not activate an assignment from it alone.

A separate V3 diagnostic revision adds source-correspondence & all-eight-corner
path queries to the existing copied-database runner. It also corrects the
candidate enum from NEVER_ALLOW to the documented spaced NEVER ALLOW. Vendor
Standard documentation 683230/18.1 describes instance scope; it does not certify
25.1 Lite support. A hashed native scope/value certificate & reviewed ancestry
remain mandatory. Neither global retiming nor RTL is changed.

Accept a future factor only if its intended physical effect is observed,
its targeted failing R0 dependency improves, no required corner's WNS/TNS/count
regresses, no new failing family appears & ancillary/resource/cycle gates pass.
Combine no factors until independent acceptance. Coverage & real CRT hardware
qualification remain separate from setup closure.
