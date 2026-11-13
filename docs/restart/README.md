# Independent timing experiments after rollback

**Measured follow-up:** all eight RTL variants below regressed setup timing.
Do not repeat or integrate them unchanged. The current implementation uses
[gated physical experiments](../physical-timing/README.md), beginning with R0
diagnostics & fixed generated inputs. The historical instructions below are
retained as experiment provenance.

The rollback restores the entire tracked tree to
`c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17`, tree
`51e56ffb5637fdfd67bd90b3908f0e325c78f85d`. The published history through
`69562854a9055c3dc81ae90c902d724b22034572` remains reachable, including through
`backup/crt-targeted-6956285`. `baseline/crt-hps-c8d4b38` preserves the starting
source. `d79174a^` is exactly `c8d4b38`.

This iteration integrates the independent experiment harness, proofs, language
checks & reporting. Default production RTL is byte-identical to `c8d4b38`.
Each named experiment applies ONE new patch to that baseline in a fresh build
snapshot. Experiments cannot be combined by this runner. This implements the
requirement to measure each physical effect before integrating RTL changes.
There is no measured replacement RTL bundle yet.

## Synthesis failure and physical references

The supplied `6956285` compile log records Error 10170 at `rtl/vga.v:112`, near
an apostrophe, followed by the ignored VGA design unit. Its runner exit status
is 3. That is a synthesis failure, with no timing result. Its expression used
`11'(interlaced && field)` inside a `VERILOG_FILE`. Earlier arithmetic checks
and SystemVerilog frontend runs did not check the real project language mode.
The new negative fixture reproduces the rejected cast in Verilog-2001, while
showing that the same fixture parses in SystemVerilog.

The newest supplied archive records a DIFFERENT local source revision,
`6add25d2437d7243d2b462c814cc0fe9961fd9be`, plus a runner overlay. Its VGA cast
was changed to a legal conditional expression. Its Slow 100C setup result is
-2.249 ns, TNS -4847.053 ns, 8807 failing endpoints. Slow -40C is -2.351 ns,
TNS -2501.049 ns, 5919 endpoints. The other two slow corners also fail.
Its minimum exported hold margin is +0.040 ns. Several detailed negative
reports in that archive had their middle removed by its previous packager;
the endpoint TSVs remain usable for endpoint counts. These are observations
from that archive, not timing measurements for the restarted experiments.

Keep these references separate:

| Reference | Setup result | Scope |
|---|---:|---|
| Original archived working tree | +0.177 ns, TNS 0 | Slow 1100 mV 100C only; different effective configuration |
| HPS-corrected `c8d4b38` | -0.089 ns, TNS -0.199 ns | Slow 100C; corrected HPS locations |
| HPS-corrected `c8d4b38` | -0.161 ns, TNS -0.389 ns | Slow -40C; six endpoints |
| Original `6956285` | No timing result | Analysis & Synthesis failed |
| Local repaired `6add25d` archive | -2.351 ns | Worst of its eight exported corners |

`physical_paths.json` extracts all 13 baseline negative corner/path pairs,
including exact launch/capture aliases, FF locations, fanouts, cell delays,
routing delays, generated-register ports & report SHA-256 hashes. It was
regenerated from the supplied detailed exports. It does not infer RTL
registers from generated names. Reproduce it without Quartus with:

```bash
python3 tests/restart/map_evidence.py \
  /path/to/hps-corrected/output_files \
  /path/to/newer-local-build/output_files \
  physical_paths.json
```

## Physical-to-RTL mapping

| Cone | Evidence in baseline reports | Source correspondence and limit |
|---|---|---|
| CRT reads | `wcol[14]~DUPLICATE` to bank 0 odd output; 6 levels, 3.297 ns cell, 8.321 ns routing, -0.089 ns | Range qualification, row/column address & final RAM mux. Launch FF fanout is 2, downstream drivers differ. Preserve all six final drivers. |
| First-line row arithmetic | `delay_lines[1]` to `advance_rows[1]~61_OTERM4407`; 8 levels, 7.341 ns cell, 4.226 ns routing, -0.161 ns | `Add8`, `LessThan7`, `output_now`, position mux, `Add1` carry, retimed subtraction. Capture `advance_rows...NEW_REG` is generated; it is not a declared RTL register. |
| Delta selection | `PoC_lz4_delta_index[3]` to `r_vram_in2[2]`; launch fanout 914; slow -40C: 4.661 ns cell, 6.905 ns routing, -0.148 ns | 128x64 register buffer read, independent byte additions in unchanged `lz4.v`, then `decode_pixel`. |
| VGA/root arithmetic | `PoC_V[0]~DUPLICATE` to root `Add17~5` aliases; 9 levels, 8.045 ns cell, 3.764 ns routing, -0.026 ns | Path includes VGA `Add1`, `Add0`, `Add54`, `LessThan19`, then root `Add17` carry. The ultimate source-level capture is unresolved. Do not identify Add17 with V_total or field-height arithmetic solely from its name. |
| Sync/metadata | `hb_d~0_OTERM4457` to packed `dv_hs1` delay RAM input; 9 levels, 4.048 ns cell, 7.426 ns routing, -0.017 ns | Line-begin/output selection & tag/complete qualification reach packed metadata/control. Physical RAM bit is not proof that it stores HS alone. `sys_top.v` still captures `csync_en ? dv_cs_osd : dv_hs_osd` at its original edge. |

The fitted database/retiming correspondence is not reconstructed by the
independent tools. Root field-height expressions, `V_total`, sync registers,
transport FSM & passing LZ4 decoder stay unchanged. These mappings justify
isolated cone experiments, not a claimed fitted timing improvement.

## Experiments

Every patch is derived from `c8d4b38`, with baseline, patch & result hashes in
`tests/timing_experiments/index.json`. `source_manifest.json` inventories the
complete baseline; each variant replaces only its named RTL file. Build-time
manifests capture the actual complete source snapshot & generated assignments.

| Variant | Changed expression | Focused checks |
|---|---|---|
| `row-increment` | 16-bit integer increment plus fractional carry; separate overflow bit preserves the original 17-bit subtraction | Unrestricted 32-bit SMT identity, reduced-width exhaustive checks, overflow negative control, six-bank/video cycle comparison |
| `row-enable` | First-output choice at the existing position/source-row/slot state updates; global output/read qualification unchanged | Predicate proof under established line-begin, six-bank/video comparison |
| `read-fields` | Production read addresses concatenate the 3-bit stored-row base with 9 qualified column bits; other parameterizations retain `address_word` | Finite-width address identity, quotient/remainder transition invariant, saturation/CE/bypass & six-bank comparison |
| `read-late` | Select complete current-line addresses using late range qualification, versus the baseline's early column selection | Same address/invariant proof & cycle checks; compare with `read-fields`, never stack them |
| `delta-8x16` | Eight 16-entry combinational selections followed by an 8-way selection | Actual selector/unchanged byte-add/actual decode task comparison, root elaboration & geometry regression |
| `delta-4x32` | Four 32-entry selections followed by a 4-way selection | Same checks; compare with 8x16; neither repeats the previous 16-group layout |
| `vga-terminal` | Compare 17-bit counter+1 against nonzero V_total; remove total-1 from this comparison's fan-in | SMT for all 16-bit counter/total pairs including total zero, Verilog parse, every-clock video/reference comparison |
| `sync-first-row` | Select the constant first-row readiness result after tag comparisons; one continuing dynamic lookup remains | Selection identity & every-clock RAM/video/HS/VS/CE/field comparison |

For row arithmetic, let `d = (step[31:16] + fractional_carry) mod 65536`.
The exact original 17-bit subtraction is `{carry(position[31:16]+d), d}`.
A plain integer-step result loses the high borrow bit on position wrap. The
preserved negative control uses position `0xffff0000`, step `0x00010000`:
reference `0x10001`, naive expression `1`.

The address proof requires a qualified read column in 0..511. The actual
quotient/remainder state advances with the CE-qualified wcol, saturates at
LINE_PX, holds during CE stalls & restarts on the same line-begin edge.
Production reads satisfy that invariant; writes are untouched. No extra state,
RAM, read latency, video latency or DUPLICATE_ATOM assignment is added.

The delta selector's logical depth changes from a 128-entry selection to
16-by-8 or 32-by-4 grouping. Both still express a 7-bit selection. Intel LUT
mapping, physical fanout & route length must be measured; RTL grouping/keep
attributes do not establish retained physical hierarchy or driver duplication.

## Non-Quartus validation

Requirements: Python 3, z3-solver, Icarus, Verilator, g++, make & Tcl. Run:

```bash
python3 tests/run_timing_candidate_tests.py --main /path/to/Main_MiSTer
python3 tests/restart/check_experiment.py row-increment --output row-increment-check.json
```

Repeat the second command with each desired variant. Individual machine-readable
results & logs are under `results/`. Syntax runs first, arithmetic before cycle
comparison. Mixed elaboration uses Verilog-2001 for `.v` and SystemVerilog for
`.sv`, explicit IP/VHDL models & documented inherited frontend waivers. VGA
still has inherited `[size]` array declarations accepted with Icarus warnings.
These independent checks do not certify Quartus 17 synthesis support.

CRT cycle comparison covers 2111136 reduced-width clocks plus 4587681 production
clocks per CRT variant, all six RAM read/write/enable/data inputs, synchronous
outputs, RGB/sync/CE/field outputs, all sizes -7..+7, saturation, same-cycle line
bypass, stalls, reset/restart & runtime geometry changes. Native VGA regression
covers progressive 240/288-line & interlaced 480/481-line input modes. Delta
comparison covers 21737 cycles per grouping, all four mode encodings, index
127 wrap, partial/full refills, stalls & reset. The delta wrapper exercises the
actual selector, byte-add expressions & decode task, not the entire DDR FSM.
Existing LZ4 regressions test its unchanged decoder separately.

Simulation is bounded cycle evidence. SMT proves the stated arithmetic
identities, not whole-design formal equivalence. No Quartus command was run.

## Fresh user-run Quartus builds

Use Quartus Prime Lite 17.0.2 Build 602 with its executables on PATH. Fetch the
published restart commit, then create a fresh detached worktree at that SHA.
From that worktree:

```bash
CRT_READ_BUILD_DIR="$PWD/../Groovy-restart-baseline-build" \
  bash tests/run_crt_read_address_quartus.sh baseline
CRT_READ_BUILD_DIR="$PWD/../Groovy-restart-row-increment-build" \
  bash tests/run_crt_read_address_quartus.sh row-increment
```

Use a NEW build directory per invocation. The runner rejects an existing path,
does not copy db/incremental_db/output_files & snapshots committed source.
Historical `old-builds/` and `test-builds/` distribution bundles are excluded
from build snapshots and listed in provenance; they are not project inputs.
The exact project/revision is `Groovy -c Groovy`. It runs mapping, resolves
fresh synthesized duplication sources, fits with the guarded fitter, assembles,
runs STA, exports all eight corners & audits RAM/driver/I/O/resource coverage.
It retains seed 1, 5CSEBA6U23I7, corrected HPS, inactive HDMI & 12.081 ns clocks.
Default baseline configuration, including multicorner physical settings, stays
unchanged. All-corner reporting is independent of the fitter option.

Measure baseline first; then row-increment, row-enable & one read alternative
at a time. Compare the second read alternative if the first changes routing
adversely. Compare both delta layouts. VGA & sync variants remain separate.
Do not combine winners until each has source & physical evidence. An exact
variant is identified by checked-out commit, variant name, patch digest,
result digest & the generated full source manifests.

For explicit local modifications use `working-tree --working-tree`. The
provenance records HEAD, dirty paths, binary diff & actual source bytes. It is
marked uncontrolled, rather than described as the committed experiment.

## Compact complete archives

Success & failure both create `<build-directory>-reports.tar.gz`. Failure at
mapping remains a failed compilation in `build_state.json`, with no timing
claim. Inputs are preserved separately for prepared/before_map/before_fit;
later Quartus QSF expansion cannot overwrite the original snapshot.

Every uncompressed tar member is at most 209715200 bytes. Verbose positive
reports use an 8388608-byte member bound. Large files are split into numbered
byte parts, including every middle byte. Original reports remain unchanged.
The manifest records each original & part SHA-256. Restore before reading a
split file with an ordinary report viewer:

```bash
python3 tests/restart/package_reports.py \
  ../Groovy-restart-baseline-build-reports.tar.gz --verify
python3 tests/restart/package_reports.py \
  ../Groovy-restart-baseline-build-reports.tar.gz --restore ../Groovy-restored-reports
```

Manual repackaging uses the same lossless policy:

```bash
python3 tests/restart/package_reports.py \
  ../Groovy-restart-baseline-build/output_files \
  ../Groovy-restart-baseline-repacked.tar.gz
```

All negative setup/hold/recovery/removal endpoints & detailed paths remain
complete. Positive family details are bounded to eight paths; global negative
inventories remain unlimited. Pulse summary prefixes grow until a nonnegative
check or an exhausted result establishes completeness; detailed negative pulse
checks remain complete. The validator rejects missing corners, inconsistent
endpoint TNS/counts, truncated negative reports & incomplete pulse prefixes.
Plain Tcl stand-ins test export control flow; they do not test Quartus APIs.

Return the complete diagnostic archive. It includes `build_state.json`, tool
version/logs, provenance, source manifests/inputs, effective project calls,
`Groovy.{map,fit,asm,sta}.{rpt,summary}` when produced, map/cmp driver TSV/JSON,
resource gate, plus `timing_closure/` with all corner and endpoint inventories,
full failures, compact worst/family paths, pulse summaries, clocks, exceptions,
ignored constraints, clock transfers & I/O coverage. SOF/RBF files are excluded.

## Physical acceptance

Every required corner must have setup/hold WNS >=0, TNS=0 & zero failing
endpoints. Recovery/removal/pulse checks must pass. Confirm six 3072x40 banks,
four MLAB/two M10K, 491520 MLAB bits, total M10Ks <=553, retained final driver
separation & unchanged clock. Unmatched family filters require node inspection;
they do not establish that a family passes. Active I/O requirements & unexplained
CDC/constraint issues remain separate release gates. No timing exception or
external I/O delay is invented here. Real CRT validation follows timing &
interface qualification; these changes do not authorize a CRT test.

## Reference basis

Receiver source inspected: `psakhis/Groovy_MiSTer`, `rtl/vga.v` native totals,
terminal/field processing; `rtl/lz4.v` independent-byte delta additions & output
readiness. Linux upstream inspected: `s3gfaultx/mistercast-linux`,
`src/stream/GroovyMister.cpp`, `GroovyMister::sendFrame`, modeline payload/field
validation & LZ4 command/payload submission. No sender/protocol change is made.
Target baseline source: `crt_vsize_fixed` address/state logic,
`Groovy.sv:decode_pixel`, `rtl/vga.v` terminal condition &
`sys/sys_top.v` `dv_hs1` capture. The experiment structures are new source
transformations checked against the target baseline, not inherited protocol
behavior.
