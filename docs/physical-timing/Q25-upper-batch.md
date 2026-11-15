# Q25 upper selectors & counter boundary

All candidates use the original Q25 R0 hardware control
`3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a`. The shared infrastructure starts
from reviewed physical-export commit `83862f796f4382dfec91ebbf4dbc5a9ea8409f0c`.
No V1 blanking-sum or V2 next-line RTL is incorporated. All 93 approved
hardware/configuration files remain byte-identical to the Q25 profile.

| Factor | Destination | Status | Evidence |
| --- | --- | --- | --- |
| U10 | Bank-1 even upper bit 10 | Fresh-map candidate ready | R0 upper routed segment 3.629 ns; fitted source spans 640/642/20 loads |
| U9 | Bank-0 odd upper bit 9 | Fresh-map candidate ready, exploratory timing target | Separate source spans 640/641/20 fitted loads; rejected V2 exposed a bank-0 odd failure |
| V3 | One original VGA `v_cnt` register group | Blocked pending ancestry & native instance-scope review | Source family/root D/CLK/Q correspondence established, original register movement not established |
| U10_U9_V3 | Exact composition of the three factors | Blocked while any required factor lacks evidence | No branch merge, database reuse or assumed additive gain |

U9's measured failing bank-0 odd path comes from rejected V2. Original R0's
exported negative endpoints do not establish a failing U9 destination. U9 can
be measured independently, but cannot qualify merely because fanout drops or
a positive odd-bank path improves. Its review must identify a genuine improved
failing R0 dependency under the same acceptance rule. Otherwise keep it as
experimental evidence & leave combined promotion blocked.

## Reference basis

`rtl/CRT/crt_vsize_fixed.sv:75-78,215-278` defines position/row advancement,
bank-local logical read addresses & six RAM instances. `crt_packed_ram.sv`
retains synchronous reads, widths & memory types. `rtl/vga.v:96,109,702-742`
defines vertical counter state, total, reset priorities & CE qualification.
`Groovy.sv:1074-1078` defines the root frame-skip product.

The reviewed R0-PHYS archive hash is
`ec067377ace04da1e7ce444b91f6dcd4639a4e8e11f9c6331f8b41f63cb29011`.
`tests/physical/fixtures/upper_selection_r0_map.json` identifies the complete
selected native port excerpt & its source/fixture hashes. It contains all
5,600 input/output records for the two selected map sources, not a top-N sample.
Mapped source fanout is 1,400 each, partitioned 680/680/40. These are map counts;
they must not be confused with the fitted 1,302/1,301 counts.

## Resolution & integrity gates

`upper_selection.py` obtains each source from logical PORTBADDR bit 10/9 on
bank 2's M10K read port. It validates the actual COMBOUT/SUMOUT source, complete
outgoing pins, reciprocal input connections & all bank partitions. Generated
suffixes are not source selectors. Selected MLAB consumers are DATA pins of
actual `rd_mux` hierarchy, including typed `mux_...:rd_mux` names.

The unchanged low-bit resolver still writes exactly 30 assignments to
`crt_address_duplication_resolved.qsf`. A separate generated
`upper_address_duplication.qsf` contains one U10 or U9 factor, or both in the
combined candidate. No static location is assigned. Before fitting, the input
gate checks the exact generated assignment events against the fresh map;
unknown or missing duplicates cannot hide behind the historical DUPLICATE_ATOM
accounting filter. Original RTL, clock/SDC, QIP/HPS/HDMI settings & generated
bytes remain fixed.

The post-fit gate requires a distinct native physical source for each copy,
bank-only complete fanout, retained original sources for other banks & no
remaining shared original connection into the selected bank. It retains
copy/original fanin for review. It does not claim that a named copy improves
timing or that unreviewed retiming is cycle proof. Logical-bit diagnostics
include these validated copy connections without inventing MLAB address pins.

The sealed original R0 report predates full output-port export. When it has no
OUTPUT records at all, preparation uses the committed, hash-checked complete
R0-PHYS excerpt. Partial fresh candidate output exports always fail. Neither
the old diagnostic failure nor a historical suffix is silently treated as a
successful candidate mechanism.

## One user-side batch command

Do not run these vendor builds through CI. The assistant has not run Quartus.
Use the shared batch branch for all experiments, rather than combining
individual experiment branches:

```bash
git fetch origin work/q25-timing-batch
git worktree add --detach ../Groovy-Q25-upper-batch-source origin/work/q25-timing-batch
cd ../Groovy-Q25-upper-batch-source

python3 tests/run_q25_timing_experiment_batch.py \
  --quartus-bin /home/taichi/altera_lite/25.1std/quartus/bin \
  --baseline-reports /home/taichi/src/groovy-crt-build/Groovy-Q25-R0-postmapgate/output_files \
  --experiments U10,U9,V3 \
  --combined-when-qualified \
  --output-root /home/taichi/src/groovy-crt-build/q25-upper-timing-batch
```

The output root must not exist & must be outside the checkout. A normal Git
checkout or detached linked worktree is accepted; dirty sources are rejected.
Every eligible candidate gets a detached source snapshot at the exact same
infrastructure commit & a new build directory. Builds run sequentially via the
existing physical runner. Six selected executables must report exact
25.1std.0 Build 1129 Lite identities. Old databases are never copied into
candidate builds. The original R0 database & reports are read-only inputs.

Add `--prepare-only` to exercise preparation without probing a vendor executable.
V3 remains blocked without a reviewed recipe; this is not an R0 substitute.
An individual branch can run its named candidate directly:

```bash
CRT_READ_BUILD_DIR="$PWD/../Groovy-Q25-U10" \
  bash tests/run_physical_timing_quartus.sh U10 --profile q25 \
  --quartus-bin /home/taichi/altera_lite/25.1std/quartus/bin \
  --evidence /home/taichi/src/groovy-crt-build/Groovy-Q25-R0-postmapgate/output_files
```

Use U9 with a different new directory for the other upper selector. No factor
depends on another candidate's source or fit result.

## V3 diagnostics & activation

`tests/physical/recipes/V3.blocked.json` records source expressions, reset/CE
rules, exact missing evidence & the future recipe schema. It has no physical
assignment or guessed register. `root_operand_r0.json` retains the actual
reviewed root arithmetic source & map/fitted D/CLK/Q observations.

The following user-side command copies the existing R0 native database into a
new query-only snapshot, then reads selected map/cmp ports. It does not map or
fit. It writes separate diagnostics & a lossless archive even on native query
failure:

```bash
python3 tests/physical/run_v3_diagnostics.py \
  --build-dir /home/taichi/src/groovy-crt-build/Groovy-Q25-R0-postmapgate \
  --output /home/taichi/src/groovy-crt-build/Groovy-Q25-V3-boundary-evidence \
  --quartus-bin /home/taichi/altera_lite/25.1std/quartus/bin
```

An optional isolated `--single-assignment-query ADV_NETLIST_OPT_ALLOWED`
queries one known assignment's metadata in a separate process. Default is off.
It never calls hazardous `get_all_assignment_names`. Metadata observation
does not approve instance-register scope, values or actual compiler effect.
Source cross-probe/reset/enable/initialization ancestry still needs review.

A reviewed `q25-v3-boundary-v1` recipe must bind the original R0 provenance,
hardware profile & generated bytes; hash its ancestry/cycle/native-scope proof
files in a separate `V3-evidence` directory; identify exact observed original
& fitted registers; & select one instance-scoped movement-control factor.
Use `--v3-recipe /absolute/path/V3.json` with the batch. Unknown/global settings,
wildcards, absent registers, mixed controls or unverified values are rejected.
The validator supports only a narrow original `v_cnt[0..15]` group, not a
generated Add17 name masquerading as an RTL register. No code implementation
session is required to load a later correctly reviewed recipe.

The `native_assignment_scope_values` proof is a reviewed JSON certificate with
`status: supported`, exact `version: 25.1std.0`, `build: 1129`, `edition: Lite`,
`scope: instance`, `object_type: register`, assignment `name`, `accepted_values`,
`reviewed_by` & a `native_evidence` dictionary of relative native-export paths
to SHA-256 hashes. It is not generated as approved by the metadata query.
Missing, unsupported or changed evidence keeps V3 blocked. The query's raw
metadata alone does not certify that a particular register accepts the setting.

## Results & combined eligibility

Expected files under the output root:

```text
Groovy-Q25-U10-reports.tar.gz
Groovy-Q25-U9-reports.tar.gz
Groovy-Q25-V3-reports.tar.gz
Groovy-Q25-COMBINED-reports.tar.gz  # only after eligible combined execution
q25-timing-batch-summary.json
q25-timing-batch-comparison.tsv
q25-timing-batch-results.md
```

A blocked individual gets an explicitly labelled diagnostic-only package. It
contains no claimed timing result. Failed compilation keeps native logs &
partial outputs. A completed timing failure does not stop the next independent
candidate. Each compiled package includes source/provenance, prepared/pre-map/
pre-fit manifests, map/fitted copy audits, every required timing corner &
complete endpoint distributions. Lossless packaging caps each uncompressed
member at 200 MiB & uses smaller partitions for verbose positive reports.

`physical/q25_batch_compare.py` checks every corner's WNS/TNS/count, all ancillary
checks, complete endpoint distributions, new failing families, hardware/input/
resource/driver gates & host controls. It keeps both launch/capture direction
and unmatched-name correspondence status. Cell/routing/skew/levels, physical
locations, fanout & memory reports remain in each package & comparison JSON.

Automatic timing comparison is not an automatic source-correspondence proof.
`--reviews-dir` accepts U10.json, U9.json & V3.json tied to the exact control and
candidate provenance hashes, actual hashed report evidence, physical/cycle
review & an improved originally failing target endpoint. A renamed endpoint
requires explicit correspondence explanation. A positive-path improvement
alone does not meet the retention gate.

Default combined execution requires each constituent to be ACCEPTED. An
explicit `--combined-exploratory` permits a separate combination measurement
despite timing rejection only when all physical application/evidence gates
are valid. It cannot bypass blocked V3 support, ignored assignments or invalid
sources. The combined candidate is reconstructed directly from the unchanged
hardware profile plus the three factors; it does not merge branches or reuse
any fit. Its own eight-corner result is independently accepted or rejected.

Batch exit codes: 0 prepared/accepted, 1 incomplete compilation, 2 invalid CLI/
source/output selection, 3 blocked/invalid evidence or pending review, 4 completed
but rejected timing. Each candidate also retains its original runner exit code.
Nothing is promoted automatically to the original R0 branch.

## Verification & remaining physical requirements

```bash
python3 -m unittest discover -s tests -p test_q25_upper_batch.py -v
python3 tests/run_timing_candidate_tests.py
bash -n tests/run_physical_timing_quartus.sh
```

The focused suite uses the labelled actual selected R0 excerpt plus explicitly
synthetic splits/builds. No vendor executable runs in these tests. The full
suite retains actual Verilog/SystemVerilog mode checks, finite-width proofs,
six-bank ports/synchronous data & CRT geometry -7..+7, reset/CE/mode transitions,
LZ4 full/byte-only differential & delta/decode regressions. Source identity is
expected for these assignment-only candidates; actual mapped register movement
and timing still require user-side physical evidence.

Final timing closure needs nonnegative setup/hold WNS at all eight corners,
zero negative TNS/failing endpoints & passing recovery/removal/pulse checks.
The 2,470 no_clock & 3-input/47-output coverage findings remain separate release
work. No clock relaxation, broad exception or fabricated external delay is
introduced. Real CRT acceptance remains pending after timing qualification.
