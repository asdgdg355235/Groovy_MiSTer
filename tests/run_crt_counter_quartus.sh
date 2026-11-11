#!/usr/bin/env bash
# On the real Quartus 17 checkout, run this after RTL equivalence is confirmed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
for tool in quartus_sh quartus_sta; do
    command -v "$tool" >/dev/null || { echo "ERROR: missing $tool" >&2; exit 127; }
done
mkdir -p output_files
set -o pipefail
quartus_sh --flow compile Groovy 2>&1 | tee output_files/crt_counter_compile.log
quartus_sta -t tests/report_crt_counter_timing.tcl 2>&1 | tee output_files/crt_counter_sta.log
printf '\nCompilation and detailed setup/hold reports complete.\n'
printf '%s\n' output_files/Groovy.fit.rpt output_files/Groovy.sta.rpt \
    output_files/crt_counter_worst_setup.txt output_files/crt_counter_worst_hold.txt
