#!/usr/bin/env python3
"""Actual read-selector/byte-add/decode task comparison; wrapper clock controls.

Does not simulate the whole DDR FSM. A byte comparison guards all unchanged
root state/update logic, while this harness exercises refill and consumption.
"""
import os,shlex,subprocess,tempfile,sys
from pathlib import Path
from experiments import ROOT,baseline
root=Path(sys.argv[1]); src=(root/'Groovy.sv').read_text();old=baseline('Groovy.sv').decode()
if '// Independent experiment:' in src:
 a=src.index('// Independent experiment:');b=src.index('reg        PoC_lz4_delta_req;',a)
 select=src[a:b]
 expected=old.replace('(PoC_lz4_delta_FB[PoC_lz4_delta_index])      ','(delta_read_value)')
 assert src[:a]+src[b:]==expected
else:
 # The physical experiments keep the original selector. Exercise that actual
 # binding without applying either rejected hierarchical-selector patch.
 assert src==old,'Flat-selector test requires untouched baseline root state/decode'
 assert src.count('(PoC_lz4_delta_FB[PoC_lz4_delta_index])')==1
 select='wire [63:0] delta_read_value=PoC_lz4_delta_FB[PoC_lz4_delta_index];\n'
# The approved Q25 decoder changes only the window RAM schedule. The delta
# selector is checked here, while the full decoder gets a separate
# original-source differential simulation in both modes.
from physical.control import hardware_hashes
hardware_hashes(root, 'q25')
task=src[src.index('task decode_pixel;'):src.index('endtask',src.index('task decode_pixel;'))+7]
lz4=(root/'rtl/lz4.v').read_text();start=lz4.index('assign lz4_uncompressed_long[07:00]')
addition=lz4[start:lz4.index('assign lz4_long_valid',start)]
head='''(input clk,reset,write,consume,input [6:0] index,write_index,input [63:0] data,uncompressed_long,input [1:0] rgb_mode,input [23:0] total);
reg [63:0] PoC_lz4_delta_FB[128];wire [6:0] PoC_lz4_delta_index=index;
wire [63:0] lz4_delta_long,lz4_uncompressed_long;
reg [7:0] r_vram_in1=0,g_vram_in1=0,b_vram_in1=0,r_vram_in2=0,g_vram_in2=0,b_vram_in2=0,r_vram_in3=0,g_vram_in3=0,b_vram_in3=0,r_vram_in4=0,g_vram_in4=0,b_vram_in4=0;
reg vram_wren1=0,vram_wren2=0,vram_wren3=0,vram_wren4=0;
reg [23:0] PoC_subframe_px_vram=0,PoC_subframe_px_lz4=0;
reg [1:0] PoC_frame_rgb_offset=0;reg [255:0] ddr_data_tmp=0;
'''
tail='''always @(posedge clk) begin
 if(write) PoC_lz4_delta_FB[write_index]<=data;
 {vram_wren1,vram_wren2,vram_wren3,vram_wren4}<=0;
 if(reset) begin PoC_subframe_px_vram<=0;PoC_subframe_px_lz4<=0;PoC_frame_rgb_offset<=0;ddr_data_tmp<=0;end
 else if(consume) decode_pixel(1'b1,lz4_uncompressed_long,total);
end
endmodule
'''
observed=['r_vram_in1','g_vram_in1','b_vram_in1','r_vram_in2','g_vram_in2','b_vram_in2','r_vram_in3','g_vram_in3','b_vram_in3','r_vram_in4','g_vram_in4','b_vram_in4','vram_wren1','vram_wren2','vram_wren3','vram_wren4','PoC_subframe_px_vram','PoC_subframe_px_lz4','PoC_frame_rgb_offset','ddr_data_tmp']
check=lambda x:'{'+','.join(x+'.'+n for n in observed)+'}'
tb='''module tb;
reg clk=0;always #5 clk=~clk;
reg reset=1,write=0,consume=0;reg [6:0] index=0,write_index=0;reg [63:0] data=0,pixels=0;reg [1:0] mode=0;reg [23:0] total=0;
candidate dut(clk,reset,write,consume,index,write_index,data,pixels,mode,total);
reference ref0(clk,reset,write,consume,index,write_index,data,pixels,mode,total);
integer i,m,refill,cycles=0;reg [31:0] state=32'h843616;
function [31:0] random_word;begin state=state^(state<<13);state=state^(state>>17);state=state^(state<<5);random_word=state;end endfunction
task tick;begin @(posedge clk);#1;
 if(dut.lz4_delta_long!==ref0.lz4_delta_long || dut.lz4_uncompressed_long!==ref0.lz4_uncompressed_long) $fatal(1,"delta word mismatch");
 if(CHECK) $fatal(1,"pixel update mismatch at %d",cycles);
 cycles=cycles+1;@(negedge clk);end endtask
initial begin
 for(i=0;i<128;i=i+1) begin dut.PoC_lz4_delta_FB[i]={random_word(),random_word()};ref0.PoC_lz4_delta_FB[i]=dut.PoC_lz4_delta_FB[i];end
 tick();
 for(m=0;m<4;m=m+1) begin
  mode=m;reset=1;tick();reset=0;
  for(refill=0;refill<5;refill=refill+1) begin
   for(i=0;i<(refill%2?128:19);i=i+1) begin
    write=1;write_index=(i+123)%128;index=write_index;data={random_word(),random_word()};consume=0;tick();
   end
   write=0;
   for(i=0;i<1024;i=i+1) begin
    index=(i+125)%128;pixels={random_word(),random_word()};reset=i%131==0;consume=i%9!=0;
    total=dut.PoC_subframe_px_vram+i%8;tick();
   end
  end
 end
 $display("PASS: %d actual delta/decode cycles, all modes, refill/wrap/reset/stalls",cycles);$finish;
end
endmodule
'''.replace('CHECK',check('dut')+' !== '+check('ref0'))
with tempfile.TemporaryDirectory() as t:
 t=Path(t);p=t/'delta.sv'
 p.write_text('module candidate'+head+select+'assign lz4_delta_long=delta_read_value;\n'+addition+task+'\n'+tail+'module reference'+head+'assign lz4_delta_long=PoC_lz4_delta_FB[index];\n'+addition+task+'\n'+tail+tb)
 subprocess.run(shlex.split(os.environ.get('IVERILOG','iverilog'))+['-g2012','-s','tb','-o',str(t/'sim'),str(p)],check=True)
 subprocess.run(shlex.split(os.environ.get('VVP','vvp'))+[str(t/'sim')],check=True)
