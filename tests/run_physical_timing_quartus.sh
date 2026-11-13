#!/usr/bin/env bash
# USER RUN ONLY. Never source this script from independent regression tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
EXPERIMENT="${1:-R0}"
[[ $# -eq 0 ]] || shift
OVERLAY= EVIDENCE= PREPARE_ONLY=0 PROFILE=q25
QBIN=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quartus-bin) QBIN="$2"; shift 2 ;;
        --profile) PROFILE="$2"; shift 2 ;;
        --overlay) OVERLAY="$2"; shift 2 ;;
        --evidence) EVIDENCE="$2"; shift 2 ;;
        --prepare-only) PREPARE_ONLY=1; shift ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
[[ "$PROFILE" == q17 || "$PROFILE" == q25 ]] || { echo 'Expected --profile q17 or q25' >&2; exit 2; }
[[ -n "$QBIN" ]] || { if [[ "$PROFILE" == q25 ]]; then QBIN="${QUARTUS_25_BIN:-}"; else QBIN="${QUARTUS_17_BIN:-}"; fi; }
[[ "$EXPERIMENT" == R0 || "$EXPERIMENT" == A1 || "$EXPERIMENT" == D1 ]] || { echo 'Expected R0, A1 or D1' >&2; exit 2; }
[[ "${CRT_DUPLICATION_DISABLED:-0}" != 1 ]] || { echo 'Driver duplication must remain enabled' >&2; exit 2; }
OUT="${CRT_READ_BUILD_DIR:-$ROOT/../physical-$EXPERIMENT-$(date -u +%Y%m%d-%H%M%S)}"
OUT="$(python3 -c 'import pathlib,sys;print(pathlib.Path(sys.argv[1]).resolve())' "$OUT")"
[[ ! -e "$OUT" ]] || { echo 'Refusing existing build directory' >&2; exit 2; }
python3 - "$ROOT" "$OUT" <<'PY'
from pathlib import Path
import sys
source,out=map(lambda p:Path(p).resolve(),sys.argv[1:])
if source==out or source in out.parents: raise SystemExit('Build directory must be outside source')
out.parent.mkdir(parents=True,exist_ok=True)
PY
STAGE=preparation
finish() {
    result=$?
    trap - EXIT
    mkdir -p "$OUT/output_files"
    if [[ -f "$OUT-preparation.log" ]]; then mv "$OUT-preparation.log" "$OUT/output_files/preparation.log"; fi
    if ! python3 "$ROOT/tests/physical/diagnostics.py" "$OUT/output_files" > "$OUT/output_files/diagnostic_assembly.log" 2>&1; then
        echo 'Diagnostic assembly failed; inspect diagnostic_assembly.log' >&2
        printf 'Diagnostic assembly failed\n' > "$OUT/output_files/diagnostic_assembly_failed.txt"
        [[ "$result" != 0 && "$result" != 4 ]] || result=1
    elif [[ "$STAGE" == complete ]]; then
        if ! python3 - "$OUT/output_files/closure_diagnostics/diagnostic_status.json" <<'PY'
from pathlib import Path
import json,sys
status=json.loads(Path(sys.argv[1]).read_text())
if not status['export_queries_complete'] or not status['video_requirements_pass']:
    raise SystemExit('INVALID EXPERIMENT: incomplete physical exports; reports retained')
PY
        then
            [[ "$result" != 0 && "$result" != 4 ]] || result=1
        fi
    fi
    python3 "$ROOT/tests/restart/finalize_build.py" "$OUT" "$result" "$STAGE" || exit 1
    exit "$result"
}
trap finish EXIT
args=("$ROOT" "$OUT" "$EXPERIMENT" --profile "$PROFILE")
[[ -z "$OVERLAY" ]] || args+=(--overlay "$OVERLAY")
[[ -z "$EVIDENCE" ]] || args+=(--evidence "$EVIDENCE")
python3 "$ROOT/tests/physical/control.py" prepare "${args[@]}" > "$OUT-preparation.log" 2>&1
cd "$OUT"
python3 - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json,os,platform
Path('output_files/host_environment.json').write_text(json.dumps({
    'actual_timestamp_utc':datetime.now(timezone.utc).isoformat(),
    'host':platform.node(),'platform':platform.platform(),'cpu_count':os.cpu_count(),
    'affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
    'parallel_setting':'ALL (unchanged)', 'database_reuse':False},indent=2)+'\n')
PY
python3 tests/physical/q25_ram_evidence.py preflight . --profile "$PROFILE"
if [[ "$PREPARE_ONLY" == 1 ]]; then
    python3 tests/physical/control.py freeze .
    python3 tests/physical/control.py stage-inputs . before_map
    STAGE=prepared-only
    exit 0
fi
STAGE=preflight
[[ -n "$QBIN" && -d "$QBIN" ]] || { echo 'Set QUARTUS_25_BIN or QUARTUS_17_BIN to its explicit Lite bin directory' >&2; exit 2; }
QBIN="$(cd "$QBIN" && pwd -P)"
export PATH="$QBIN:$PATH"
for tool in quartus_sh quartus_map quartus_fit quartus_asm quartus_sta quartus_cdb; do
    [[ -x "$QBIN/$tool" ]] || { echo "Missing selected executable: $tool" >&2; exit 127; }
    [[ "$(readlink -f "$(command -v "$tool")")" == "$(readlink -f "$QBIN/$tool")" ]] || { echo "Mixed toolchain executable: $tool" >&2; exit 2; }
    "$QBIN/$tool" --version > "output_files/${tool}_version.txt"
    python3 tests/physical/control.py verify-version "output_files/${tool}_version.txt" --profile "$PROFILE"
done
cp output_files/quartus_sh_version.txt output_files/crt_read_address_tool_version.txt
# The support-mode Tcl script must not infer the compiler profile from
# quartus(version): Q25 crashes in native PJC on assignment enumeration.
export PHYSICAL_COMPILER_PROFILE="$PROFILE"
STAGE=capabilities
quartus_sh -t tests/physical/report_project.tcl support > output_files/closure_diagnostics/assignment_support.log 2>&1
STAGE=pre-flow
quartus_sh -t sys/build_id.tcl pre_flow Groovy Groovy 2>&1 | tee output_files/crt_read_address_pre_flow.log
[[ -s jtag.cdf ]]
python3 tests/physical/control.py freeze .
python3 tests/physical/control.py stage-inputs . before_map
STAGE=mapping
quartus_map Groovy -c Groovy 2>&1 | tee output_files/crt_read_address_compile.log
grep -F 'Quartus Prime Analysis & Synthesis was successful' output_files/crt_read_address_compile.log >/dev/null
python3 tests/physical/q25_ram_evidence.py map output_files --profile "$PROFILE"
quartus_sh -t tests/physical/report_project.tcl map > output_files/closure_diagnostics/project_map.log 2>&1
quartus_cdb -t tests/physical/report_atoms.tcl map > output_files/closure_diagnostics/atoms_map.log 2>&1
python3 tests/physical/application.py output_files map
quartus_cdb -t tests/report_crt_local_drivers.tcl map > output_files/crt_local_drivers_map.log 2>&1
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_map.tsv > output_files/crt_local_drivers_map.json
python3 tests/resolve_crt_duplicate_sources.py output_files/crt_local_drivers_map.tsv output_files/crt_address_duplication_resolved.qsf
python3 tests/physical/control.py stage-inputs . before_fit
STAGE=fitting
python3 tests/run_crt_duplicate_fit.py 2>&1 | tee -a output_files/crt_read_address_compile.log
STAGE=assembly
quartus_asm Groovy -c Groovy 2>&1 | tee -a output_files/crt_read_address_compile.log
STAGE=sta
quartus_sta Groovy -c Groovy 2>&1 | tee -a output_files/crt_read_address_compile.log
STAGE=sta-export
quartus_sta -t tests/report_timing_closure.tcl > output_files/crt_read_address_sta.log 2>&1
STAGE=diagnostics
quartus_sh -t tests/physical/report_project.tcl cmp > output_files/closure_diagnostics/project_cmp.log 2>&1
quartus_cdb -t tests/physical/report_atoms.tcl cmp > output_files/closure_diagnostics/atoms_cmp.log 2>&1
quartus_sta -t tests/physical/report_fanout.tcl > output_files/closure_diagnostics/fanout.log 2>&1
python3 tests/physical/application.py output_files cmp
STAGE=audits
python3 tests/physical/control.py verify-generated .
quartus_cdb -t tests/report_crt_local_drivers.tcl cmp > output_files/crt_local_drivers_cmp.log 2>&1
python3 tests/summarize_crt_local_drivers.py output_files/crt_local_drivers_cmp.tsv --require-local > output_files/crt_local_drivers_cmp.json
python3 tests/report_io_coverage.py output_files/timing_closure/unconstrained.txt output_files/timing_closure/io_coverage.json
python3 tests/validate_timing_exports.py output_files/timing_closure
python3 tests/validate_fitted_resources.py output_files
python3 - <<'PY'
from pathlib import Path
import json
if not json.loads(Path('output_files/resource_clock_gate.json').read_text())['resource_clock_pass']:
    raise SystemExit('INVALID EXPERIMENT: resource/clock gate failed')
PY
STAGE=complete
python3 - <<'PY'
from pathlib import Path
import json
if not json.loads(Path('output_files/timing_closure/timing_gate.json').read_text())['timing_pass']:
    print('Compilation completed; TIMING FAILED. Diagnostic archive will be retained.')
    raise SystemExit(4)
print('Timing checks passed; coverage and hardware acceptance remain separate.')
PY
