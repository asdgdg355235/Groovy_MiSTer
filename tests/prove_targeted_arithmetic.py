#!/usr/bin/env python3
"""Unrestricted finite-width proofs for the selected candidate; needs z3-solver."""
from z3 import BitVec, BitVecVal, ZeroExt, Extract, Concat, Solver, unsat

def prove(label,a,b):
 s=Solver();s.add(a!=b)
 assert s.check()==unsat,(label,s.model())
 print('PASS:',label)

p,s=BitVec('p',32),BitVec('s',32)
f=ZeroExt(1,Extract(15,0,p))+ZeroExt(1,Extract(15,0,s))
i=ZeroExt(1,Extract(31,16,s))+ZeroExt(16,Extract(16,16,f))
h=ZeroExt(1,Extract(31,16,p))+i
candidate=Concat(Extract(16,16,i)^Extract(16,16,h),Extract(15,0,i))
reference=ZeroExt(1,Extract(31,16,p+s))-ZeroExt(1,Extract(31,16,p))
prove('17-bit row difference for every 32-bit position/step',candidate,reference)
for bits in range(1,5):
 mask=(1<<(2*bits))-1; part=(1<<bits)-1
 for p0 in range(mask+1):
  for s0 in range(mask+1):
   inc=(s0>>bits)+(((p0&part)+(s0&part))>>bits)
   wrap=((p0>>bits)+inc)>>bits
   a=(inc^(wrap<<bits))&((1<<(bits+1))-1)
   b=((((p0+s0)&mask)>>bits)-(p0>>bits))&((1<<(bits+1))-1)
   assert a==b
 print('PASS: exhaustive reduced-width row difference, half width',bits)
