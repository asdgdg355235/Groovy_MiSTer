#!/usr/bin/env python3
"""SMT checks of fixed-width identities, not a proof of the complete design.

Requires z3-solver. All operands are unrestricted, including wrap/underflow.
"""
from z3 import (BitVec, BitVecVal, Bool, Concat, Extract, If, Not, Or, Solver,
                UGE, ULT, ZeroExt, unsat)


def prove(name, left, right):
    solver = Solver()
    solver.add(left != right)
    assert solver.check() == unsat, (name, solver.model())
    print('PASS:', name)

p, step = BitVec('position', 32), BitVec('step', 32)
fraction = ZeroExt(1, Extract(15, 0, p)) + ZeroExt(1, Extract(15, 0, step))
increment = ZeroExt(1, Extract(31, 16, step)) + ZeroExt(16, Extract(16, 16, fraction))
position_sum = ZeroExt(1, p) + ZeroExt(1, step)
next_p = Extract(31, 0, position_sum)
advance = increment ^ Concat(Extract(32, 32, position_sum), BitVecVal(0, 16))
prove('position addition, all 32-bit inputs', next_p, p + step)
prove('17-bit row advance including position wrap', advance,
      ZeroExt(1, Extract(31, 16, p + step)) - ZeroExt(1, Extract(31, 16, p)))

col = BitVec('column', 16)
ce, hb, begin, started = (Bool(n) for n in ('ce', 'hb', 'begin', 'started'))
for limit in (0, 1, 32, 2560, 65535, 65536):
    in_range = ULT(ZeroExt(16, col), limit)
    start = ce & begin & started
    advance_col = ce & Not(start) & Not(hb) & in_range
    next_col = If(start, BitVecVal(1, 16), If(advance_col, col + 1, col))
    flag_next = If(start, (1 < limit),
                   If(advance_col, Or(limit >= 65536, col != BitVecVal(limit - 1, 16)), in_range))
    prove(f'column predicate invariant, LINE_PX={limit}', flag_next,
          ULT(ZeroExt(16, next_col), limit))

v, bp, fp, sync = BitVec('V', 16), BitVec('VBP', 8), BitVec('VFP', 8), BitVec('VS', 8)
field = BitVec('adjust', 1)
old_total = v + ZeroExt(8, bp) + ZeroExt(8, fp) + ZeroExt(8, sync) - ZeroExt(15, field)
balanced = (v + ZeroExt(8, bp)) + ZeroExt(7, ZeroExt(1, fp) + ZeroExt(1, sync)) - ZeroExt(15, field)
prove('balanced vertical total with 16-bit truncation', balanced, old_total)
cnt, total = BitVec('v_cnt', 16), BitVec('V_total', 16)
prove('vertical terminal comparison including V_total=0',
      (total != 0) & UGE(ZeroExt(1, cnt) + 1, ZeroExt(1, total)),
      UGE(ZeroExt(16, cnt), ZeroExt(16, total) - 1))
