# Experimental Quartus 25.1 LZ4 window RAM compatibility

## Status

The source has a candidate one-read/one-write synchronous memory interface.
Icarus RTL equivalence and Quartus 25.1 inference **are not confirmed** by
this branch's commits. Do not use the generated FPGA image on hardware until
the functional, memory-resource, timing and interface checks pass.

Quartus 25.1 initially reported Error 276003 because `emu|lz4|window`
was not inferred as embedded RAM. The original LZ4 declaration contains
8192 words of 64 bits; Quartus 17.0.2 reported two inferred window RAM
copies, each 8192 by 64.

## Implementation

`rtl/lz4.v` now has a single synchronous window read. The read-ahead
address predicts the next registered `MP13` value when entering match-copy
states or advancing the source-word index. A previous-cycle write bypass
handles the address collision case without depending on a particular M10K
read-during-write mode.

The original decoder's 26 memory-write expressions are collected into one
write port. Output-register assignments and state-update cycles are retained.

An explicit 64-bit read-data register and the forwarding registers add logic.
Quartus 25.1 must establish whether the intended inference and resource
mapping actually occur. No timing improvement is assumed.

## Verification without Quartus

From the checked-out experimental branch:

```bash
python3 tests/test_lz4_q25_window_schedule.py
python3 tests/test_lz4_q25_source_contract.py
python3 tests/run_lz4_q25_differential.py
```

The differential runner requires Icarus Verilog and vvp. It obtains an
independent reference from commit
`c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17` and runs both the normal
64-bit and `MISTER_LZ4_DISABLE_64B` modes. The existing testbench compares
cycle-by-cycle outputs and critical state and checks changed window words.

The Python schedule and expression checks are supporting evidence only.
They cannot replace the HDL differential simulation.

## User-only Quartus test

**Do not run Quartus inside ChatGPT Work.**

The following command is for the user's local Linux machine:

```bash
python3 tests/run_q25_lz4_user.py
```

The runner selects
`/home/taichi/altera_lite/25.1std/quartus/bin`, verifies Quartus 25.1,
creates a fresh committed-source archive, copies the existing
`sys/pll_q17.qip` file list to `sys/pll_q25.qip` in that copy, and
runs Analysis & Synthesis. It checks for a window `ALTSYNCRAM` report
entry and packages the output.

After reviewing that result and confirming resource mapping, the user
may request a full compilation and eight-corner timing export:

```bash
python3 tests/run_q25_lz4_user.py --full
```

Each build creates a separate directory and a `-reports.tar.gz`
diagnostic archive. Keep the Quartus 17.0.2 baseline unchanged.

## Acceptance

A successful differential simulation is required but is not proof of RAM
inference. Successful Quartus mapping is required but is not proof of
cycle equivalence or timing closure. The user must verify both gates, then
check M10K capacity, the original CRT memory banks, final address-driver
separation, and all eight timing corners before accepting this change.
