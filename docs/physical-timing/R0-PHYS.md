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

## Recovery update

The runner now opens a fresh, non-hardlinked copy of the existing source/database
in a sibling `R0_PHYS-native-query` directory. It never launches map/fit/assembly.
The original fitted database & sealed reports remain untouched even if a native
API writes cache metadata. This copy requires additional local disk space. Keep
it for debugging or remove it after reviewing the export archive.

Fresh mapped AND fitted atoms include LZ4 window/state, VGA totals/counters &
root Add17/Mult0/Add18 consumers. Targeted STA reports cover every corner,
complete filtered endpoint inventories & eight detailed paths per family,
including positive LZ4 window captures, address/control & CRT hb/wcol/advance.
All path detail includes native routing, locations & clock skew.

Fresh graph/atom data now override historical data only in corrected_diagnostics.
The earlier helper instead reassembled the historical exports. The fresh seal
records exactly which raw inputs were used. Missing/unmatched native queries
produce exit code 3 with the partial archive retained; they cannot reuse an old
successful diagnostic status. Source-location observations remain distinct from
register ancestry & functional capture-enable proof.

Use --prepare-only for command/schema preparation with no vendor lookup. Run the
full helper only locally. Both R0_PHYS & its archive must be new; if a previous
attempt exists, select another parent directory or preserve/rename that attempt.
The archive is Groovy-Q25-R0-PHYS-reports.tar.gz beside the requested output.
Only the user-side read-only export is pending, not another R0 compilation.
