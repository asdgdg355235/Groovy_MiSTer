#!/usr/bin/env bash
# Preserve the working checkout and previous results; never reuse a build DB.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VARIANT="${1:-candidate}"
OUT="${CRT_READ_BUILD_DIR:-"$ROOT/../crt-read-address-build-$(date -u +%Y%m%d-%H%M%S)"}"
for tool in quartus_sh quartus_map quartus_fit quartus_asm quartus_sta quartus_cdb python3 tclsh; do
    command -v "$tool" >/dev/null || { echo "ERROR: missing $tool" >&2; exit 127; }
done
if [[ -e "$OUT" ]]; then
    echo "ERROR: build directory already exists: $OUT" >&2
    exit 1
fi
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
# Copy committed inputs only: never copy an old DB, stale generated QSF or
# untracked local source override into a supposedly fresh build.
git -C "$ROOT" archive HEAD | tar -C "$OUT" -xf -
python3 "$ROOT/tests/configure_timing_variant.py" "$ROOT" "$OUT" "$VARIANT"
CANDIDATE_REV="$(git -C "$ROOT" rev-parse HEAD)"
cd "$OUT"
mkdir -p output_files
printf '%s\n' "$CANDIDATE_REV" > output_files/timing_candidate_commit.txt
printf '%s\n' "$VARIANT" > output_files/build_variant.txt
python3 tests/project_assignments.py . > output_files/project_calls_before_map.json
quartus_sh --version > output_files/crt_read_address_tool_version.txt
grep -F "17.0.2 Build 602" output_files/crt_read_address_tool_version.txt >/dev/null || { echo "Wrong Quartus version" >&2; exit 1; }
# Individual stage executables do not run the project's PRE_FLOW_SCRIPT_FILE.
# Match sys/sys.tcl and the callback's {stage project revision} argument layout.
quartus_sh -t sys/build_id.tcl pre_flow Groovy Groovy 2>&1 | tee output_files/crt_read_address_pre_flow.log
[[ -s build_id.v && -s jtag.cdf ]] || {
    echo 'ERROR: pre-flow did not generate build_id.v and jtag.cdf' >&2; exit 1;
}
python3 tests/source_manifest.py "$ROOT" "$OUT" mapped_inputs
quartus_map Groovy -c Groovy 2>&1 | tee output_files/crt_read_address_compile.log
quartus_cdb -t tests/report_crt_local_drivers.tcl map 2>&1 | tee output_files/crt_local_drivers_map.log
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_map.tsv > output_files/crt_local_drivers_map.json
# Resolve synthesis-generated names before Fitter reads its QSF. No historical
# source-name fallback is allowed in a real compilation.
if [[ "$VARIANT" == dup-off ]]; then
    echo '# Diagnostic variant: no required duplication assignments' > output_files/crt_address_duplication_resolved.qsf
    export CRT_DUPLICATION_DISABLED=1
else
    python3 tests/resolve_crt_duplicate_sources.py output_files/crt_local_drivers_map.tsv output_files/crt_address_duplication_resolved.qsf
fi
python3 tests/source_manifest.py "$ROOT" "$OUT" fitted_inputs
python3 tests/project_assignments.py . > output_files/project_calls_before_fit.json
# Audit exact sources before fitting; stop on the first missing-node warning.
python3 tests/run_crt_duplicate_fit.py 2>&1 | tee -a output_files/crt_read_address_compile.log
quartus_asm Groovy -c Groovy 2>&1 | tee -a output_files/crt_read_address_compile.log
quartus_sta Groovy -c Groovy 2>&1 | tee -a output_files/crt_read_address_compile.log
for stage in 'Analysis & Synthesis' Fitter Assembler 'TimeQuest Timing Analyzer'; do
    grep -F "Quartus Prime $stage was successful" output_files/crt_read_address_compile.log >/dev/null || {
        echo "ERROR: missing successful fresh stage: $stage" >&2; exit 1;
    }
done
if grep -Ei '(skipp|not required|up.to.date).*(synthesis|fitter|assembler)|(synthesis|fitter|assembler).*(skipp|not required|up.to.date)' \
    output_files/crt_read_address_compile.log; then
    echo 'ERROR: a required compilation stage was skipped' >&2; exit 1
fi
quartus_sta -t tests/report_timing_closure.tcl 2>&1 | tee output_files/crt_read_address_sta.log
for stage in cmp; do
    quartus_cdb -t tests/report_crt_local_drivers.tcl "$stage" 2>&1 | tee "output_files/crt_local_drivers_${stage}.log"
done
if [[ "$VARIANT" == dup-off ]]; then
    python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_cmp.tsv > output_files/crt_local_drivers_cmp.json
else
    python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_cmp.tsv --require-local > output_files/crt_local_drivers_cmp.json
fi
python3 tests/report_io_coverage.py output_files/timing_closure/unconstrained.txt output_files/timing_closure/io_coverage.json
python3 tests/validate_timing_exports.py output_files/timing_closure
python3 tests/validate_fitted_resources.py output_files
# Package after completed reports, regardless of whether measured timing passed.
tar -czf "${OUT}-reports.tar.gz" --exclude='*.sof' --exclude='*.rbf' -C "$OUT" output_files
echo "Results: $OUT/output_files"
echo 'Review setup/hold slack even when the compilation exit status is successful.'
