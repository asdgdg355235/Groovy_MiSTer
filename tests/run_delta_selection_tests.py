#!/usr/bin/env python3
"""Compile actual selector, LZ4 byte assignments & decode_pixel task vs baseline.

The wrapper models buffer writes and consumption, not the entire transport FSM.
The surrounding production FSM must stay byte-identical (checked below).
"""
from pathlib import Path
import os,shlex,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
BASE='c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17'
src=(ROOT/'Groovy.sv').read_text()
old=subprocess.check_output(['git','show',BASE+':Groovy.sv'],cwd=ROOT,text=True)
a=src.index('// Two combinational mux levels:');b=src.index('reg        PoC_lz4_delta_req;',a)
selector=src[a:b]
assert src[:a]+src[b:]==old.replace('PoC_lz4_delta_FB[PoC_lz4_delta_index])','PoC_lz4_delta_selected)')
task=src[src.index('task decode_pixel;'):src.index('endtask',src.index('task decode_pixel;'))+7]
lz4=(ROOT/'rtl/lz4.v').read_text();start=lz4.index('assign lz4_uncompressed_long[07:00]')
adds=lz4[start:lz4.index('assign lz4_long_valid',start)]
pre='''(input clk,reset,we,consume,input [6:0] idx,wridx,input [63:0] data,uncompressed_long,input [1:0] rgb_mode,input [23:0] total);
reg [63:0] PoC_lz4_delta_FB[128];
wire [6:0] PoC_lz4_delta_index=idx;
reg [7:0] r_vram_in1=0,g_vram_in1=0,b_vram_in1=0,r_vram_in2=0,g_vram_in2=0,b_vram_in2=0;
reg [7:0] r_vram_in3=0,g_vram_in3=0,b_vram_in3=0,r_vram_in4=0,g_vram_in4=0,b_vram_in4=0;
reg vram_wren1=0,vram_wren2=0,vram_wren3=0,vram_wren4=0;
reg [23:0] PoC_subframe_px_vram=0,PoC_subframe_px_lz4=0;
reg [1:0] PoC_frame_rgb_offset=0;reg [255:0] ddr_data_tmp=0;
wire [63:0] lz4_delta_long, lz4_uncompressed_long;
'''
tail='''always @(posedge clk) begin
 if(we) PoC_lz4_delta_FB[wridx]<=data;
 {vram_wren1,vram_wren2,vram_wren3,vram_wren4}<=0;
 if(reset) begin PoC_subframe_px_vram<=0;PoC_subframe_px_lz4<=0;PoC_frame_rgb_offset<=0;ddr_data_tmp<=0;end
 else if(consume) decode_pixel(1'b1,lz4_uncompressed_long,total);
end
endmodule
'''
tb='''module tb;
reg clk=0;always #5 clk=~clk;
reg reset=1,we=0,consume=0;reg [6:0] idx=0,wridx=0;reg [63:0] data=0,pixels=0;reg [1:0] mode=0;reg [23:0] total=0;
new_path d(clk,reset,we,consume,idx,wridx,data,pixels,mode,total);
old_path r(clk,reset,we,consume,idx,wridx,data,pixels,mode,total);
integer n,m,k,cycles=0;reg [31:0] random_state=32'hd311a;
function [31:0] rnd;begin random_state=random_state^(random_state<<13);random_state=random_state^(random_state>>17);random_state=random_state^(random_state<<5);rnd=random_state;end endfunction
 task tick;begin @(posedge clk);#1;
 if(d.lz4_delta_long!==r.lz4_delta_long || d.lz4_uncompressed_long!==r.lz4_uncompressed_long) $fatal(1,"delta selection %d",idx);
 if({d.r_vram_in1,d.g_vram_in1,d.b_vram_in1,d.r_vram_in2,d.g_vram_in2,d.b_vram_in2,d.r_vram_in3,d.g_vram_in3,d.b_vram_in3,d.r_vram_in4,d.g_vram_in4,d.b_vram_in4,d.vram_wren1,d.vram_wren2,d.vram_wren3,d.vram_wren4,d.PoC_subframe_px_vram,d.PoC_subframe_px_lz4,d.PoC_frame_rgb_offset,d.ddr_data_tmp} !==
 {r.r_vram_in1,r.g_vram_in1,r.b_vram_in1,r.r_vram_in2,r.g_vram_in2,r.b_vram_in2,r.r_vram_in3,r.g_vram_in3,r.b_vram_in3,r.r_vram_in4,r.g_vram_in4,r.b_vram_in4,r.vram_wren1,r.vram_wren2,r.vram_wren3,r.vram_wren4,r.PoC_subframe_px_vram,r.PoC_subframe_px_lz4,r.PoC_frame_rgb_offset,r.ddr_data_tmp}) $fatal(1,"decode/cycle %d",cycles);
 cycles=cycles+1;@(negedge clk);end endtask
initial begin
 // Define identical power-up contents; reset must not clear this buffer.
 for(n=0;n<128;n=n+1) begin d.PoC_lz4_delta_FB[n]={rnd(),rnd()};r.PoC_lz4_delta_FB[n]=d.PoC_lz4_delta_FB[n];end
 tick();
 for(m=0;m<4;m=m+1) begin mode=m;reset=1;tick();reset=0;
  for(k=0;k<4;k=k+1) begin
   // Partial refill, full refill and wrap at 127; old words must survive.
   for(n=0;n<(k==0?17:128);n=n+1) begin we=1;wridx=(n+125)%128;idx=wridx;data={rnd(),rnd()};consume=0;tick();end
   we=0;
   for(n=0;n<1024;n=n+1) begin idx=(n+125)%128;pixels={rnd(),rnd()};consume=n%7!=0;reset=n%127==0;total=d.PoC_subframe_px_vram+(n%8);tick();end
  end
 end
 $display("PASS: %d delta cycles; four pixel modes, partial/full refill, wrap, stalls, reset/restart",cycles);$finish;
end
endmodule
'''
with tempfile.TemporaryDirectory() as t:
 t=Path(t)
 (t/'path.sv').write_text('module new_path'+pre+selector+'assign lz4_delta_long=PoC_lz4_delta_selected;\n'+adds+task+'\n'+tail+'module old_path'+pre+'assign lz4_delta_long=PoC_lz4_delta_FB[idx];\n'+adds+task+'\n'+tail+tb)
 subprocess.run(shlex.split(os.environ.get('IVERILOG','iverilog'))+['-g2012','-s','tb','-o',str(t/'sim'),str(t/'path.sv')],check=True)
 subprocess.run(shlex.split(os.environ.get('VVP','vvp'))+[str(t/'sim')],check=True)
