# Q25 V2 root next-line operand experiment

Reference basis: reviewed R0-PHYS export from source 3b8d1ed & exporter 9275020.
The native D/CLK/Q witnesses, mapped counter inputs & multiplier/Add18 consumers
are committed in tests/physical/evidence/R0-PHYS-reviewed.json. That reviewed
source cone supports this root operand experiment, not a register-control overlay.
The old work/q25-v2-counter-boundary branch remains blocked & unchanged.

## One source factor

The original shared operand is vga_vcount + 10'd1 + PoC_interlaced. Split the
16-bit unsigned count x into upper u=x[15:1] & low bit b=x[0]. For parity p:

- Result low bit is ~(b ^ p).
- The carry into the upper field is b | p.
- The upper result is zero-extended u plus that carry, using 16 bits.

Concatenating upper & low gives a 17-bit value from 1 through 65,537. Zero-extend
to 24 bits before multiplication. This preserves the original 24-bit product
truncation before the framebuffer-interlace shift & final +3. A 16-bit next-line
value would be wrong at rollover & is explicitly rejected by a negative proof.

V2 replaces the operand at its two shared multiplication uses: the line-skip
decision & S_Blit_Auto_Skip pixel-count update. It preserves their common input.
The other terminal predicates, multiplier expression, VGA counter/total logic,
register enables, resets, video outputs & pipeline boundaries are unchanged.
There are no source changes to rtl/vga.v, LZ4, CRT RAM, QSF, SDC, PLL or HPS.
No new register or memory is introduced.

The proposed mechanism removes the serial +1 then +parity dependency from this
one operand. Quartus can remap/share/retime it again. No timing gain is claimed.

## Source profile & verification

Checkout RTL stays at R0. The complete patch is tests/physical/variants/V2.patch;
the runner applies it only in a new V2 snapshot. V2.json records original,
result, patch & R0 physical-review hashes. The baseline hardware manifest remains
unchanged & default R0 validation rejects the candidate Groovy.sv. V1 is not
registered or imported. No physical overlay may be combined with V2.

```bash
python3 tests/prove_v2_nextline.py
python3 tests/run_v2_frameskip_compare.py
python3 tests/run_timing_candidate_tests.py
```

Z3 checks unrestricted 16-bit count/parity identity. A separate congruence check
proves the complete 24-bit product/shift/update/comparison context using that
proved equality. These are expression proofs for defined inputs, not whole-FPGA
formal equivalence or four-state startup equivalence.

Icarus compiles the actual candidate helper, exhaustively compares all 131,072
count/parity cases & 1,048,576 product contexts. The frozen-R0 cycle comparison
uses actual VGA RTL plus extracted original/candidate root decisions & update
blocks. It covers reset, CE stalls, fields, dynamic modelines, rollover, first/
end/line choices & all VGA outputs. FIFO/overlay models are explicit; this is
not an end-to-end DDR/HPS traffic simulation. Full candidate mixed-language emu
elaboration & existing CRT/LZ4/delta regressions remain mandatory.

## User-only physical build

In a clean committed V2 checkout, choose a new directory outside the source:

```bash
export QUARTUS_25_BIN=/home/taichi/altera_lite/25.1std/quartus/bin
CRT_READ_BUILD_DIR="$PWD/../Groovy-Q25-V2-nextline-build" \
  bash tests/run_physical_timing_quartus.sh V2 --quartus-bin "$QUARTUS_25_BIN"
```

Preparation only uses the same command with --prepare-only & does not probe a
vendor executable. Both paths retain frozen build bytes, seed, physical settings,
12.081 ns clock, uncertainty, driver duplication & eight-corner inventories.
Return ../Groovy-Q25-V2-nextline-build-reports.tar.gz even on failure. Reports
remain losslessly partitioned, with at most 200 MiB per uncompressed member.

Compare against original Q25 R0, not V1. Retain only if the mapped root operand
mechanism is observed, the target improves, every required corner's WNS/TNS/count
does not regress, no new failing family appears & hold/resource/function gates
pass. Renamed Add17 endpoints need correspondence review. If Quartus recreates
the old serial structure or total timing worsens, reject V2 rather than adding
an LZ4 or counter change. C1, coverage qualification & CRT hardware acceptance
remain separate gates.
