# CRT geometry RTL

The following files are copied without modification from
[`asdgdg355235/MiSTer-CRT-Adjust`](https://github.com/asdgdg355235/MiSTer-CRT-Adjust),
commit [`597e000eed284c75df29b80c70a6ec9db918561c`](https://github.com/asdgdg355235/MiSTer-CRT-Adjust/commit/597e000eed284c75df29b80c70a6ec9db918561c):

| File | Source path |
|---|---|
| `crt_vsize_fixed.sv` | `rtl/crt_vsize_fixed.sv` |
| `crt_edge_mask.sv` | `rtl/crt_edge_mask.sv` |
| `COPYING` | `LICENSE` |

`crt_vsize_fixed` derives its gamma-2 two-tap filter & square-root encoder
from rmonic79's `crt_vsize.sv`. Its field-local storage & parallel pipeline
preserve native sync & accept pixel enables below the original eight-clock
ratio. `crt_edge_mask` changes edge RGB without changing DE or sync.

The modules use GPL-3.0-or-later. See `COPYING` & the source headers.
Integration, reference symbols, test commands & FPGA validation limits are
documented in [`docs/crt-geometry.md`](../../docs/crt-geometry.md).
