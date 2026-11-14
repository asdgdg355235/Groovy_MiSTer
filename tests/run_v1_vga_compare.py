#!/usr/bin/env python3
"""Actual VGA RTL cycle comparison plus extracted root frame-skip updates."""
from pathlib import Path
import os,re,shlex,subprocess,tempfile,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from physical.variants import apply_variant,variant
BASE='3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a'

def run():
 original=subprocess.check_output(['git','show',BASE+':rtl/vga.v'],cwd=ROOT,text=True)
 root=subprocess.check_output(['git','show',BASE+':Groovy.sv'],cwd=ROOT,text=True)
 assert (ROOT/'Groovy.sv').read_text()==root
 with tempfile.TemporaryDirectory(prefix='v1-cycle-') as temp:
  temp=Path(temp);(temp/'rtl').mkdir();(temp/'rtl/vga.v').write_text(original);apply_variant(temp)
  candidate=temp/'rtl/vga.v';reference=temp/'reference.v';reference.write_text(original.replace('module vga (','module vga_reference (',1))
  iv=shlex.split(os.environ.get('IVERILOG','iverilog'));vvp=shlex.split(os.environ.get('VVP','vvp'))
  subprocess.run(iv+['-g2001','-i','-tnull','-s','vga',str(candidate)],check=True,capture_output=True)
  # Parse the actual module interface, retaining every output in the comparison.
  ports=re.findall(r'\b(input|output)\s*(\[[^\]]+\])?\s*(\w+)\s*[,\n]',re.sub(r'//[^\n]*|/\*.*?\*/','',original[:original.index(');')],flags=re.S))
  inputs=[(n,w) for k,w,n in ports if k=='input'];outputs=[(n,w) for k,w,n in ports if k=='output']
  assert len(inputs)==40 and len(outputs)==17,(len(inputs),len(outputs))
  decl='\n'.join('reg '+w+' '+n+'=0;' for n,w in inputs)+'\n'
  decl+='\n'.join('wire '+w+' '+n+'0,'+n+'1;' for n,w in outputs)+'\n'
  links=lambda i:','.join('.'+n+'('+n+')' for n,w in inputs)+','+','.join('.'+n+'('+n+str(i)+')' for n,w in outputs)
  decision=root[root.index("  cmd_fskip <= 1'b0;"):root.index('   // case -> only evaluates first match')]
  update=root[root.index('           if (PoC_state_frameskip == S_Blit_Auto_First)'):root.index('           state <= PoC_state_frameskip == S_Blit_Auto_First')]
  wrapper='''module root_skip(input clk,reset,run_skip,input [15:0] vga_vcount,PoC_V,PoC_H,input PoC_interlaced,PoC_FB_interlaced,vblank_core,input [23:0] vram_queue,vram_pixels,vga_pixels,input cmd_switchres,
 output reg cmd_fskip=0,output reg [1:0] PoC_state_frameskip=0,output reg [23:0] PoC_px_frameskip=0);
 localparam S_Blit_Auto_First=0,S_Blit_Auto_End=1,S_Blit_Auto_Line=2;
 wire hps_frameskip=1,cmd_logo=0;wire [23:0] PoC_frame_vram=1;
 reg vga_frameskip=0,vga_frameskip_prev=0;
 always @(posedge clk) begin
 if(reset) begin cmd_fskip<=0;PoC_state_frameskip<=0;PoC_px_frameskip<=0;vga_frameskip<=0;vga_frameskip_prev<=0;end
 else begin
 '''+decision+'\nif(run_skip) begin\n'+update+'\nend\nend\nend\nendmodule\n'
  (temp/'root_skip.sv').write_text(wrapper)
  compare='{'+','.join(n+'0' for n,w in outputs)+'}'+' !== '+'{'+','.join(n+'1' for n,w in outputs)+'}'
  bench='`timescale 1ns/1ps\nmodule tb;\n'+decl+'vga dut('+links(0)+');\nvga_reference refdut('+links(1)+');\n'
  bench+='''reg run_skip=0;reg [23:0] queue=0,pixels=0,total=0;reg switchres=0;
 wire skip0,skip1;wire [1:0] state0,state1;wire [23:0] px0,px1;
 root_skip s0(clk_sys,vga_reset,run_skip,vcount0,V,H,interlaced,FB_interlaced,vblank0,queue,pixels,total,switchres,skip0,state0,px0);
 root_skip s1(clk_sys,vga_reset,run_skip,vcount1,V,H,interlaced,FB_interlaced,vblank1,queue,pixels,total,switchres,skip1,state1,px1);
 integer i,mode,seed=12345,hs_edges=0,fields=0,stalls=0,firsts=0,ends=0,lines=0,decisions=0;
 reg previous_hs=0,previous_field=0;
 initial begin
  H=32;HFP=2;HS=3;HBP=2;V=24;VFP=1;VS=2;VBP=3;vga_reset=1;vram_reset=1;
  for(i=0;i<180000;i=i+1) begin
   clk_sys=0;
   ce_pix=(i%7!=3);if(!ce_pix)stalls=stalls+1;
   vga_reset=(i<3 || i%30000==0);vram_reset=vga_reset;vga_frame_reset=vga_reset;
   vga_soft_reset=(i%991==990);vga_wait_vblank=(i%701==700);
   interlaced=(i/10000)%2;FB_interlaced=(i/20000)%2;
   cmd_blit_vsync=(i%379==0);vsync_skip=(i%467==0);vsync_overlay=(i/1000)%2;
   vram_active=(i/2000)%2;vram_wren1=(i%13==0);vram_wren2=(i%19==0);vram_wren3=(i%23==0);vram_wren4=(i%29==0);
   r_in=i;g_in=i>>2;b_in=i>>3;
   {r_vram_in1,g_vram_in1,b_vram_in1}=i;{r_vram_in2,g_vram_in2,b_vram_in2}=i*3;
   {r_vram_in3,g_vram_in3,b_vram_in3}=i*5;{r_vram_in4,g_vram_in4,b_vram_in4}=i*7;
   if(i%10000==0)begin
    mode=(i/10000)%6;
    case(mode)
     0:begin H=32;V=24;HFP=2;HS=3;HBP=2;VFP=1;VS=2;VBP=3;end
     1:begin H=16;V=7;VFP=0;VS=1;VBP=0;end
     2:begin H=8;V=0;VFP=0;VS=0;VBP=0;end
     3:begin H=32;V=65535;VFP=255;VS=255;VBP=255;end
     4:begin H=65535;V=1;HFP=255;HS=255;HBP=255;VFP=0;VS=0;VBP=0;end
     5:begin H=17;V=33;HFP=0;HS=1;HBP=0;VFP=255;VS=0;VBP=255;end
    endcase
   end
   // Boundary-state injections are paired; other cycles run the original counters.
   if(i%10000==4 && (mode==3 || mode==4))begin
    dut.v_cnt=65533;refdut.v_cnt=65533;dut.h_cnt=H+HFP;refdut.h_cnt=H+HFP;
   end
   queue=0;pixels=(i%2) ? 23 : (H<<2)+30;total=(H*V)+100;switchres=(i%101==0);run_skip=(i%3==0);
   #4;clk_sys=1;#1;
   if('''+compare+''')$fatal(1,"VGA output mismatch cycle %0d",i);
   if({dut.h_cnt,dut.v_cnt,dut.field,dut._hs,dut._vs,dut.hb,dut.vb} !== {refdut.h_cnt,refdut.v_cnt,refdut.field,refdut._hs,refdut._vs,refdut.hb,refdut.vb})$fatal(1,"Counter mismatch %0d",i);
   if({skip0,state0,px0} !== {skip1,state1,px1})$fatal(1,"Root frame-skip mismatch %0d",i);
   if(hsync0!=previous_hs)hs_edges=hs_edges+1;if(vga_f10!=previous_field)fields=fields+1;
   previous_hs=hsync0;previous_field=vga_f10;
   if(skip0)begin decisions=decisions+1;case(state0)0:firsts=firsts+1;1:ends=ends+1;2:lines=lines+1;endcase end
   #5;
  end
  if(hs_edges==0 || fields==0 || stalls==0 || firsts==0 || ends==0 || lines==0)$fatal(1,"Missing coverage hs=%0d field=%0d first/end/line=%0d/%0d/%0d",hs_edges,fields,firsts,ends,lines);
  $display("PASS V1 VGA 180000 clocks, HS=%0d field=%0d CE-stalls=%0d; frame-skip first/end/line=%0d/%0d/%0d",hs_edges,fields,stalls,firsts,ends,lines);
  $finish;
 end
 endmodule
'''
  tb=temp/'tb.sv';tb.write_text(bench);output=temp/'sim'
  command=iv+['-g2012','-s','tb','-o',str(output),str(tb),str(candidate),str(reference),str(ROOT/'tests/rtl_models.sv'),str(ROOT/'rtl/binary_to_bcd.v'),str(temp/'root_skip.sv')]
  subprocess.run(command,check=True,capture_output=True);subprocess.run(vvp+[str(output)],check=True)
if __name__=='__main__':run()
