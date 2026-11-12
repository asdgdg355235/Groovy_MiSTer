# Targeted eight-corner candidate

The +0.177 ns archive is a Slow 1100 mV 100 C measurement only. Its 866
manifest-verified files remain in the separate read-only reference extraction.
Exact archived QSFs are preserved as inert text in docs/evidence/plus0177_*;
archived RTL matches ancestor 00136c5. The separate HPS-corrected measured
reference is c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17, also retained as local
baseline/targeted-hps-fixed-c8d4b38. That build measures -0.089 ns at slow
100 C & -0.161 ns at slow -40 C. It is not the +0.177 ns physical result.
Both sets of reports remain untouched. This candidate starts from c8d4b38,
not from an assumed passing commit or a fitter database.

`evidence/targeted_path_mapping.json` preserves all 13 negative corner-path
records (nine unique launch/capture pairs), source/capture names, cell/routing
delays, fanout, locations & mapped cell chains from the user's reports.
No fitted database was included, so the mapping below uses the supplied atom
and detailed path exports, not a new vendor-netlist inspection.

| Physical path | Source correspondence & limit |
|---|---|
| delay_lines[1] -> advance_rows~NEW_REG / Add2 | CRT first-output/line qualification, position mux, Add1 carry chain, row difference; a retimed arithmetic capture, not an RTL advance_rows register. |
| wcol[14]~DUPLICATE -> bank 0 odd dataout | CRT column range -> current address -> local read driver -> MLAB -> retimed data output. |
| hb_d~NEW_REG -> bank 1 odd dataout | Retimed blanking control -> line-begin/address selection -> MLAB output. Original hb_d updates only on CE. |
| delta_index[3] -> r_vram_in2[2] | 128x64 delta buffer selection -> byte addition in lz4 output -> decode_pixel -> pixel register. Launch fanout 914. |
| PoC_V[0]~DUPLICATE -> Add17~5 and duplicate | Confirmed vga Add1, Add0, Add54, LessThan19 then root Add17 carry chain. V_total/vertical terminal logic participates. Exact ultimate RTL register behind root Add17 is ambiguous after retiming; it is not evidence for changing root field-height arithmetic. |
| hb_d~NEW_REG -> dv_hs1 delay RAM datain7 | Confirmed line_begin -> line_now -> Equal7 -> tag address -> Mux2 -> Equal10 -> comb1 -> control~9. Likely retimed/packed control metadata; the physical RAM name does not prove this is the literal HS bit. Preserve all sync/control clocks. |

Reference basis: measured sources & path exports; approved psakhis/Groovy_MiSTer
rtl/vga.v V_total and terminal-counter semantics, rtl/lz4.v per-byte delta
addition; s3gfaultx/mistercast-linux src/stream/GroovyMister.cpp::sendFrame
LZ4 block/payload behavior. No sender or packet representation changes.

No physical timing gain is claimed. The clock, seed, QSF settings, HPS placement,
inactive HDMI tie, six memories & final driver resolution remain fixed.
