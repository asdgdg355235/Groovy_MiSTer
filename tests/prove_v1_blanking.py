#!/usr/bin/env python3
"""Finite-width V_total identity, not a Quartus or sequential proof."""
from z3 import BitVec,Bool,ZeroExt,Extract,If,Solver,unsat,sat

def prove():
 v=BitVec('V',16);bp=BitVec('VBP',8);fp=BitVec('VFP',8);vs=BitVec('VS',8);field=Bool('field_adjust')
 old_sum=v+ZeroExt(8,bp)+ZeroExt(8,fp)+ZeroExt(8,vs)
 blank=ZeroExt(2,bp)+ZeroExt(2,fp)+ZeroExt(2,vs)
 base=v+ZeroExt(6,blank)
 old=If(field,old_sum-1,old_sum);new=If(field,base-1,base)
 solver=Solver();solver.add(old!=new);assert solver.check()==unsat
 # Negative control rejects an insufficient 9-bit porch sum.
 broken=v+ZeroExt(7,Extract(8,0,blank));solver=Solver();solver.add(old_sum!=broken);assert solver.check()==sat
 print('PASS: V_total full-range unsigned 16/8/8/8-bit identity, field decrement and wrap; rejects 9-bit truncation')
if __name__=='__main__':prove()
