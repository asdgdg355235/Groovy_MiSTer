# Offline Q25 R0 diagnostic repair

Reference basis: exact 3b8d1ed tests/physical/diagnostics.py, report_fanout.tcl &
the supplied R0 native atom/STA exports. Hardware & timing inputs are unchanged.

Run without Quartus:

```bash
python3 tests/physical/repair_r0.py \
  /path/to/Groovy-Q25-R0-postmapgate-reports.tar.gz \
  ../Groovy-Q25-R0-corrected
```

The destination must be new. The original archive & its failed status remain
unchanged. `output_files/corrected_diagnostics` contains a new seal, normalized
fanout graph, per-source accounting, the 72-key summary & registered selector
chains. Original native reports & all timing distributions remain in the package.
The corrected archive uses the existing lossless 200 MiB member cap.

`fanout_normalization.json` binds raw/normalized SHA-256 hashes. Only exact rows
are removed. Conflicting IDs, type/location disagreements, inconsistent fanout &
missing arcs fail validation. Distinct pins & parallel arcs survive. Historical
zero-edge visits remain unnamed; future exports record every processed source,
including zero fanout, plus native aliases. Native IDs are local to one netlist.

Logical dependencies crossing one observed SDATA/Q selector register require a
mapped connection, the matching logical-bit RAM driver, a unique observed clock
& a fitted Q-to-read-mux connection. Register crossings & capture-cycle offset
are reported; capture-enable/function equivalence remains pending. No physical
MLAB pins above bit 4 are invented. Names do not establish pixel-bit semantics.

This repair does not change setup timing or qualify I/O/CDC or CRT hardware.
