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

## Selected source changes

1. Row advance: keep the original 32-bit position update. Form a 17-bit
fractional sum, integer step plus carry, then correct bit 16 using the overflow
of the integer-position sum. Low advance bits no longer wait for a full
position addition followed by subtraction. This preserves the 17-bit result
for all 32-bit position/step values, including increment 65536.
2. Qualification: compute the upcoming 16-bit line number & its output window
before the line-begin selection. Existing position/source/aslot updates use
that already-established branch directly. No new state or pipeline stage.
3. Read addresses: production 512-word rows use nonoverlapping row/9-bit-column
fields. All reachable wcol/group/lane states, saturation, line-start zero & all
four-bit slot values are covered. Other parameterizations keep address_word.
Writes are untouched. Selected alternative A keeps complete current/next-line
addresses ahead of the final six muxes. `read-add` restores alternative B's
qualified-column/full-adder calculation, without other changes. No claim about
fitted routing distance follows from this source simplification.
4. Delta: sixteen eight-word read groups followed by a final selector; keep
only group outputs. Existing buffer state, writes, index updates, LZ4 decoder,
eight modulo-256 byte additions & decode_pixel are unchanged. Map/fit must
establish group retention, fanout & whether memory inference remains acceptable.
5. PoC_V: detailed paths establish vga Add1/Add0/Add54/LessThan19 predecessors.
Precompute the small blanking/parity term before adding V, with explicit signed
extension for zero-blanking underflow. Move terminal subtraction off this cone
using a 17-bit counter increment comparison, preserving V_total==0 behavior.
Root field-height arithmetic is deliberately unchanged: the trace does not
support identifying Add17 as that expression. No guessed retiming target added.
6. hb_d: compute current/upcoming row readiness in parallel before final
line-begin selection. This removes hb_d-derived tag-address selection ahead of
lookup/comparison on the observed control~9 cone. The tag/complete arrays and
all RGB/sync/control pipeline registers stay unchanged. No HS edge is moved.
The post-fit dv_hs1 endpoint may be a packed metadata bit; measure its new path
rather than assuming the name proves a sync-bit dependency.

No new QSF timing exceptions or register-duplication assignments were introduced.
No global retiming/physical-synthesis options changed. A narrow preservation
experiment is deferred until a new map/fit confirms retiming of identified
source registers still recreates the failing chain.

## Verification

Run independent tests with Verilator, Icarus, g++, Tcl & Python z3-solver:

```bash
python3 tests/prove_targeted_arithmetic.py
python3 tests/run_targeted_arithmetic_rtl.py
python3 tests/run_delta_selection_tests.py
python3 tests/run_timing_candidate_tests.py --main ../validation-main
```

Arithmetic SMT covers unrestricted row arithmetic, upcoming-line wrap, lookup
selection distribution, read row/column fields, VGA blanking/parity arithmetic
& terminal comparison. Reduced-width row arithmetic is exhaustive for half
widths 1..4. Reachable production column transitions are checked through
saturation. Actual compiled RTL receives 100,000 arithmetic vectors (including
zero/max/overflow boundaries) & 8,192 read-field combinations.

The focused delta harness extracts the actual candidate selector, unchanged
LZ4 byte assignments & decode_pixel task. It compares 17,993 write/consume cycles
with the baseline for RGB565, RGB888, RGBA888 & the default mode encoding,
partial/full refills, rollover, stalls & reset/restart. It is not a simulation
of the entire DDR/transport state machine; a source guard confirms that the
surrounding root FSM remains byte-identical to c8d4b38.

The existing CRT suite compares all six read/write ports, synchronous RAM data,
registered RGB & all sync/CE/field metadata for 6,698,817 clocks. Seven VGA mode
cases cover progressive/interlaced parity, runtime geometry/mode changes & reset.
The final full suite passed: 20 unit tests, 114,000 legacy RTL address cycles,
74 golden LZ4 packets with 65,536 delta-byte input pairs per macro configuration,
OSD/H-size, emu
elaboration and HPS/controller tests. Simulation models do not establish vendor
RAM inference or physical timing. The existing menu.cpp host pointer-cast warning
remains. One Verilator frontend internal fault on an intermediate qualification
run was retried with debug enabled; the completed focused & final suite results
are recorded separately from that tool failure. A legacy Icarus comparison also
caught an intermediate helper-function sensitivity mismatch. The final RTL uses
explicit tag/complete array reads; both simulators are rerun on that correction.

## Compact eight-corner reports

`report_timing_closure.tcl` retains unlimited complete negative endpoint tables
& routed failure paths for setup/hold/recovery/removal. Positive global/family
samples are bounded at ten, including LZ4 launch paths. Unmatched filters remain
explicit review items, never evidence that a renamed family passed.

Quartus 17 report_min_pulse_width has no slack filter. Its documented worst-first
ordering permits adaptive summary queries: start at 32, double while every
returned row fails, stop on exhaustion or a nonnegative row. Thus every negative
pulse/period check is retained, with full details for exactly the failing prefix.
`min_pulse_coverage.tsv` records count, negative count, WNS & completion per corner.
The validator rejects missing/mismatched coverage or explicit truncation markers.
Reference: https://resources.altera.com/quartushelp/17.0/tafs/tafs/tcl_pkg_sta_ver_1.0_cmd_report_min_pulse_width.htm

Plain-Tcl stand-ins test eight operating-condition iterations, 45 setup failures
per corner, pulse queries expanding past 70 failures, bounded positive samples,
complete failing pulse details, and rejection of malformed/truncated/unsorted
pulse reports. These are reporter tests, not Quartus execution.

## User-run builds

Use the pushed integrated commit in a fresh detached worktree. From that checkout:

```bash
export CRT_READ_BUILD_DIR="$(realpath ..)/Groovy-targeted-candidate-build"
bash tests/run_crt_read_address_quartus.sh candidate
```

The directory must not exist. The runner archives committed inputs only, checks
17.0.2 Build 602, invokes map/fit/asm/STA for project/revision Groovy, resolves
fresh-map duplication sources, audits fitted six-driver separation & RAM types,
analyzes all eight corners & saves exact source/configuration manifests.
The EXIT handler creates `${CRT_READ_BUILD_DIR}-reports.tar.gz` even after a stage
error; inspect build_runner_exit_status.txt, timing_gate.json, resource_clock_gate.json
& io_coverage.json independently. A successful runner is not release qualification.

Run candidate first. Compare only the relevant one-factor variant if measured
results need explanation; do not automatically compile every variant:

| Variant | Change relative to integrated candidate |
|---|---|
| baseline | c8d4b38 CRT/root/VGA RTL with current compact reporting & unchanged configuration |
| read-add | Full read-address adder after column qualification instead of row/column fields |
| delta-flat | Original flat delta-buffer selection, all other corrections retained |
| ready-shared | Original shared tag-address/lookup readiness cone |
| vga-old | Original measured VGA arithmetic only |

Example diagnostic command, using a different new directory:

```bash
CRT_READ_BUILD_DIR="$(realpath ..)/Groovy-targeted-read-add-build" \
  bash tests/run_crt_read_address_quartus.sh read-add
```

Return the generated archive with complete timing_closure/, map/fit/assembly/STA
reports, source_inputs/manifests, project_calls, tool version, seed & driver audits.
Acceptance: setup/hold WNS >=0, TNS 0 & no failing endpoints at all eight corners;
passing recovery/removal/pulse checks; six-bank inference, <=553 M10Ks, 491520
MLAB bits & unchanged 12.081 ns clock. Active I/O/CDC coverage remains a separate
release requirement. No fabricated delays or broad false paths were added.
Real CRT hardware testing remains deferred until these measurements are reviewed.
