#!/usr/bin/env python3
"""Cycle-level reference comparison using Icarus Verilog, never Quartus."""
from pathlib import Path
import os, shlex, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17"

def run(args):
    print("+", shlex.join(args), flush=True)
    subprocess.run(args, check=True, cwd=ROOT)

def main():
    original = subprocess.check_output(["git", "show", f"{BASE}:rtl/lz4.v"], cwd=ROOT, text=True)
    if original.count("module lz4 (") != 1:
        raise RuntimeError("Reference RTL source identity mismatch")
    reference = original.replace("module lz4 (", "module lz4_reference (", 1)
    with tempfile.TemporaryDirectory(prefix="lz4-q25-compare-") as temp:
        temp = Path(temp)
        refpath = temp / "lz4_reference.v"
        refpath.write_text(reference)
        for disabled in (False, True):
            output = temp / ("byte-only" if disabled else "full-64-bit")
            cmd = shlex.split(os.environ.get("IVERILOG", "iverilog"))
            cmd += ["-g2012", "-s", "tb_lz4_timing", "-o", str(output)]
            if disabled:
                cmd += ["-DMISTER_LZ4_DISABLE_64B"]
            cmd += [str(ROOT / "tests/tb_lz4_timing.sv"), str(ROOT / "rtl/lz4.v"), str(refpath)]
            run(cmd)
            run(shlex.split(os.environ.get("VVP", "vvp")) + [str(output)])
            print("PASS:", output.name)

if __name__ == "__main__":
    main()
