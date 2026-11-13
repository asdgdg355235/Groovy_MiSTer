# Quartus 25.1 R0 timing infrastructure

This branch starts from the exact physical-timing R0 commit
`248d48ab625b04418fab1bc369c4cb60ff47fff1`, with two approved
hardware-level compatibility changes:

* `rtl/lz4.v`: the exact registered-read, look-ahead and forwarding decoder
  on `experimental/quartus25-lz4-registered-window`, commit
  `a692f4f6d75a79e67cb36f1065ff0d7c9a97ae92`.
* `sys/pll_q25.qip`: byte-identical four-PLL source list from
  `sys/pll_q17.qip`, selected by the existing major-version rule in
  `sys/sys.qip`.

The fixed Q25 manifest `tests/physical/hardware_q25.json` lists 93
hash-checked hardware/configuration files. The original Q17 92-file
manifest is kept intact. New or modified source files outside the allow-list
cause preparation to fail. The build date is frozen as the exact 27 bytes
`` `define BUILD_DATE "261112" `` without a trailing newline.

## Non-Quartus checks

```bash
python3 tests/run_timing_candidate_tests.py
python3 -m unittest discover -s tests -p test_physical_experiments.py -v
python3 tests/run_lz4_q25_differential.py
bash -n tests/run_physical_timing_quartus.sh
```

The LZ4 differential compares actual RTL and the independent original
`c8d4b38` module in full-64-bit and byte-only modes. The optional
`--prepare-only` runner checks committed source, frozen generated input,
QIP identity and effective static assignments without invoking Quartus.
Do not interpret preparation success as FPGA synthesis or timing closure.

## Q25 R0 user compilation

This following block is for the machine with Quartus installed. Do not run it
in ChatGPT CI.

```bash
git fetch origin refs/heads/work/physical-timing-q25:refs/remotes/origin/work/physical-timing-q25
git worktree add --detach ../Groovy-Q25-R0-source origin/work/physical-timing-q25
cd ../Groovy-Q25-R0-source
export QUARTUS_25_BIN=/home/taichi/altera_lite/25.1std/quartus/bin
CRT_READ_BUILD_DIR="$PWD/../Groovy-Q25-R0" \
  bash tests/run_physical_timing_quartus.sh R0 \
  --profile q25 --quartus-bin "$QUARTUS_25_BIN"
```

The runner preserves `../Groovy-Q25-R0-reports.tar.gz` whether synthesis
succeeds or a later stage fails. Key files under the archive's `output_files`
directory are `provenance.json`, `static_preflight.json`,
`q25_window_ram_gate.json`, `generated_input_freeze.json`,
`source_manifest_{prepared,before_map,before_fit}.json`, compiled map/fit
reports, `closure_diagnostics/` and `timing_closure/` (eight corners).
The archive preserves complete reports using independently hashed pieces
capped at 200 MiB. The build must establish LZ4 M10K inference, the original
four CRT MLAB banks and two CRT M10K banks, and required video timing.

## Quartus 25.1 assignment capability discovery

On Quartus Prime Lite 25.1std.0 Build 1129, `get_all_assignment_names`
terminates `quartus_sh` with `PJC: Unsupported smart action`, even when the
project is open. The R0 runner passes the preflight-verified `q25` compiler profile to the
support probe, which avoids that native command and records all 16 map/fit,
global/instance assignment combinations as `available=0` with explicit
`UNVERIFIED` metadata. Direct invocations without a verified profile also
fail closed. The Q17 profile retains assignment discovery when its compiler
version is verified as 17.0.2. This is not a finding that the
assignments are unsupported. No capabilities or legal values are inferred.
The pre-existing A1 overlay validator still rejects any unverified
assignment; R0 and D1 do not depend on approving A1 assignments.

Do not use a prior failed build directory for the next run. Fetch the
updated branch, choose a new `CRT_READ_BUILD_DIR`, and retain the new report
archive for analysis. A successful R0 build does not approve A1 retiming
assignments; these require separate compiler-supported evidence.

## Quartus-updated QSF project version metadata

Quartus 25.1 rewrites `LAST_QUARTUS_VERSION` from
`17.0.2 Lite Edition` to `25.1std.0 Lite Edition` when opening
the original project. The input-stage gate accepts this exact version
metadata transition for the Q25 profile only, while preserving the
unaltered sourced assignment sequence in `project_calls_*.json` and
recording the exception in each `input_gate_*.json`. Any change to an
other assignment, any unexpected compiler stamp, or a duplicate/reordered
version stamp still rejects the build. Q17 retains byte-for-byte
assignment comparison without this exception.

## Quartus Q25 R0 post-map assignment serialization

Quartus Prime Lite 25.1std.0 Build 1129 appends 237 sourced QSF
assignment calls after mapping and before the recursive QIP input calls.
The observed block comprises 234 repeats of existing source assignments
and three HPS location aliases matching the prepared HPS_LOCATION
assignments. The R0 `before_fit` input gate accepts only the complete
ordered block observed in the uploaded
`Groovy-Q25-R0-metadataguard-reports.tar.gz`: its SHA-256 is
`92bb9095ba3cbb792187af197f1d375d06d8e25afea451fcd40acdb490af96de`
over compact UTF-8 JSON of the captured event rows. A compact fixture
of indices into the approved pre-map assignment sequence is kept in
`tests/physical/fixtures/q25_r0_postmap_serialization.json`.
The raw capture remains in `project_calls_before_fit.json` and the
accepted serialization is recorded in `input_gate_before_fit.json`.

Q17, pre-map comparison, A1/D1 comparisons and unrelated QSF
changes retain their existing fail-closed gates. RTL, physical settings,
device pinout, and timing constraints are unchanged.

## Evidence and comparisons

Q25 A1/D1 recipes require new Q25 R0 evidence. Quartus 17 targets and sites
are not accepted. Each recipe must include `compiler_profile: q25`,
`r0_source_commit`, the sealed R0 evidence SHA-256, exact source/physical
register correspondence, assignment-support evidence and all other fields
specified by the inherited `tests/physical/overlays.py` contract. Neither
experiment is applied automatically.

For one-toolchain candidate comparison, use `compare.py` with the Q25 R0
directory as the control:

```bash
python3 tests/physical/compare.py ../Groovy-Q25-R0/output_files \
  ../Groovy-Q25-A1/output_files --output ../Groovy-Q25-A1/comparison.json
```

For descriptive comparisons between compilers (no cross-version node-name
equivalence or compiler-only causal claim), run:

```bash
python3 tests/physical/compare.py ../Groovy-Q17-R0/output_files \
  ../Groovy-Q25-R0/output_files --cross-version \
  --output ../Groovy-Q25-R0/output_files/q17_vs_q25.json
```

Timing acceptance requires all eight setup WNS >= 0, no failing
setup/hold endpoints, passing recovery/removal/pulse checks, accepted
constraint coverage, and observed CRT resource/driver topology. Physical
overlays require separate evidence review. No compiler or hardware result is
implied by the source commit.
