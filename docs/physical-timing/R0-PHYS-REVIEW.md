# Returned Q25 R0 physical review

Reference basis: native export by 9275020236af5f37068073b73f2b76c3cc534280
from fitted R0 3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a.
Archive SHA-256: ec067377ace04da1e7ce444b91f6dcd4639a4e8e11f9c6331f8b41f63cb29011.

The return has exit code 0, all eight operating corners, all nine focused
families/corner & no native query errors. Fresh graph validation finds 592,564
unique edges, no duplicate edges, 28 explicit zero-fanout sources & no unresolved
logical address bits. Original timing report bytes remain unchanged. Setup still
fails; this read-only export is not a new physical implementation.

## Root operand correspondence

Pre-synthesis emu:emu|Add17 is a combinational source at Groovy.sv:1078.
Mapped Add17 input edges cover every vga:vga|v_cnt bit 0 through 15.
Fitted Add17~5/SUMOUT reaches two observed D inputs:

| Fitted register | Observed Q consumer |
|---|---|
| Add17~5_NEW_REG5722 | Mult0~8 AY[16] |
| Add17~5_OTERM5723DUPLICATE | Add18~5 DATAB |

Both observed CLK inputs use the video divclk[0]~CLKENA0 OUTCLK. The unchanged
v_cnt[15] register has observed D & CLK edges; other counter logic is retimed.
These connections establish the root increment/multiplier cone. They do not
prove complete original-register ancestry or approve a retiming assignment.

The next independent source experiment can change the root next-line operand,
shared by the line-skip decision & pixel-count update. Keep VGA counter/total
logic unchanged. No physical assignment has verified installed Lite scope yet.

## LZ4 & CRT

The previously missing hot R0 window-write detail is now observed: +0.618 ns,
3.063 ns cell, 8.039 ns routing, 8 levels, -0.164 ns skew. V1 was -0.218 ns,
2.740 ns cell, 9.174 ns routing, 7 levels, -0.184 ns skew, on a different
launch/packed capture. This is a family comparison, not an identical-bit delta.
R0 LZ4 stays unchanged.

The hb pin footprint & all 3,840 low-bit driver loads are now available. Lower
MLAB address selection & upper output mux selection remain separate layers.
Observed locations still do not establish legal target sites or supported
assignment scope. C1 remains blocked; no bank relocation or replication is added.
Metadata tap ancestry & the existing clock/I/O coverage findings remain open.

## Reproduce without Quartus

Restore the supplied archive with tests/restart/package_reports.py --restore.
Run tests/physical/review_r0_phys.py RESTORED/output_files NEW_REVIEW_DIR.
The output retains raw/normalized hashes, complete selected load arcs & reviewed
D/CLK/Q witnesses. The committed evidence JSON & native excerpt fixture identify
the original report hashes. Negative tests reject missing inputs, clocks,
consumers & incorrect source correspondence.
