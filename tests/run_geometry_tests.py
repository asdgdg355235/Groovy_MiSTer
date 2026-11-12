#!/usr/bin/env python3
"""Geometry simulation and core elaboration. Requires Icarus, Verilator and C++."""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '735c777be2ec859afe3dc37cc448d49440447add'

def compile_run(tmp, top, sources, parameters=()):
    build = tmp/top
    cmd = shlex.split(os.environ.get('VERILATOR','verilator'))
    result = subprocess.run(cmd+['--binary','--timing','-DSIMULATION','-Wno-fatal',
                            '--top-module',top,'-j','2','--Mdir',str(build)] + list(parameters) +
                            [str(p) for p in sources], stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if result.returncode:
        print(result.stdout)
        result.check_returncode()
    subprocess.run([str(build/('V'+top))],check=True)

def function(source, signature):
    start=source.index(signature)
    return source[start:source.index('\n}',start)+2]

def status_test(tmp, framework):
    source=(framework/'user_io.cpp').read_text()
    prelude='''#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cassert>
#include <vector>
static char cur_status[16]={};
static std::vector<uint16_t> sent;
bool is_st(){return false;}
uint32_t minimig_core_extcfg(){return 0;}
bool is_minimig(){return false;}
enum {UIO_SET_STATUS2=0};
void spi_uio_cmd_cont(int) {sent.clear();}
void spi_w(uint16_t x) {sent.push_back(x);}
void DisableIO(){}
int user_io_status_bits(const char*,int*,int*,int,int single=0);
'''
    code=prelude+'\n'.join(function(source,s) for s in
            ['int user_io_status_bits(', 'uint32_t user_io_status_get(', 'void user_io_status_set('])
    code+='''
int main(){
user_io_status_set("[21:17]",31,0); user_io_status_set("[26:22]",7,0);
user_io_status_set("[51:48]",15,0); user_io_status_set("[63:60]",14,0);
user_io_status_set("[67:64]",15,0); user_io_status_set("[71:68]",9,0); user_io_status_set("[72]",1,0);
assert(user_io_status_get("[21:17]",0)==31); assert(user_io_status_get("[26:22]",0)==7);
assert(user_io_status_get("[51:48]",0)==15); assert(user_io_status_get("[63:60]",0)==14);
assert(user_io_status_get("[67:64]",0)==15); assert(user_io_status_get("[71:68]",0)==9);
assert(user_io_status_get("[72]",0)==1); assert(sent.size()==8);
char saved[16]; memcpy(saved,cur_status,16); memset(cur_status,0,16); memcpy(cur_status,saved,16);
assert(user_io_status_get("[72]",0)==1); // byte-for-byte configuration round trip
memset(cur_status,0,16);
user_io_status_set("[68:67]",3,0); // NES core's unrelated Overscan option
user_io_status_set("T",1,0); // Genesis Border, legacy option syntax
assert(user_io_status_get("[68:67]",0)==3); assert(user_io_status_get("T",0)==1);
assert(user_io_status_get("[63:60]",0)==0);
puts("PASS: actual Main status encode/decode, 128-bit SPI, configuration bytes and legacy core options");
}
'''
    cpp=tmp/'status.cpp'; cpp.write_text(code)
    out=tmp/'status'
    subprocess.run(['g++','-std=c++17','-funsigned-char',str(cpp),'-o',str(out)],check=True)
    subprocess.run([str(out)],check=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--crt-adjust',type=Path,help='CRT Adjust checkout for shared RTL regression suite')
    parser.add_argument('--main',type=Path,help='Main_MiSTer fork for status/menu compatibility test')
    args=parser.parse_args()
    if args.crt_adjust:
        crt=args.crt_adjust.resolve()
        for name in ['crt_vsize_fixed.sv','crt_edge_mask.sv']:
            assert (ROOT/'rtl/CRT'/name).read_bytes()==(crt/'rtl'/name).read_bytes(), 'vendored RTL mismatch: '+name
        subprocess.run([os.environ.get('PYTHON','python3'),str(crt/'tests/run_tests.py')],check=True)
    text=(ROOT/'Groovy.sv').read_text()
    options=re.findall(r'"[^"\n]*O\[(\d+)(?::(\d+))?\],[^"\n]*"',text)
    occupied=set()
    for end,start in options:
        end=int(end); start=int(start or end)
        bits=set(range(start,end+1))
        assert not occupied & bits, ('OSD status overlap', bits & occupied)
        occupied |= bits
    # VGA arithmetic and LZ4 counter/delta changes have dedicated reference tests.
    for path in ['rtl/hps_ext.v','rtl/sound.v',
                 'hps_linux/src/input.cpp','hps_linux/src/support/groovy/groovy.cpp']:
        inherited=subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
        assert (ROOT/path).read_bytes()==inherited, 'unexpected protocol/controller/audio/timing change: '+path
    framework=(ROOT/'sys/sys_top.v').read_text()
    inactive_hdmi = '''// With ascal absent, retain the mapped inactive value explicitly. The palette
// edge detector must not consume an undriven net. HDMI remains disabled.
`ifdef MISTER_DEBUG_NOHDMI
assign hdmi_vs = 1'b0;
`endif

'''
    assert framework.count(inactive_hdmi) == 1
    framework = framework.replace(inactive_hdmi, '')
    without_anchor=re.sub(r'`ifdef GROOVY_CRT_GEOMETRY\n.*?`endif\n','',framework,flags=re.S)
    original_framework=subprocess.check_output(['git','show',BASE+':sys/sys_top.v'],cwd=ROOT).decode()
    assert without_anchor==original_framework, 'unexpected framework change for unrelated cores'
    qip=(ROOT/'files.qip').read_text()
    for name in ['crt_vsize_fixed','crt_edge_mask']:
        assert 'rtl/CRT/'+name+'.sv' in qip
    print('PASS: OSD fields do not overlap; protocol, controller and audio sources retained; VGA/LZ4 checked separately')
    with tempfile.TemporaryDirectory(prefix='groovy-geometry-') as temp:
        tmp=Path(temp)
        if args.main: status_test(tmp,args.main.resolve())
        original=subprocess.check_output(['git','show',BASE+':rtl/JTFRAME/jtframe_hsize.v'],cwd=ROOT).decode()
        old=tmp/'hsize_reference.v'
        old.write_text(original.replace('module jtframe_hsize','module jtframe_hsize_reference'))
        compile_run(tmp,'tb_hsize',[ROOT/'tests/tb_hsize.sv',old,*sorted((ROOT/'rtl/JTFRAME').glob('jtframe_hsize.v')),
                    ROOT/'rtl/JTFRAME/jtframe_linebuf.v',ROOT/'rtl/JTFRAME/jtframe_rpwp_ram.v'])
        video_reference = tmp/'vga_reference.v'
        video_reference.write_text(subprocess.check_output(
            ['git', 'show', '00136c5f03de63d80d8e78208bb6802cfe53c53d:rtl/vga.v'], cwd=ROOT, text=True)
            .replace('module vga (', 'module vga_reference (', 1))
        compile_run(tmp,'tb_video_geometry',[ROOT/'tests/tb_video_geometry.sv',ROOT/'tests/rtl_models.sv',
                    ROOT/'rtl/vga.v',ROOT/'rtl/binary_to_bcd.v',ROOT/'rtl/CRT/crt_vsize_fixed.sv',
                    ROOT/'rtl/CRT/crt_packed_ram.sv',video_reference], ['-DTIMING_REFERENCE'])
        old_osd=tmp/'osd_reference.v'
        old_osd.write_text(subprocess.check_output(['git','show',BASE+':sys/osd.v'],cwd=ROOT).decode().replace('module osd','module osd_reference',1))
        for macro in [False,True]:
            compile_run(tmp,'tb_osd_anchor',[ROOT/'tests/tb_osd_anchor.sv',ROOT/'sys/osd.v',old_osd],
                        ['-Wno-BLKANDNBLK']+(['-DGROOVY_CRT_GEOMETRY'] if macro else []))
        # Verilator rejects Quartus's unpacked wire declaration initializer.
        # Spell the same continuous assignment explicitly in this temporary copy.
        normal=text.replace("wire [31:0] PLL_ARM_F[PLL_PARAM_F_COUNT * 2] = '{",
                            "wire [31:0] PLL_ARM_F[PLL_PARAM_F_COUNT * 2];\nassign PLL_ARM_F = '{")
        top=tmp/'Groovy.sv'; top.write_text(normal)
        (tmp/'build_id.v').write_text('`define BUILD_DATE "simulation"\n')
        sources=[top,ROOT/'tests/rtl_models.sv',*sorted((ROOT/'rtl/CRT').glob('*.sv')),
                 *sorted((ROOT/'rtl/JTFRAME').glob('*.v'))]
        sources += [ROOT/p for p in ['rtl/vga.v','rtl/hps_ext.v','rtl/ddram.sv','rtl/sound.v',
                    'rtl/lz4.v','rtl/binary_to_bcd.v','sys/hq2x.sv','sys/math.sv']]
        cmd=shlex.split(os.environ.get('VERILATOR','verilator'))
        result=subprocess.run(cmd+['--lint-only','--bbox-unsup','-Wno-fatal',
                    '-Wno-PROCASSWIRE','-Wno-BLKANDNBLK','-DGROOVY_CRT_GEOMETRY','--top-module','emu',
                    '-I'+str(ROOT),'-I'+str(ROOT/'sys'),'-I'+str(tmp)]+[str(p) for p in sources],
                    cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        if result.returncode:
            print(result.stdout); result.check_returncode()
        # These waivers cover inherited Quartus net assignments and block-local
        # initialization. PLLs, Intel FIFO IP and VHDL debug overlay are models.
        print('PASS: complete emu RTL elaborates with explicit vendor/VHDL models and inherited frontend waivers')

if __name__=='__main__':
    main()
