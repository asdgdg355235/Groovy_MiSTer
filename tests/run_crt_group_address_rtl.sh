#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
command -v iverilog >/dev/null || { echo 'ERROR: iverilog not installed'; exit 127; }
command -v vvp >/dev/null || { echo 'ERROR: vvp not installed'; exit 127; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if [[ -n "${CRT_BASELINE_FILE:-}" ]]; then
    cp "$CRT_BASELINE_FILE" "$TMP/reference_original.sv"
else
    git -C "$ROOT" show "${CRT_BASELINE_REV:-9c27398c5358a62214c910283293333099da4baf}:rtl/CRT/crt_vsize_fixed.sv" > "$TMP/reference_original.sv"
fi
sed 's/^module crt_vsize_fixed #(/module crt_vsize_fixed_reference #(/' \
    "$TMP/reference_original.sv" > "$TMP/reference.sv"
grep -q '^module crt_vsize_fixed_reference #(' "$TMP/reference.sv" || {
    echo 'ERROR: missing baseline module'; exit 1;
}
for parts in 0 2; do
    iverilog -g2012 -s tb_crt_group_address \
      -P "tb_crt_group_address.MLAB_PARTS=$parts" \
      -o "$TMP/sim_$parts" \
      "$ROOT/rtl/CRT/crt_packed_ram.sv" \
      "$ROOT/rtl/CRT/crt_vsize_fixed.sv" \
      "$TMP/reference.sv" \
      "$ROOT/tests/tb_crt_group_address.sv"
    vvp "$TMP/sim_$parts"
done
