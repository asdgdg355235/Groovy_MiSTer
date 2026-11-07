#!/usr/bin/env bash
set -euo pipefail

# Always clean the project containing this script, not the caller's directory.
cd -- "$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")"

if [[ ! -f Groovy.qpf || ! -f files.qip || ! -f clean.bat ]]; then
    printf 'Error: clean.sh must be in the Groovy_MiSTer project root.\n' >&2
    exit 1
fi

# Some wildcard patterns (.csv, .xml, etc.) can match source files.
# Preserve anything tracked by Git.
remove_untracked_file() {
    local file="${1#./}"
    if ! git ls-files --error-unmatch -- "$file" >/dev/null 2>&1; then
        rm -f -- "$file"
    fi
}

printf 'Cleaning Quartus-generated files in %s\n' "$PWD"

# Directories removed by clean.bat.
rm -rf -- \
    db incremental_db output_files simulation greybox_tmp hc_output \
    .qsys_edit hps_isw_handoff sys/.qsys_edit sys/vip

shopt -s nullglob
for dir in sys/*_sim rtl/*_sim; do
    [[ -d "$dir" ]] && rm -rf -- "$dir"
done

# Netlist directories, wherever Quartus generated them.
find . -type d -name .git -prune -o \
    -type d \( -name new_rtl_netlist -o -name old_rtl_netlist \) \
    -prune -exec rm -rf -- {} +

# Recursive file patterns from clean.bat. Never traverse .git.
while IFS= read -r -d '' file; do
    remove_untracked_file "$file"
done < <(
    find . -type d -name .git -prune -o -type f \( \
        -name '*.bak' -o -name '*.orig' -o -name '*.rej' -o -name '*~' \
        -o -name '*.qws' -o -name '*.ppf' -o -name '*.ddb' \
        -o -name '*.csv' -o -name '*.cmp' -o -name '*.sip' \
        -o -name '*.spd' -o -name '*.bsf' -o -name '*.f' \
        -o -name '*.sopcinfo' -o -name '*.xml' \
        -o -name new_rtl_netlist -o -name old_rtl_netlist \
    \) -print0
)

# Root-level files and patterns from clean.bat.
for file in build_id.v c5_pin_model_dump.txt PLLJ_PLLSPE_INFO.txt ./*.cdf ./*.rpt; do
    [[ -f "$file" || -L "$file" ]] && remove_untracked_file "$file"
done

printf 'Clean complete. Git-tracked files were preserved.\n'
