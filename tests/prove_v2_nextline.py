#!/usr/bin/env python3
"""Finite-width expression proof; not whole-design or fitted equivalence."""
from z3 import BitVec,BitVecVal,Extract,Concat,ZeroExt,LShR,Solver,unsat,sat,UGT

def prove():
    count=BitVec('vga_vcount',16);parity=BitVec('PoC_interlaced',1)
    old=ZeroExt(8,count)+BitVecVal(1,24)+ZeroExt(23,parity)
    upper=ZeroExt(1,Extract(15,1,count))+ZeroExt(15,Extract(0,0,count)|parity)
    new=ZeroExt(7,Concat(upper,~(Extract(0,0,count)^parity)))
    s=Solver();s.set(timeout=10000);s.add(old!=new);assert s.check()==unsat
    print('PASS: all 16-bit counters and both parity values, including 65536/65537')
    # Prove the complete changed context compositionally using the established lemma.
    h=BitVec('PoC_H',16);fb=BitVec('PoC_FB_interlaced',1);pixels=BitVec('vram_pixels',24)
    line_a=BitVec('proved_line_a',24);line_b=BitVec('proved_line_b',24)
    a=LShR(ZeroExt(8,h)*line_a,ZeroExt(23,fb));b=LShR(ZeroExt(8,h)*line_b,ZeroExt(23,fb))
    s=Solver();s.set(timeout=10000);s.add(line_a==line_b);s.add((a+3!=b+3) | (UGT(a,pixels)!=UGT(b,pixels)))
    assert s.check()==unsat
    print('PASS: 24-bit product truncation before shift, pixel update and decision comparison')
    bad=ZeroExt(8,count+1+ZeroExt(15,parity))
    s=Solver();s.add(old!=bad);assert s.check()==sat
    print('PASS: rejects an incorrectly wrapped 16-bit next-line operand')
if __name__=='__main__':prove()
