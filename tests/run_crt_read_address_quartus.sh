#!/usr/bin/env bash
# USER RUN ONLY. Independent experiments use fresh copies of c8d4b38 RTL.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
EXPERIMENT="${1:-baseline}"
MODE="${2:-}"
[[ -z "$MODE" || "$MODE" == --working-tree ]] || { echo 'Expected --working-tree or no second argument' >&2; exit 2; }
OUT="${CRT_READ_BUILD_DIR:-"$ROOT/../crt-independent-$(date -u +%Y%m%d-%H%M%S)"}"
prepare_args=("$ROOT" "$OUT" "$EXPERIMENT")
[[ -z "$MODE" ]] || prepare_args+=(--working-tree)
python3 "$ROOT/tests/restart/prepare_build.py" "${prepare_args[@]}"
OUT="$(cd "$OUT" && pwd -P)"
cd "$OUT"
STAGE=preflight
finish() {
    result=$?
    trap - EXIT
    python3 tests/restart/finalize_build.py "$OUT" "$result" "$STAGE" || { echo 'Packaging failed; reports remain in output_files' >&2; exit 1; }
    exit "$result"
}
trap finish EXIT
for tool in quartus_sh quartus_map quartus_fit quartus_asm quartus_sta quartus_cdb tclsh; do
    command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 127; }
done
quartus_sh --version > output_files/crt_read_address_tool_version.txt
grep -F '17.0.2 Build 602' output_files/crt_read_address_tool_version.txt >/dev/null
python3 tests/project_assignments.py . > output_files/project_calls_before_map.json
STAGE=pre-flow
quartus_sh -t sys/build_id.tcl pre_flow Groovy Groovy 2>&1 | tee output_files/crt_read_address_pre_flow.log
[[ -s build_id.v && -s jtag.cdf ]]
python3 tests/restart/prepare_build.py . before_map --record
STAGE=mapping
quartus_map Groovy -c Groovy 2>&1 | tee output_files/crt_read_address_compile.log
grep -F 'Quartus Prime Analysis & Synthesis was successful' output_files/crt_read_address_compile.log >/dev/null
quartus_cdb -t tests/report_crt_local_drivers.tcl map 2>&1 | tee output_files/crt_local_drivers_map.log
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_map.tsv > output_files/crt_local_drivers_map.json
python3 tests/resolve_crt_duplicate_sources.py output_files/crt_local_drivers_map.tsv output_files/crt_address_duplication_resolved.qsf
python3 tests/restart/prepare_build.py . before_fit --record
python3 tests/project_assignments.py . > output_files/project_calls_before_fit.json
STAGE=fitting
python3 tests/run_crt_duplicate_fit.py 2>&1 | tee -a output_files/crt_read_address_compile.log
STAGE=assembly
quartus_asm Groovy -c Groovy 2>&1 | tee -a output_files/crt_read_address_compile.log
STAGE=sta
quartus_sta Groovy -c Groovy 2>&1 | tee -a output_files/crt_read_address_compile.log
for stage in Fitter Assembler 'TimeQuest Timing Analyzer'; do
    grep -F "Quartus Prime $stage was successful" output_files/crt_read_address_compile.log >/dev/null
done
STAGE=sta-export
quartus_sta -t tests/report_timing_closure.tcl 2>&1 | tee output_files/crt_read_address_sta.log
STAGE=audits
quartus_cdb -t tests/report_crt_local_drivers.tcl cmp 2>&1 | tee output_files/crt_local_drivers_cmp.log
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_cmp.tsv --require-local > output_files/crt_local_drivers_cmp.json
python3 tests/report_io_coverage.py output_files/timing_closure/unconstrained.txt output_files/timing_closure/io_coverage.json
python3 tests/validate_timing_exports.py output_files/timing_closure
python3 tests/validate_fitted_resources.py output_files
STAGE=complete
printf 'Build completed. Inspect timing_gate.json, resource_clock_gate.json and io_coverage.json.\n'
