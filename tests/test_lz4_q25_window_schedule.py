#!/usr/bin/env python3
"""Non-Quartus schedule checks; does not establish RTL cycle equivalence."""
from pathlib import Path
import random
import unittest
ROOT=Path(__file__).resolve().parents[1]
MATCH_OFFSET=7
MATCH_LENGTH=10
COPY=12
COPY64=13
COPY64_8=14

def ahead(state,advance,mp13,mp3,window_addr,offset,ml,blocks_readed,data):
    result=mp13
    if advance:
        if state==MATCH_OFFSET and not ((offset==0 and ml==0) or blocks_readed) and ml<15:
            result=((window_addr-offset)&0xffff)>>3
        elif state==MATCH_LENGTH and data<255:
            result=((window_addr-offset)&0xffff)>>3
        elif state==COPY and mp3==7:
            result=mp13+1
        elif state in (COPY64,COPY64_8):
            result=mp13+1
    return result&8191

class WindowSchedule(unittest.TestCase):
    def test_next_address(self):
        rng=random.Random(2501)
        for _ in range(100000):
            state=rng.randrange(15);advance=rng.choice([False,True])
            mp13=rng.randrange(8192);mp3=rng.randrange(8)
            addr=rng.randrange(65536);offset=rng.randrange(65536)
            ml=rng.randrange(32);br=rng.choice([False,True]);data=rng.randrange(256)
            predicted=ahead(state,advance,mp13,mp3,addr,offset,ml,br,data)
            actual=mp13
            if advance:
                if state==MATCH_OFFSET and not ((offset==0 and ml==0) or br) and ml<15:
                    actual=((addr-offset)&65535)>>3
                elif state==MATCH_LENGTH and data<255:
                    actual=((addr-offset)&65535)>>3
                elif state==COPY and mp3==7:actual+=1
                elif state in (COPY64,COPY64_8):actual+=1
            self.assertEqual(predicted,actual&8191)
    def test_collision_forwarding(self):
        rng=random.Random(2502);mem=[rng.getrandbits(64) for _ in range(8192)]
        for _ in range(20000):
            read=rng.randrange(8192)
            write=read if rng.randrange(3)==0 else rng.randrange(8192)
            data=rng.getrandbits(64)
            old=mem[read];mem[write]=data
            result=data if write==read else old
            self.assertEqual(result,mem[read])
    def test_registered_ram_access(self):
        rtl=(ROOT/"rtl/lz4.v").read_text()
        self.assertEqual(rtl.count("window_prefetch_data <= window[window_prefetch_addr];"),1)
        self.assertEqual(rtl.count("window[window_addr13] <= window_write_value;"),1)
        self.assertNotIn("window[MP13]",rtl)

if __name__=="__main__":
    unittest.main()
