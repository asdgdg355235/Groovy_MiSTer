#!/usr/bin/env python3
"""Cycle-based independent reference check for CRT division-by-five replacement.

This is a high-level model, not an RTL simulator or Quartus timing validation.
For actual HDL simulation, run tests/run_crt_group_address_rtl.sh.
"""
from dataclasses import dataclass
from pathlib import Path
import random
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "rtl/CRT/crt_vsize_fixed.sv").read_text()

LINE_PX = 2560
GROUP_PX = 5
LINE_WORDS = LINE_PX // GROUP_PX
BANK_WORDS = 3072
RING_LINES = 12
MASK120 = (1 << 120) - 1
MASK24 = (1 << 24) - 1

@dataclass
class State:
    wcol: int = 0
    group: int = 0
    lane: int = 0
    hb_d: int = 1
    vs_d: int = 0
    started: int = 0
    wslot: int = 0


def evaluate(s, *, ce, hb, vb, vs, reset, running, width, rgb, slot_now, pack):
    line_begin = bool(ce and not hb and s.hb_d)
    first_source = bool(not s.started and not vb)
    field_begin = bool(ce and vs and not s.vs_d)
    col_now = 0 if line_begin else s.wcol
    group_now = 0 if line_begin else s.group
    lane_now = 0 if line_begin else s.lane
    read_col = col_now if col_now < LINE_PX else 0
    read_group = group_now if col_now < LINE_PX else 0
    read_lane = lane_now if col_now < LINE_PX else 0
    # The field/line state is intentionally minimal. The original and new
    # group-address functions are exercised with the same source slots.
    write_slot = ((0 if first_source else (s.wslot+1) % 12)
                  if line_begin and not vb else s.wslot)
    bslot = (slot_now + 1) % RING_LINES
    even_slot = bslot if slot_now & 1 else slot_now
    odd_slot = slot_now if slot_now & 1 else bslot
    old_wa = ((write_slot // 2) * LINE_WORDS + col_now // GROUP_PX) & 4095
    new_wa = ((write_slot // 2) * LINE_WORDS + group_now) & 4095
    old_reads = tuple(((slot // 2) * LINE_WORDS + read_col // GROUP_PX) & 4095
                      for slot in (even_slot, odd_slot))
    new_reads = tuple(((slot // 2) * LINE_WORDS + read_group) & 4095
                      for slot in (even_slot, odd_slot))
    write_pixel = bool(running and not reset and ce and not hb and not vb
                       and col_now < LINE_PX and col_now < width)
    flush_old = col_now % GROUP_PX == 4 or col_now == width-1
    flush_new = lane_now == 4 or col_now == width-1
    pold = (0 if col_now % GROUP_PX == 0 else pack)
    pold = (pold & ~(MASK24 << ((col_now % GROUP_PX)*24))) | (rgb << ((col_now % GROUP_PX)*24))
    pnew = (0 if lane_now == 0 else pack)
    pnew = (pnew & ~(MASK24 << (lane_now*24))) | (rgb << (lane_now*24))
    return (line_begin, first_source, field_begin, col_now, old_wa, new_wa,
            old_reads, new_reads, write_pixel, flush_old, flush_new,
            pold & MASK120, pnew & MASK120, read_lane,
            write_slot)


def edge(s, *, ce, hb, vb, vs, reset, ev):
    (line_begin, first_source, field_begin, *_tail) = ev
    if ce:
        old_hb = s.hb_d
        s.hb_d = int(bool(hb))
        s.vs_d = int(bool(vs))
        if line_begin and (s.started or first_source):
            s.started = 1
            s.wcol = 1
            s.group = 0
            s.lane = 1
            if not vb:
                s.wslot = 0 if first_source else (s.wslot+1)%12
        elif not hb and s.wcol < LINE_PX:
            s.wcol += 1
            if s.lane == 4:
                s.lane = 0
                s.group += 1
            else:
                s.lane += 1
    if field_begin:
        s.started = 0
        s.wslot = 0
    if reset:
        s.started = 0
        s.hb_d = 1
        s.vs_d = 0
    assert s.wcol == s.group*5+s.lane, (s,ev)


class CRTGroupAddressTest(unittest.TestCase):
    def test_source_retains_memory_configuration(self):
        self.assertEqual(SRC.count("crt_packed_ram #("), 2)
        self.assertEqual(SRC.count(".USE_MLAB(part < MLAB_PARTS)"), 2)
        self.assertIn(".wa(wa)", SRC)
        self.assertEqual(SRC.count(".wa(wa)"), 2)
        self.assertIn("read_lane <= read_column_in_range ? lane_now : 3'd0;", SRC)
        no_comments = "\n".join(x.split('//')[0] for x in SRC.splitlines())
        self.assertNotRegex(no_comments, r"(?<!\w)(?:wcol|col_now|read_col)\s*[/%]")
        self.assertEqual(len(re.findall(r"/\s*GROUP_PX", no_comments)), 1)  # constant LINE_WORDS only
        self.assertNotRegex(no_comments, r"%\s*GROUP_PX")
        self.assertIn("LINE_WORDS = (LINE_PX+GROUP_PX-1)/GROUP_PX", SRC)
        self.assertEqual(SRC.count("q(qe[part*40 +: 40])"), 1)
        self.assertEqual(SRC.count("q(qo[part*40 +: 40])"), 1)

    def test_all_valid_columns_and_end_saturation(self):
        lane=0
        group=0
        for col in range(LINE_PX+1):
            for slot in range(RING_LINES):
                old = (slot//2)*LINE_WORDS + col//5
                new = (slot//2)*LINE_WORDS + group
                self.assertEqual(new,old)
            self.assertEqual((group,lane), divmod(col,5))
            if lane == 4:
                lane=0
                group+=1
            else:
                lane+=1

    def test_clocked_stalls_blankings_resets_ram_and_pack(self):
        r = random.Random(0x5354524F)
        state = State()
        old_mem = [[{} for _ in range(3)] for _ in range(2)]
        new_mem = [[{} for _ in range(3)] for _ in range(2)]
        old_pack = 0
        new_pack = 0
        old_q = [None,None]
        new_q = [None,None]
        writes=0
        reads=0
        stalls=0
        group_crossings=0
        line_starts=0
        field_starts=0
        saturated=0
        widths=[1,4,5,6,319,320,639,640,1919,1920,2559,2560]
        width=2560
        line_cycle=0
        length=2800
        vs=0
        running=True
        for cycle in range(210_000):
            if line_cycle == 0:
                length=r.choice([10,322,642,1950,2580,2800])
                width=r.choice(widths)
                if cycle and r.randrange(8)==0:
                    vs=1
                else:
                    vs=0
            hb=int(line_cycle < 3 or line_cycle >= length-8)
            vb=int(vs and line_cycle < 4)
            ce=not (r.randrange(6)==0)
            reset=bool(cycle>0 and cycle % 21317 == 0)
            rgb=r.getrandbits(24)
            slot_now=r.randrange(RING_LINES)
            ev=evaluate(state,ce=ce,hb=hb,vb=vb,vs=vs,reset=reset,
                        running=running,width=width,rgb=rgb,slot_now=slot_now,pack=old_pack)
            _,_,field_begin,col_now,old_wa,new_wa,old_ra,new_ra,wp,fo,fn,po,pn,read_lane,write_slot=ev
            # Model the proposed design independently with its own previous pack.
            ev_new=evaluate(state,ce=ce,hb=hb,vb=vb,vs=vs,reset=reset,
                            running=running,width=width,rgb=rgb,slot_now=slot_now,pack=new_pack)
            self.assertEqual(old_wa,new_wa,(cycle,col_now,state))
            self.assertEqual(old_ra,new_ra,(cycle,col_now,state))
            self.assertEqual(col_now % 5, 0 if ev[0] else state.lane)
            self.assertEqual(read_lane, (col_now%5 if col_now<LINE_PX else 0))
            self.assertEqual(fo,fn)
            self.assertEqual(po,ev_new[12])
            if not ce: stalls+=1
            if ev[0]: line_starts+=1
            if field_begin: field_starts+=1
            if state.wcol==LINE_PX: saturated+=1
            if wp and fn and state.lane==4: group_crossings+=1
            # Old data at the registered read ports is returned before writes.
            for bank in (0,1):
                old_lanes = [old_mem[bank][part].get(old_ra[bank]) for part in range(3)]
                new_lanes = [new_mem[bank][part].get(new_ra[bank]) for part in range(3)]
                self.assertEqual(old_lanes,new_lanes,(cycle,bank))
                old_q[bank] = (sum(x << (40*part) for part,x in enumerate(old_lanes))
                               if all(x is not None for x in old_lanes) else None)
                new_q[bank] = (sum(x << (40*part) for part,x in enumerate(new_lanes))
                               if all(x is not None for x in new_lanes) else None)
                if old_q[bank] is not None:
                    reads+=1
                    self.assertEqual((old_q[bank]>>(24*read_lane)) & MASK24,
                                     (new_q[bank]>>(24*read_lane)) & MASK24)
            if wp and fo:
                bank = write_slot & 1
                for part in range(3):
                    old_mem[bank][part][old_wa] = (po>>(40*part)) & ((1<<40)-1)
                    new_mem[bank][part][new_wa] = (ev_new[12]>>(40*part)) & ((1<<40)-1)
                writes+=1
            if wp:
                old_pack=po
                new_pack=ev_new[12]
            edge(state,ce=ce,hb=hb,vb=vb,vs=vs,reset=reset,ev=ev)
            line_cycle+=1
            if line_cycle>=length: line_cycle=0
        self.assertGreater(writes,400)
        self.assertGreater(stalls,1000)
        self.assertGreater(group_crossings,100)
        self.assertGreater(line_starts,10)
        self.assertGreater(reads,1000)
        self.assertGreater(saturated,50)
        for b in (0,1):
            for part in range(3):
                self.assertEqual(old_mem[b][part],new_mem[b][part])
        print(f'  cycles=210000 writes={writes} comparable_reads={reads} stalls={stalls}'
              f' line_starts={line_starts} field_starts={field_starts}'
              f' saturated={saturated} bank_entries={sum(len(p) for b in old_mem for p in b)}')


if __name__=='__main__':
    unittest.main(verbosity=2)
