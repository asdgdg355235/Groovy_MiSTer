#!/usr/bin/env bash
# Preserve the working checkout and previous results; never reuse a build DB.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
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
tar -C "$ROOT" --exclude='./.git' --exclude='./db' --exclude='./incremental_db' \
    --exclude='./output_files' -cf - . | tar -C "$OUT" -xf -
cd "$OUT"
mkdir -p output_files
quartus_sh --version > output_files/crt_read_address_tool_version.txt
# Individual stage executables do not run the project's PRE_FLOW_SCRIPT_FILE.
# Match sys/sys.tcl and the callback's {stage project revision} argument layout.
quartus_sh -t sys/build_id.tcl pre_flow Groovy Groovy 2>&1 | tee output_files/crt_read_address_pre_flow.log
[[ -s build_id.v && -s jtag.cdf ]] || {
    echo 'ERROR: pre-flow did not generate build_id.v and jtag.cdf' >&2; exit 1;
}
quartus_map Groovy -c Groovy 2>&1 | tee output_files/crt_read_address_compile.log
quartus_cdb -t tests/report_crt_local_drivers.tcl map 2>&1 | tee output_files/crt_local_drivers_map.log
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_map.tsv > output_files/crt_local_drivers_map.json
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
quartus_sta -t tests/report_crt_read_address_timing.tcl 2>&1 | tee output_files/crt_read_address_sta.log
for stage in cmp; do
    quartus_cdb -t tests/report_crt_local_drivers.tcl "$stage" 2>&1 | tee "output_files/crt_local_drivers_${stage}.log"
done
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_cmp.tsv > output_files/crt_local_drivers_cmp.json
echo "Results: $OUT/output_files"
echo 'Review setup/hold slack even when the compilation exit status is successful.'
