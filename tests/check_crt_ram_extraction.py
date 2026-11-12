#!/usr/bin/env python3
"""Source-preservation checks plus an independent reference packing/bank model.

This is NOT RTL simulation or Quartus synthesis. It checks the extracted
interfaces and compares the original 120-bit word model against six 40-bit lanes.
"""
import os
import random
import re
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
def baseline_source():
    path = os.environ.get('CRT_RAM_BASELINE')
    if path:
        return Path(path).read_text()
    try:
        return subprocess.check_output(['git', 'show', '00136c5f03de63d80d8e78208bb6802cfe53c53d:rtl/CRT/crt_vsize_fixed.sv'],
                                       cwd=ROOT, stderr=subprocess.DEVNULL, text=True)
    except (OSError, subprocess.CalledProcessError):
        return None

BASELINE = baseline_source()
NEW = (ROOT / 'rtl/CRT/crt_vsize_fixed.sv').read_text()
RAM = (ROOT / 'rtl/CRT/crt_packed_ram.sv').read_text()
START = '    wire [GROUP_BITS-1:0] qe, qo;\n'
END = '    reg [2:0] read_lane;\n'

class ExtractionChecks(unittest.TestCase):
    def test_ram_region_and_video_pipeline_preserved(self):
        if BASELINE is not None:
            # Timing arithmetic changes before the memory region are checked
            # by RTL equivalence/SMT, not by a whole-prefix text comparison.
            self.assertEqual(BASELINE[BASELINE.index(START):BASELINE.index(END)],
                             NEW[NEW.index(START):NEW.index(END)])
            # Only the existing valid-bit input is factored across line_begin;
            # all registers/stages and the other seven control bits stay exact.
            pipeline=BASELINE[BASELINE.index(END):].replace(
                'output_now && !hb_in && !vs_in && pair_ready && !dividing}',
                'line_begin ? valid_line : valid_current}')
            self.assertEqual(pipeline, NEW[NEW.index(END):])
        self.assertIn('wire write_even = write_pixel && flush_group && !write_slot[0];', NEW)
        self.assertIn('wire write_odd  = write_pixel && flush_group &&  write_slot[0];', NEW)
        for x in ['wa', 'ra_even', 'ra_odd', 'write_pixel', 'flush_group', 'pack_next', 'read_lane']:
            self.assertIn(x, NEW)

    def test_memory_synchronous_and_unreset(self):
        self.assertEqual(RAM.count('reg [39:0] mem [0:BANK_WORDS-1];'), 2)
        self.assertEqual(RAM.count('q <= mem[ra];'), 2)
        self.assertEqual(RAM.count('mem[wa] <= d;'), 2)
        self.assertEqual(RAM.count('always @(posedge clk)'), 2)
        self.assertNotRegex(RAM, r'if\s*\(\s*reset\b|@\s*\(\s*negedge')
        self.assertEqual(len(re.findall(r'\bcrt_packed_ram\s*#\s*\(', NEW)), 2)
        self.assertIn('.USE_MLAB(part < MLAB_PARTS)', NEW)
        self.assertEqual(NEW.count('.wa(wa)'),2)
        self.assertEqual(NEW.count('.we(write_even)'),1)
        self.assertEqual(NEW.count('.we(write_odd)'),1)
        self.assertEqual(NEW.count('.ra(local_ra_even)'),1)
        self.assertEqual(NEW.count('.ra(local_ra_odd)'),1)
        self.assertEqual(NEW.count('.d(pack_next[part*40 +: 40])'),2)
        self.assertEqual(NEW.count('.q(qe[part*40 +: 40])'),1)
        self.assertEqual(NEW.count('.q(qo[part*40 +: 40])'),1)

    def test_random_packing_and_registered_read_model(self):
        r = random.Random(0x43415254)
        # Original: two banks of 120-bit words. Extracted: six 40-bit banks.
        old = [dict(),dict()]
        extracted = [[dict() for _ in range(3)] for _ in range(2)]
        pack = 0
        mask40=(1<<40)-1
        mask24=(1<<24)-1
        qold=[0,0]
        qnew=[0,0]
        for cycle in range(16000):
            col=r.randrange(2560)
            lane=col%5
            slot=r.randrange(12)
            read_slot=r.randrange(12)
            read_col=r.randrange(2560)
            rgb=r.getrandbits(24)
            width=r.choice([2560,1920,640,639,320])
            write_pixel=(col < width) and bool(r.getrandbits(1))
            flush= lane==4 or col==width-1
            next_pack = (0 if lane==0 else pack) & ~(mask24<<(lane*24))
            next_pack |=rgb<<(lane*24)
            # Read before edge writes, matching each nonblocking clocked read.
            next_slot=(read_slot+1)%12
            even_slot=next_slot if read_slot&1 else read_slot
            odd_slot=read_slot if read_slot&1 else next_slot
            addr_even=(even_slot//2)*512 + read_col//5
            addr_odd=(odd_slot//2)*512 + read_col//5
            read_addrs=[addr_even,addr_odd]
            qold=[old[b].get(read_addrs[b],0) for b in range(2)]
            qnew=[sum(extracted[b][part].get(read_addrs[b],0)<<(40*part)
                         for part in range(3)) for b in range(2)]
            self.assertEqual(qold,qnew, f'read mismatch at cycle {cycle}')
            # Every source slot holds 512 words; parity chooses bank.
            if write_pixel and flush:
                bank=slot&1
                addr=(slot//2)*512 + col//5
                old[bank][addr]=next_pack
                for part in range(3):
                    extracted[bank][part][addr]=(next_pack>>(part*40)) & mask40
            if write_pixel:
                pack=next_pack
            pos=r.randrange(5)
            for b in range(2):
                self.assertEqual((qold[b]>>(pos*24))&mask24,
                                 (qnew[b]>>(pos*24))&mask24)
        self.assertGreater(sum(map(len,old)),100)

if __name__=='__main__':
    unittest.main(verbosity=2)
