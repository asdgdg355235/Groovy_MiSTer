# Q25 V2 counter-boundary evidence gate

This branch derives from R0-PHYS recovery, not rejected V1. Hardware hashes remain
those of Q25 R0 3b8d1ed. No RTL, constraint, PLL, duplication or physical control
is added. V1's patch & source-variant allowances are absent.

The measured R0 path crosses VGA total arithmetic, terminal comparison,
vertical-counter selection & root Add17 frame-skip arithmetic. Fitted names do
not identify the source capture boundary. R0-PHYS must return actual mapped and
fitted edges at D/SDATA, Q, clock & enable, plus Add17 downstream Mult0/Add18
connections. Source-location and retiming-report observations must agree with
those edges before selecting a register control or changing an operand.

V2 is registered with blocked-evidence status. Its empty pending recipe is not
an assignment overlay. control.py refuses preparation before writing a candidate,
even if a caller supplies a nominal recipe. The compilation runner still accepts
only its existing approved experiment interface; no V2 native build is ready.
A subsequent evidence-supported implementation must add its precise allowance,
focused cycle/formal checks & native application audit in a separate commit.

Use the recovery branch's read-only R0-PHYS command first. No new baseline fit.
If correspondence resolves the v_cnt boundary, evaluate one scoped movement
restriction only after installed Q25 Lite register scope and values are verified.
If that control is unsupported, inspect the confirmed root operand dependency
as an independent source experiment. Do not change both. Global retiming stays ON.
If no specific serial dependency is established, keep V2 blocked.

C1 remains independently blocked on its original locality branch. No site, bank
relocation, new register or unconditional duplication is imported here. A1/D1
validation remains unchanged. Q25 R0, rejected V1 & their archives remain intact.
