`timescale 1ns/1ps
module tb_crt_adjust_upstream;
    parameter MODE=1;
    reg clk=0; always #5 clk=~clk;
    reg ce=0, ce2=0, active=0;
    reg [23:0] rgb=0;
    reg hs=0,vs=0,hb=1,vb=1;
    reg signed [4:0] size=0;
    reg signed [8:0] hp=0;
    reg signed [5:0] vp=0;
    wire [28:0] got,refout;
    wire href,refhref;
    crt_adjust #(.HTOTAL(96),.VTOTAL(128),.HPOS_MODE(MODE)) dut(
        .clk(clk),.pxl_cen(ce),.pxl2_cen(ce2),.active(active),
        .htotal(16'd96),.vtotal(16'd128),.hsize(size),.hoffset(hp),.voffset(vp),
        .r_in(rgb[23:16]),.g_in(rgb[15:8]),.b_in(rgb[7:0]),
        .hs_in(hs),.vs_in(vs),.hb_in(hb),.vb_in(vb),
        .r_out(got[28:21]),.g_out(got[20:13]),.b_out(got[12:5]),
        .hs_out(got[4]),.vs_out(got[3]),.hb_out(got[2]),.vb_out(got[1]),.hs_ref_out(href));
    crt_adjust_reference #(.HTOTAL(96),.VTOTAL(128),.HPOS_MODE(MODE)) original(
        .clk(clk),.pxl_cen(ce),.pxl2_cen(ce2),.active(active),
        .hsize(size),.hoffset(hp),.voffset(vp),
        .r_in(rgb[23:16]),.g_in(rgb[15:8]),.b_in(rgb[7:0]),
        .hs_in(hs),.vs_in(vs),.hb_in(hb),.vb_in(vb),
        .r_out(refout[28:21]),.g_out(refout[20:13]),.b_out(refout[12:5]),
        .hs_out(refout[4]),.vs_out(refout[3]),.hb_out(refout[2]),.vb_out(refout[1]),.hs_ref_out(refhref));
    assign got[0]=0; assign refout[0]=0;
    integer age=0,x=0,y=0,acc=0,frame=0,checks=0;
    reg hd=0;
    reg oldvb,oldread;
    reg [2:0] vb_difference=0;
    always @(negedge clk) begin
        ce=(age==0); age=(age+1)%8;
        if(ce) begin
            hs=x<8; vs=y<3; hb=x<16 || x>=80; vb=y<8 || y>=120;
            rgb={8'(x),8'(y),8'(x^y)};
            x=x+1;
            if(x==96) begin x=0;y=y+1;end
            if(y==128) begin
                y=0;frame=frame+1;
                active=(frame!=1 && frame!=19);
                case(frame)
                    2: size=6; 4: size=-6; 6: hp=16; 8: hp=-16;
                    10: vp=7; 12: vp=-7; 14: begin hp=0;vp=0;size=0;end
                    16: size=15; 18:size=-16;
                endcase
            end
        end
        if(href && !hd) acc=0;
        else if(acc+4>=32+size) acc=acc+4-(32+size);
        else acc=acc+4;
        hd=href; ce2=(acc+4>=32+size);
    end
    always @(posedge clk) begin
        oldvb=dut.vb_active;oldread=ce2;
        if(ce2) vb_difference={vb_difference[1:0],dut.vb_active!=original.vb_active};
        #1;
        if({got[4:3],got[1:0],href} !== {refout[4:3],refout[1:0],refhref}) $fatal(1,"upstream CRT sync mismatch mode=%0d frame=%0d",MODE,frame);
        if(got[2]!==refout[2] && !vb_difference && dut.vb_active==original.vb_active)
            $fatal(1,"CRT DE differs outside corrected VB boundary");
        if(got[2]===refout[2] && got[28:5]!==refout[28:5]) $fatal(1,"upstream CRT RGB mismatch");
        if(active && oldread && oldvb && dut.pass_q) $fatal(1,"true VB gate");
        checks=checks+1;
        if(frame==20) begin
            $display("PASS: CRT upstream differential HPOS_MODE=%0d, %0d clocks, size/position/shift/bypass",MODE,checks);
            $finish;
        end
    end
endmodule
