#!/usr/bin/env python3
"""Finite-width SMT identities for independent experiments, not FPGA timing."""
from z3 import BitVec,BitVecVal,ZeroExt,Extract,Concat,Solver,UGE,If,Bool,unsat

def prove(label,a,b):
 s=Solver();s.add(a!=b)
 assert s.check()==unsat,(label,s.model())
 print('PASS:',label)

def row():
 p,s=BitVec('position',32),BitVec('step',32)
 frac=ZeroExt(1,Extract(15,0,p))+ZeroExt(1,Extract(15,0,s))
 delta=Extract(31,16,s)+ZeroExt(15,Extract(16,16,frac))
 total=ZeroExt(1,Extract(31,16,p))+ZeroExt(1,delta)
 candidate=Concat(Extract(16,16,total),delta)
 reference=ZeroExt(1,Extract(31,16,p+s))-ZeroExt(1,Extract(31,16,p))
 prove('row delta: unrestricted 32-bit inputs and exact 17-bit result',candidate,reference)
 # Negative control: an ordinary integer-step result loses the 17th borrow bit.
 a,b=0xffff0000,0x00010000
 wrapped=(((((a+b)&0xffffffff)>>16)-(a>>16))&0x1ffff)
 naive=(b>>16)+(((a&0xffff)+(b&0xffff))>>16)
 assert wrapped==0x10001 and naive==1 and wrapped!=naive
 print('PASS: rejects naive row identity at position overflow')
 for half in range(1,5):
  mask=(1<<(half*2))-1;low=(1<<half)-1
  for a in range(mask+1):
   for b in range(mask+1):
    d=((b>>half)+(((a&low)+(b&low))>>half))&low
    got=((((a>>half)+d)>>half)<<half)|d
    ref=((((a+b)&mask)>>half)-(a>>half))&((1<<(half+1))-1)
    assert got==ref
 print('PASS: exhaustive reduced-width arithmetic, fractional/integer/position wrap')

def qualify():
 n=BitVec('line',16);delay=BitVec('delay',6);start,first=Bool('begin'),Bool('first')
 upcoming=If(first,BitVecVal(0,16),n+1);now=If(start,upcoming,n)
 prove('first-line predicate under established line_begin',start&(now==ZeroExt(10,delay)),start&(upcoming==ZeroExt(10,delay)))

def address():
 slot,word=BitVec('slot',4),BitVec('word',9)
 prove('all read row/column fields',((ZeroExt(8,slot)>>1)*512+ZeroExt(3,word)),Concat(Extract(3,1,slot),word))
 for col in range(2561):
  group,lane=divmod(col,5); following=col+1 if col<2560 else col
  g=group+(lane==4) if col<2560 else group
  l=(lane+1)%5 if col<2560 else lane
  assert (g,l)==divmod(following,5)
  assert 0<=(group if col<2560 else 0)<512
 print('PASS: reachable quotient/remainder invariant, CE holds and saturation')

def vga():
 cnt,total=BitVec('count',16),BitVec('total',16)
 prove('VGA termination including zero and maximum total',
  UGE(ZeroExt(16,cnt),ZeroExt(16,total)-1),
  (total!=0)&UGE(ZeroExt(1,cnt)+1,ZeroExt(1,total)))

def sync():
 from z3 import Function,BitVecSort,BoolSort
 f=Bool('first_output'); slot=BitVec('continuing_slot',4); row=BitVec('continuing_row',16)
 ready=Function('ready',BitVecSort(4),BitVecSort(16),BoolSort())
 prove('first-row tag factoring before unchanged capture',
  ready(If(f,BitVecVal(0,4),slot),If(f,BitVecVal(0,16),row)),
  If(f,ready(BitVecVal(0,4),BitVecVal(0,16)),ready(slot,row)))

if __name__=='__main__':
 import sys
 names=sys.argv[1:] or ['row','qualify','address','vga']
 for name in names:globals()[name]()
