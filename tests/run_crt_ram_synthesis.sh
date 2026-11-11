#!/usr/bin/env bash
# Controlled Quartus 17 Analysis & Synthesis experiments.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${QUARTUS_RAM_OUT:-"$HOME/quartus-crt-extracted"}
mkdir -p "$OUT"
command -v quartus_map >/dev/null || { echo "quartus_map is unavailable" >&2; exit 127; }
for experiment in six_banks crt_vsize_fixed; do
    mkdir -p "$OUT/$experiment"
    cd "$OUT/$experiment"
    cat > "$experiment.qpf" <<EOF
PROJECT_REVISION = "$experiment"
EOF
    cat > "$experiment.qsf" <<EOF
set_global_assignment -name FAMILY "Cyclone V"
set_global_assignment -name DEVICE 5CSEBA6U23I7
set_global_assignment -name TOP_LEVEL_ENTITY $([ "$experiment" = six_banks ] && echo tb_six_packed_ram || echo crt_vsize_fixed)
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files
set_global_assignment -name SYSTEMVERILOG_FILE "$ROOT/rtl/CRT/crt_packed_ram.sv"
EOF
    if [ "$experiment" = six_banks ]; then
        echo "set_global_assignment -name SYSTEMVERILOG_FILE "$ROOT/tests/tb_six_packed_ram.sv"" >> "$experiment.qsf"
    else
        echo "set_global_assignment -name SYSTEMVERILOG_FILE "$ROOT/rtl/CRT/crt_vsize_fixed.sv"" >> "$experiment.qsf"
        cat >> "$experiment.qsf" <<EOF
set_parameter -name LINE_PX 2560
set_parameter -name MAX_DELTA 7
set_parameter -name RING_LINES 12
set_parameter -name MLAB_PARTS 0
EOF
    fi
    printf '\n===== Synthesizing %s =====\n' "$experiment"
    if quartus_map "$experiment" -c "$experiment" > map.log 2>&1; then
        grep -E 'Inferred altsyncram|Total block memory bits|Total registers|ERROR|Error \(' map.log "output_files/$experiment.map.summary" || true
    else
        tail -n 45 map.log
        exit 1
    fi
done
printf '\nResults: %s\n' "$OUT"
