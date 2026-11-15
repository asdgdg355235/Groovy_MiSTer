# V3 evidence recovery

This branch starts from the unchanged 9b832f8 hardware. It contains no U10/U9
assignment, VGA arithmetic rewrite, global retiming change or active V3 factor.
V3's supplied archive records BLOCKED, not a failed compilation.

The previous candidate validator incorrectly restricted ADV_NETLIST_OPT_ALLOWED
to NEVER_ALLOW. Standard vendor documentation spells the enum NEVER ALLOW
(with a space). The renderer braces this value. Correcting the spelling is not
proof of Quartus 25.1 Lite instance-register support; the native certificate
and original/fitted register ancestry gates remain mandatory.

The copied-database query runner now exports pre-synthesis/mapped/fitted source
correspondence, map/cmp D/CLK/Q ports & eight-corner upper/VGA/root path data.
It can also read the already-fitted failed U10/U9 projects, selected explicitly
with --experiment. No map, fit or assembly operation is invoked. --prepare-only
never probes a vendor executable. Queries use the measured adapters; native
acceptance of new through filters remains to be checked locally.

A later reviewed recipe can supply evidence.register_inventory, with file,
SHA-256 & explanation, beside its other proof files. The supplemental inventory
uses stage/name/type fields from native source_correspondence.tsv (short_name
is optional). This avoids editing the sealed original R0 inventory to add new
observations. Both original & fitted register identities must still exist in
the supplied observations. Other required review fields remain unchanged.

Run from a clean checkout of this branch:

```bash
python3 tests/physical/run_v3_diagnostics.py \
 --build-dir /home/taichi/src/groovy-crt-build/Groovy-Q25-R0-postmapgate \
 --output /home/taichi/src/groovy-crt-build/Groovy-Q25-R0-boundary-recovery \
 --quartus-bin /home/taichi/altera_lite/25.1std/quartus/bin
```

Repeat with --experiment U10 or U9, the corresponding existing batch build
path & a different new output directory. Never point at a candidate database
while labelling it R0. Each command archives partial query output on failure.
An optional --single-assignment-query ADV_NETLIST_OPT_ALLOWED isolates metadata
inspection of that one name. It never enumerates all assignment names.

Return all three *-reports.tar.gz packages. Review through-selector route delay,
hb/hb_d capture boundaries, reset/CE/initialization & original v_cnt ancestry.
An unmatched query is missing evidence, not a closed path. Native metadata
alone does not approve assignment scope or demonstrate a compiler effect.

Source basis: rtl/vga.v vertical counter always block, Groovy.sv
S_Blit_Auto_Skip, reviewed root_operand_r0.json & source correspondence adapter.
Vendor reference: docs.altera.com/r/docs/683230/18.1/quartus-prime-standard-edition-user-guide-design-optimization/synthesis-netlist-optimizations.
The edition/version difference is why native Lite approval remains required.
