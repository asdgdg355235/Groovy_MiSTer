# Rejected Q25 V1 & recovery controls

Reference basis: exact R0 3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a,
V1 26cb6b9b7528f14a7cbeed92740fa28c2c23fa1e & supplied native archives.
`results/v1-rejection.json` records archive/report hashes, both complete hardware
hash sets, generated input identity, endpoint summaries & the V1 change inventory.
Original archives remain sealed. No RTL or project assignment changes are retained here.

| Slow corner | R0 WNS / TNS / failures | V1 WNS / TNS / failures |
|---|---|---|
| 100 C | -0.077 / -0.094 / 2 | -0.218 / -2.843 / 19 |
| -40 C | -0.097 / -0.302 / 4 | -0.236 / -1.238 / 8 |
| 85 C | -0.001 / -0.001 / 1 | -0.060 / -0.411 / 10 |
| 0 C | +0.125 / 0 / 0 | -0.046 / -0.074 / 3 |

All fast corners pass. V1 holds/recovery/removal/pulse checks pass. V1 minimum hold
is +0.118 ns. R0 uses 32,750 ALMs / 31,206 registers; V1 uses 32,858 / 31,178.
Both retain 489 M10Ks, 491,520 MLAB bits & four MLAB/two M10K CRT banks.

Only rtl/vga.v differs in the approved hardware hashes. V1's fresh-snapshot patch,
variants/V1.json, variants.py, source-variant runner/control/compare allowances,
blanking proof & VGA differential test belong to the rejected experiment.
The published V1 branch remains intact. The recovery branch starts at independent
R0-PHYS 7041ad2, retaining graph/logical-address diagnostics without those allowances.
R0 hash validation remains unchanged. C1/A1/D1 branch infrastructure is preserved
on its original references; it is not imported as an approved physical experiment.

## VGA path

Cold R0 worst VGA/root path: 7 levels, 7.719 ns cell, 4.148 ns routing,
-0.110 ns skew. V1: 8 levels, 8.272 ns cell, 3.733 ns routing, -0.112 ns skew.
Cell delay rises 0.553 ns; route delay falls 0.415 ns. Serial total/comparison/
counter-selection/root Add17 work survives in the fitted path. The retimed launch
changes; these are path-family measurements, not identical-register subtraction.
Root Add17 is the frame-skip operand, not a field-height register. Precise D/Q
correspondence remains a gate before choosing a register-control assignment.

Before the fit, V1 passed finite-width Z3 expression equivalence, Verilog-2001
syntax, top elaboration, 180,000-clock VGA differential comparison & the recorded
CRT/LZ4/delta regressions. Those checks establish neither fitted mapping nor timing.
The native compilation succeeds, diagnostic exports pass, but timing fails with
exit code 4. Do not repair V1 by stacking LZ4/CRT rewrites on it.

## LZ4 window write

At hot R0, all 1,024 window data-input capture endpoints pass; worst is +0.618 ns,
block_read_total[10] to ram_block1a44~porta_datain_reg5, 11.099 ns data delay,
8 logic levels & -0.164 ns skew. V1 worst is -0.218 ns, block_read_total[12] to
ram_block1a54~porta_datain_reg0, 11.915 ns data delay & -0.184 ns skew.
V1 detailed data delay comprises 2.740 ns cell & 9.174 ns routing, through
LessThan12 & window_write_value selection. The two endpoint rows do not identify
the same physical bit/packed RAM. R0's bounded counter-launch detail instead covers
other positive paths. Therefore R0 window-write cell/routing decomposition,
write-address/enable detail & mapped-register correspondence remain pending.

The complete endpoint inventory establishes positive R0 timing. It does not
establish that V1 changed only routing: launches, captures & depth also changed.
Preserve R0 LZ4. Fresh focused read-only paths now cover window capture, counters,
address & state in both directions needed to trace actual memory input ports.

## CRT read selection

Hot R0 hb launches at FF_X36_Y22_N59, fanout 34, into bank-1 even dataout capture
FF_X53_Y36_N17: -0.077 ns, 2.590 ns cell, 8.892 ns routing, -0.475 ns skew.
Its upper-selection advance_rows path is -0.017 ns.
Hot V1 bank-1 even worst launches wcol[13]~DUPLICATE, with -0.045 ns,
3.342 ns cell, 8.096 ns routing, 7 levels & -0.489 ns skew.
V1's bounded hb report contains a bank-1 even capture at +0.561 ns. Its overall
worst hb-family path is +0.443 ns into bank-0 even, not the original bank-1 capture.
Thus there is measured hb-family improvement, but no proven cycle-level
correspondence between those retimed endpoints. The original dependency is not
classified as removed. New row & LZ4 failures reject V1 despite this local result.

C1 remains blocked pending full low-bit loads, upper mux/capture connections,
native pin-to-cell binding, legal site, installed Lite assignment scope & exact
post-map target matching. Fitted coordinates are observations, not legal recipes.

## Reproduce the offline analysis

Restore each archive with tests/restart/package_reports.py --restore into a new
folder. This verifies lossless parts & full-file hashes. Then run:

```bash
python3 tests/physical/recovery_analysis.py \
  /path/to/restored-R0/output_files /path/to/restored-V1/output_files \
  /path/to/new-comparison \
  --archive /path/to/original-R0-reports.tar.gz \
  --archive /path/to/original-V1-reports.tar.gz
```

The tool rejects wrong source identities, missing eight-corner inventories,
endpoint/TNS discrepancies, generated-byte drift & hardware changes beyond V1's
reviewed VGA difference. It retains positive as well as negative path observations
& writes complete bank/window physical-port subsets separately. It never guesses
cross-build identity from an edge ID or generated register name.

The complete observed pin-arc subsets also establish these fitted driver changes:

| Driver | R0 location / loads | V1 location / loads |
|---|---|---|
| crt_read_1_even_bit3 | X37_Y35_N24 / 3840 | X43_Y22_N36 / 3840 |
| local_ra_even[10]~2 | X35_Y22_N57 / 1302 | X42_Y16_N51 / 1301 |
| wa[3]~3 | X37_Y22_N18 / 15406 | X42_Y22_N48 / 15406 |

These are physical pin observations, not legal location-assignment targets.
recovery_analysis.py retains every selected pin-level arc in separate derived
TSVs, removes exact duplicates & rejects incomplete expected fanout. Parallel
arcs remain distinct. Full load locations are retained in comparison.json;
compact source locations/counts & derived hashes are committed in the rejection
record. Original R0 hb was not a seed of the old complete-selected graph, so
its complete direct-load footprint still requires the expanded R0-PHYS export.
