`timescale 1ns/1ps
module tb_hsize;
    reg clk=0;
    always #5 clk=~clk;
    integer phase=0,x=0,y=0;
    wire ce=phase==0, ce2=phase==3;
    always @(posedge clk) begin
        phase<=phase==7 ? 0 : phase+1;
        if(ce) begin
            x<=x==332 ? 0 : x+1;
            if(x==332) y<=y==261 ? 0 : y+1;
        end
    end
    reg enable=0;
    reg [3:0] scale=0;
    wire hs=x>=266 && x<290, vs=y>=242 && y<245;
    wire hb=x>=256, vb=y>=240;
    wire [27:0] original,widened;
    jtframe_hsize_reference #(.COLORW(8)) a (
        .clk(clk),.pxl_cen(ce),.pxl2_cen(ce2),.scale(scale),.offset(5'd0),.enable(enable),
        .r_in(8'(x)),.g_in(8'(y)),.b_in(8'h59),.HS_in(hs),.VS_in(vs),.HB_in(hb),.VB_in(vb),
        .HS_out(original[27]),.VS_out(original[26]),.HB_out(original[25]),.VB_out(original[24]),
        .r_out(original[23:16]),.g_out(original[15:8]),.b_out(original[7:0]));
    jtframe_hsize #(.COLORW(8),.VW(12)) b (
        .clk(clk),.pxl_cen(ce),.pxl2_cen(ce2),.scale(scale),.offset(5'd0),.enable(enable),
        .r_in(8'(x)),.g_in(8'(y)),.b_in(8'h59),.HS_in(hs),.VS_in(vs),.HB_in(hb),.VB_in(vb),
        .HS_out(widened[27]),.VS_out(widened[26]),.HB_out(widened[25]),.VB_out(widened[24]),
        .r_out(widened[23:16]),.g_out(widened[15:8]),.b_out(widened[7:0]));
    integer i,n;
    initial begin
        repeat(8*333*6) @(negedge clk);
        for(i=0;i<17;i=i+1) begin
            enable=i!=0; scale=i==0 ? 0 : i-1;
            repeat(8*333*6) @(negedge clk);
            for(n=0;n<8*333*4;n=n+1) begin
                @(negedge clk);
                if(widened!==original || ^widened===1'bx) $fatal(1,"H-size regression enable=%0d scale=%0d",enable,scale);
            end
        end
        $display("PASS: widened JTFRAME buffer matches integration-base output, bypass and all H-size steps");
        $finish;
    end
endmodule
