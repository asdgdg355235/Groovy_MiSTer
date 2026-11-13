#!/usr/bin/env python3
"""Audit original write expressions against the changed single-port RAM writer."""
from pathlib import Path
import re,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
BASE="c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17"

def norm(expr):
    value=re.sub(r"\s+","",expr.replace("window[MP13]","window_read_word"))
    return value[1:-1] if value.startswith("{") and value.endswith("}") else value

class SourceContract(unittest.TestCase):
    def test_write_values(self):
        old=subprocess.check_output(["git","show",BASE+":rtl/lz4.v"],cwd=ROOT,text=True)
        candidate=(ROOT/"rtl/lz4.v").read_text()
        first=candidate.index("// One explicit write port")
        last=candidate.index("always @(posedge lz4_clk)",first)
        writer=candidate[first:last]
        combined=r"\{uncompressed_long,\s*window\[window_addr13\]\}\s*<=\s*\{2\{(?P<combined>[^;]*?)\}\};"
        direct=r"window\[window_addr13\]\s*<=\s*(?P<direct>[^;]*);"
        before=[norm(m.group("combined") or m.group("direct"))
                for m in re.finditer(combined+"|"+direct,old,flags=re.S)]
        after=[norm(x) for x in re.findall(r"\bwindow_write_value\s*=\s*([^;]+);",writer,flags=re.S)[1:]]
        self.assertEqual(26,len(before))
        self.assertEqual(before,after)
    def test_output_updates_survive(self):
        old=subprocess.check_output(["git","show",BASE+":rtl/lz4.v"],cwd=ROOT,text=True)
        new=(ROOT/"rtl/lz4.v").read_text()
        combined=len(re.findall(r"\{uncompressed_long,\s*window\[window_addr13\]\}",old))
        self.assertEqual(17,combined)
        self.assertEqual(combined,len(re.findall(r"uncompressed_long\s*<=\s*\{",new))
                         -len(re.findall(r"uncompressed_long\s*<=\s*\{",old)))

if __name__=="__main__":unittest.main()
