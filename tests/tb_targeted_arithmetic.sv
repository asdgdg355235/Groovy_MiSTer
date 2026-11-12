`timescale 1ns/1ps
module tb_targeted_arithmetic;
reg [31:0] p=0,s=0;
reg [15:0] v=0,count=0;reg [7:0] bp=0,fp=0,vs=0;reg parity=0;
crt_vsize_fixed #(.LINE_PX(2560),.MLAB_PARTS(2)) row(.clk(1'b0));
vga video(.clk_sys(1'b0),.V(v),.VBP(bp),.VFP(fp),.VS(vs),.interlaced(1'b1));
reg [31:0] next_p;reg [16:0] expected_delta;reg [15:0] expected_total;
reg [31:0] rng=32'h612081;integer n,slot,word;
function [31:0] random_word;begin rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);random_word=rng;end endfunction
initial begin
 for(n=0;n<100000;n=n+1) begin
  p=random_word();s=random_word();v=random_word();bp=random_word();fp=random_word();vs=random_word();parity=n%2;count=random_word();
  case(n)
   0:begin p=32'hffffffff;s=1;end
   1:begin p=32'hffff0000;s=32'h10000;end
   2:begin p=32'hffff0001;s=32'hffffffff;end
   3:begin p=0;s=32'hffffffff;end
  endcase
  if(n<8) begin v=n%2?16'hffff:0;bp=0;fp=0;vs=0;count=n%2?16'hffff:0;end
  row.position=p;row.step=s;video.field=parity;video.v_cnt=count;
  next_p=p+s;expected_delta={1'b0,next_p[31:16]}-{1'b0,p[31:16]};
  expected_total=parity?v+bp+fp+vs-1'b1:v+bp+fp+vs;
  #1;
  if(row.advance_rows!==expected_delta || row.position_next!==next_p) $fatal(1,"row boundary %d",n);
  if(video.V_total!==expected_total || video.v_at_end!==(count>=expected_total-1)) $fatal(1,"VGA arithmetic %d",n);
 end
 for(slot=0;slot<16;slot=slot+1) for(word=0;word<512;word=word+1)
  if(row.read_address_word(4'(slot),12'(word))!==12'((slot>>1)*512+word)) $fatal(1,"read fields");
 $display("PASS: actual RTL 100000 arithmetic/boundary vectors and 8192 read-field cases");$finish;
end
endmodule
