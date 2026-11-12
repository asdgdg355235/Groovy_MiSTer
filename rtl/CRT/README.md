# CRT geometry RTL

The following files were originally imported from
[`asdgdg355235/MiSTer-CRT-Adjust`](https://github.com/asdgdg355235/MiSTer-CRT-Adjust),
commit [`04be786998d04769238b09190df1e36279f6e84a`](https://github.com/asdgdg355235/MiSTer-CRT-Adjust/commit/04be786998d04769238b09190df1e36279f6e84a):

| File | Source path |
|---|---|
| `crt_vsize_fixed.sv` | `rtl/crt_vsize_fixed.sv` |
| `crt_edge_mask.sv` | `rtl/crt_edge_mask.sv` |
| `COPYING` | `LICENSE` |

`crt_vsize_fixed.sv` now contains local memory/address timing changes. See
[`docs/crt-measured-baseline-integration.md`](../../docs/crt-measured-baseline-integration.md)
for the current source changes, reference tests & pending FPGA checks.

`crt_vsize_fixed` derives its gamma-2 two-tap filter & square-root encoder
from rmonic79's `crt_vsize.sv`. Its field-local storage & parallel pipeline
preserve native sync & accept pixel enables below the original eight-clock
ratio. `crt_edge_mask` changes edge RGB without changing DE or sync.

The modules use GPL-3.0-or-later. See `COPYING` & the source headers.
Integration, reference symbols, test commands & FPGA validation limits are
documented in [`docs/crt-geometry.md`](../../docs/crt-geometry.md).
