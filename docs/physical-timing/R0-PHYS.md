# Q25 R0 read-only physical exports

Reference basis: exact 3b8d1ed native atoms, project/name & STA interfaces. This
branch includes the diagnostic repairs, with unchanged hardware. Assignment
enumeration remains disabled; no location assignment is distributed.

On the user's machine, in this committed checkout:

```bash
python3 tests/physical/run_r0_phys.py \
  --build-dir /home/taichi/src/groovy-crt-build/Groovy-Q25-R0-postmapgate \
  --output /home/taichi/src/groovy-crt-build/Groovy-Q25-R0-postmapgate/output_files/R0_PHYS \
  --quartus-bin /home/taichi/altera_lite/25.1std/quartus/bin
```

The runner verifies exact R0 provenance & generated inputs, source drift & tool
version, then opens the existing mapped/fitted database for exports only. It
invokes no map, fit, assembly, flow, project-generation, assignment-setting or
assignment-export operation. Project-file hashes must remain unchanged.

`--prepare-only` works with an extracted R0 report directory & does not look up,
probe or launch vendor programs. It writes the proposed commands & request hashes.

Atom exports retain all selected input AND output edges & native IDs. Targeted
source-location observations cover VGA totals/counters, root frame-skip arithmetic
& CRT bank selectors. The fanout export includes hb, native token aliases & zero
sources. placement_binding.tsv observes an output pin's host cell where the native
query succeeds; it does not establish a legal placement site. Unknown correspondence,
legal sites & assignment applicability remain explicitly pending.

Original reports are not overwritten. The new archive is written next to the
requested output directory as Groovy-Q25-R0-PHYS-reports.tar.gz. Both paths must
be new. It retains partial results on failure, original provenance/timing & derived
corrected diagnostics. Do not compile the old R0 again.

Return that archive before selecting a C1 site or register-preservation control.
