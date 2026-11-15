#!/usr/bin/env python3
"""Compile the actual old/new emu video sections & compare bypass cycle-wise."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '735c777be2ec859afe3dc37cc448d49440447add'
HEADER = '''module NAME(input clk_sys,ce_pix,ce_pix2,RESET,
 input [127:0] status,input PoC_interlaced,PoC_FB_interlaced,
 input [7:0] r_core,g_core,b_core,input hsync_core,vsync_core,hblank_core,vblank_core,
 output [7:0] VGA_R,VGA_G,VGA_B,output VGA_HS,VGA_VS,VGA_DE,CE_PIXEL,
 output [12:0] VIDEO_ARX,VIDEO_ARY);
 wire CLK_VIDEO=clk_sys;
 wire forced_scandoubler=0, HDMI_FREEZE=0, crop_240p=0, no_rotate=1;
 wire [1:0] scandoubler_fx=status[4:3],ar=status[2:1],scale=status[6:5];
 wire [4:0] crop_offset=0;
 wire [11:0] HDMI_WIDTH=1920,HDMI_HEIGHT=1080;
 wire [21:0] gamma_bus;
 assign gamma_bus[20:0]=0;
 wire vga_reset=RESET,vga_soft_reset=0,new_modeline=0,req_modeline=0;
 wire [7:0] ce_pix_arm=7,PoC_HFP=4,PoC_HS=8,PoC_HBP=20;
 wire [7:0] PoC_VFP=2,PoC_VS=3,PoC_VBP=19;
 wire [15:0] PoC_H=64,PoC_V=240;
'''
INIT = '''initial begin
 jtframe_resync.field=0;
 jtframe_resync.last_LHBL=0;jtframe_resync.last_LVBL=0;
 jtframe_resync.last_hsin=0;jtframe_resync.last_vsin=0;
end
endmodule
'''

def section(source, name):
    start = source.index('wire hs_jt, vs_jt;')
    end = source.index('//////////////////////////////////// AUDIO', start)
    return HEADER.replace('NAME', name) + source[start:end] + INIT

def main():
    old = subprocess.check_output(['git', 'show', BASE + ':Groovy.sv'], cwd=ROOT, text=True)
    files = ['tests/tb_video_pipeline.sv', 'sys/video_mixer.sv', 'sys/video_freezer.sv',
             'sys/gamma_corr.sv', 'sys/scandoubler.v', 'sys/hq2x.sv', 'sys/math.sv',
             'sys/video_freak.sv', 'rtl/CRT/groovy_crt.sv', 'rtl/CRT/crt_adjust.sv', 'rtl/CRT/crt_vsize.sv']
    files += [str(x.relative_to(ROOT)) for x in (ROOT / 'rtl/JTFRAME').glob('*.v')]
    with tempfile.TemporaryDirectory(prefix='groovy-video-') as name:
        temp = Path(name)
        ref = temp / 'original.sv'
        changed = temp / 'changed.sv'
        ref.write_text(section(old, 'original_pipeline'))
        changed.write_text(section((ROOT / 'Groovy.sv').read_text(), 'changed_pipeline'))
        # The unchanged framework uses array assignment patterns & positional
        # omitted ports that Icarus 12 cannot elaborate. Verilator accepts
        # these source constructs without changing the framework for a test.
        for cabinet in (False, True):
            obj = temp / ('cabinet' if cabinet else 'base')
            cmd = shlex.split(os.environ.get('VERILATOR', 'verilator'))
            # Legacy hq2x declares a clocked output as wire. Quartus accepts
            # it; this frontend compatibility switch leaves its logic intact.
            cmd += ['--binary', '--timing', '-Wno-fatal', '-Wno-PROCASSWIRE',
                    '-Wno-BLKANDNBLK', '-DSIMULATION',
                    '--top-module', 'tb_video_pipeline', '--Mdir', str(obj), '-j', '2']
            if cabinet:
                cmd += ['-DGROOVY_CRT_CABINET']
            subprocess.run(cmd + [str(ref), str(changed)] + [str(ROOT / f) for f in files], check=True)
            subprocess.run([str(obj / 'Vtb_video_pipeline')], check=True)
            print('PASS: actual emu video section, Cabinet build =', cabinet, flush=True)
            if cabinet:
                obj = temp / 'enabled'
                enabled_cmd = cmd[:]
                enabled_cmd[enabled_cmd.index('--Mdir') + 1] = str(obj)
                enabled_cmd += ['-GENABLED=1']
                subprocess.run(enabled_cmd + [str(ref), str(changed)] + [str(ROOT / f) for f in files], check=True)
                subprocess.run([str(obj / 'Vtb_video_pipeline')], check=True)

if __name__ == '__main__':
    main()
