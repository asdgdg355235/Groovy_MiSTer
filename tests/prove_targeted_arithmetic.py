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
from z3 import Bool, If, UGE, ULT, Not
line,first,started=Bool('line_begin'),Bool('first_source'),Bool('started')
n,out=BitVec('line_no',16),BitVec('out_height',16)
d=BitVec('delay_lines',6)
read=If(first,BitVecVal(0,16),n+1)
now=If(line,read,n)
old=If(line,(started|first)&UGE(now,ZeroExt(10,d))&ULT(ZeroExt(1,now),ZeroExt(1,out)+ZeroExt(11,d)),Bool('line_active'))
new=If(line,(started|first)&UGE(read,ZeroExt(10,d))&ULT(ZeroExt(1,read),ZeroExt(1,out)+ZeroExt(11,d)),Bool('line_active'))
prove('upcoming-line qualification including 16-bit wrap',old,new)
prove('first-output qualification',line&(now==ZeroExt(10,d)),line&(read==ZeroExt(10,d)))
# Every reachable production column state, including saturated blanking reads.
# Field/reset/CE holds leave these counters unchanged. Line starts assign 1/0/1.
for col in range(2561):
 group,lane=divmod(col,5)
 next_col=col+1 if col<2560 else col
 next_group=group+(lane==4) if col<2560 else group
 next_lane=(0 if lane==4 else lane+1) if col<2560 else lane
 assert (next_group,next_lane)==divmod(next_col,5)
 word=group if col<2560 else 0
 for slot in range(16):
  assert (((slot>>1)*512+word)&4095)==((((slot>>1)<<9)|(word&511))&4095)
print('PASS: all production column transitions, saturation & all 4-bit slot values')
slot,word=BitVec('slot',4),BitVec('word',9)
prove('read row/column fields for every qualified word',
      (ZeroExt(8,slot)>>1)*512+ZeroExt(3,word),
      ((ZeroExt(8,slot)>>1)<<9)|ZeroExt(3,word))
from z3 import SignExt
v,bp,fp,vs=BitVec('V',16),BitVec('BP',8),BitVec('FP',8),BitVec('VS',8)
parity=BitVec('adjust',1)
blank=ZeroExt(2,bp)+ZeroExt(2,fp)+ZeroExt(2,vs)
adjusted=ZeroExt(1,blank)-ZeroExt(10,parity)
prove('V_total all input widths, zero blanking & parity underflow',v+SignExt(5,adjusted),v+ZeroExt(8,bp)+ZeroExt(8,fp)+ZeroExt(8,vs)-ZeroExt(15,parity))
cnt,total=BitVec('count',16),BitVec('total',16)
prove('vertical terminal comparison including zero/max',
 (total!=0)&UGE(ZeroExt(1,cnt)+1,ZeroExt(1,total)),
 UGE(ZeroExt(16,cnt),ZeroExt(16,total)-1))
from z3 import Function, BitVecSort, BoolSort
ready=Function('ready',BitVecSort(4),BitVecSort(16),BoolSort())
cur_slot,next_slot=BitVec('cur_slot',4),BitVec('next_slot',4)
cur_row,next_row=BitVec('cur_row',16),BitVec('next_row',16)
first_line=Bool('first_line')
old_slot=If(line,If(first_line,BitVecVal(0,4),next_slot),cur_slot)
old_row=If(line&first_line,BitVecVal(0,16),If(line,next_row,cur_row))
ready_line=ready(If(first_line,BitVecVal(0,4),next_slot),If(first_line,BitVecVal(0,16),next_row))
prove('move complete/tag lookup before line selection',ready(old_slot,old_row),If(line,ready_line,ready(cur_slot,cur_row)))
