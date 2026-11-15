# Software verification results

Quartus was not executed. `manifest.json` identifies the verified RTL & build
configuration bytes. Logs retain software-tool warnings; they aren't Quartus
reports or physical timing measurements.

| Check | Observed result |
| --- | --- |
| LZ4 full configuration | 134,626 clocks, 39 golden streams, all decoder states |
| LZ4 byte-only configuration | 215,939 clocks, 39 golden streams |
| Delta arithmetic | All 65,536 byte-input pairs in each LZ4 configuration |
| Read-rate generator | Both HPOS modes, integer ratios 8…16, 108 line-reference resets per mode |
| CRT upstream comparison | 1,966,074 clocks per HPOS mode; signed size/position/shift & bypass |
| Integrated CRT glue | 11,108,474 clocks per HPOS mode; 1,682 fixed OSD anchors; first/last source rows retained; dynamic modeline/ratio/reset cases |
| Cabinet eight-clock pixels | 11,206,650 clocks, 771,584 photometric pixels; maximum requested size ±24 lines |
| Cabinet sixteen-clock pixels | 22,413,298 clocks, 771,584 photometric pixels |
| Full-width Cabinet ring | 640 pixels at capacity, 5,505,018 clocks, 302,080 photometric pixels |
| VSync maximum delay | 24-line delay reached; 11,206,650 clocks & 640,896 photometric pixels |
| Integer square root | Every 16-bit input checked against mathematical floor square root |
| Actual emu video-section bypass | 2,230,272 compared clocks in each build configuration; original offsets/scale & interlace fallback |
| Actual enabled emu pipeline | 1,233,360 true-blank alignment checks through mixer → CRT → video_freak |
| Native video | 240p & eight interlaced field changes; both half-line VSync phases |
| Native audio | Frozen-base differential comparison, three rate selectors, mono/stereo |
| Controllers | Trigger calibration/polarity, both slots, fallback/reset/registration, Buttons 1…10, L3/R3, three defect mutations & full HPS source syntax checks |
| Source/report unit tests | 15 passed |
| Isolated build preparation | BASE, CABINET & SYNCSHIFT passed; all source/assignment hashes checked; existing output directories rejected |
| Yosys memory collection | Synchronous 1R/1W: 8,192 × 64 LZ4; 29,440 × 24 Cabinet; 2,048 × 24 horizontal buffer |

The frozen-reference Cabinet RGB differences are confined to the tested source
overrun correction: 512 clocks at an eight-clock pixel period, 1,024 at sixteen
clocks, & 11,264 in the extended VSync test. Sync/control comparisons remain
active during those cases. Absolute cursor bounds & photometric results pass.
The Groovy blanking correction is covered by separate first/last-row assertions.
The H-Size pixel-preservation check qualifies pixels with the final OSD window.

The native audio test compares the unchanged implementation's FIFO startup
phase rather than assuming a different FIFO latency. Simulation FIFO models
don't validate hardware CDC. The inherited video framework emits simulator
width/implicit-net diagnostics retained in `video-pipeline.log`; source identity
& software differential results don't replace the required Quartus/color-output
hardware check.

`check_q25_prepare.py` separately verifies isolated BASE, CABINET & SYNCSHIFT
preparation from a clean committed checkout. It supplies an absent compiler
directory & uses only `--prepare-only`; no Quartus program is called.

Remaining acceptance evidence is the local Q25-BASE/Q25-CABINET compile,
eight-corner timing, complete constraint/warning review, physical RAM/resource
mapping, analog output, HDMI compatibility & real-controller/A/V checks.
