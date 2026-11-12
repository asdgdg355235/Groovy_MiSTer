`timescale 1ns/1ps
module tb_video_geometry;
    reg clk=0;
    always #5 clk=~clk;
    reg reset=1, interlace=0;
    integer ratio=8, phase=0;
    wire ce=phase==0;
    always @(posedge clk) phase<=phase==ratio-1 ? 0 : phase+1;
    reg [15:0] width=16, height=240;
    reg signed [5:0] size=0;
    wire hs,vs,hb,vb,field;
    wire [7:0] r,g,b;
    wire [15:0] vcount;
    vga native_video (
        .clk_sys(clk),.ce_pix(ce),.vga_reset(reset),.vga_frame_reset(reset),
        .vga_soft_reset(1'b0),.vga_wait_vblank(1'b0),
        .H(width),.HFP(8'd8),.HS(8'd8),.HBP(8'd16),
        .V(height),.VFP(8'd4),.VS(8'd6),.VBP(8'd34),
        .interlaced(interlace),.FB_interlaced(interlace),
        .vram_active(1'b0),.vram_reset(reset),
        .vram_wren1(1'b0),.vram_wren2(1'b0),.vram_wren3(1'b0),.vram_wren4(1'b0),
        .r_vram_in1(8'd0),.g_vram_in1(8'd0),.b_vram_in1(8'd0),
        .r_vram_in2(8'd0),.g_vram_in2(8'd0),.b_vram_in2(8'd0),
        .r_vram_in3(8'd0),.g_vram_in3(8'd0),.b_vram_in3(8'd0),
        .r_vram_in4(8'd0),.g_vram_in4(8'd0),.b_vram_in4(8'd0),
        .r_in(vcount[7:0]),.g_in(8'h81),.b_in(8'h35),
        .cmd_blit_vsync(1'b0),.vsync_skip(1'b0),.vsync_overlay(1'b0),
        .hsync(hs),.vsync(vs),.hblank(hb),.vblank(vb),.vga_f1(field),
        .r(r),.g(g),.b(b),.vcount(vcount));
`ifdef TIMING_REFERENCE
    wire ref_hs,ref_vs,ref_hb,ref_vb,ref_field;
    wire [7:0] ref_r,ref_g,ref_b;
    wire [15:0] ref_vcount;
    vga_reference reference_video (
        .clk_sys(clk),.ce_pix(ce),.vga_reset(reset),.vga_frame_reset(reset),
        .vga_soft_reset(1'b0),.vga_wait_vblank(1'b0),
        .H(width),.HFP(8'd8),.HS(8'd8),.HBP(8'd16),
        .V(height),.VFP(8'd4),.VS(8'd6),.VBP(8'd34),
        .interlaced(interlace),.FB_interlaced(interlace),
        .vram_active(1'b0),.vram_reset(reset),
        .vram_wren1(1'b0),.vram_wren2(1'b0),.vram_wren3(1'b0),.vram_wren4(1'b0),
        .r_vram_in1(8'd0),.g_vram_in1(8'd0),.b_vram_in1(8'd0),
        .r_vram_in2(8'd0),.g_vram_in2(8'd0),.b_vram_in2(8'd0),
        .r_vram_in3(8'd0),.g_vram_in3(8'd0),.b_vram_in3(8'd0),
        .r_vram_in4(8'd0),.g_vram_in4(8'd0),.b_vram_in4(8'd0),
        .r_in(ref_vcount[7:0]),.g_in(8'h81),.b_in(8'h35),
        .cmd_blit_vsync(1'b0),.vsync_skip(1'b0),.vsync_overlay(1'b0),
        .hsync(ref_hs),.vsync(ref_vs),.hblank(ref_hb),.vblank(ref_vb),.vga_f1(ref_field),
        .r(ref_r),.g(ref_g),.b(ref_b),.vcount(ref_vcount));
    always @(posedge clk) begin
        #2;
        if ({hs,vs,hb,vb,field,r,g,b,vcount,native_video.h_cnt,native_video.vga_frame}
            !== {ref_hs,ref_vs,ref_hb,ref_vb,ref_field,ref_r,ref_g,ref_b,ref_vcount,reference_video.h_cnt,reference_video.vga_frame})
            $fatal(1,"video timing/reference mismatch");
    end
`endif
    wire [23:0] color;
    wire co,c2o,ho,vo,hbo,vbo,fo,running,underrun;
    wire [15:0] pic_height;
    // Match Groovy.sv's upcoming-field height decode at native VSync.
    wire [15:0] fh=interlace ? (height+{15'd0,field})>>1 : height;
    crt_vsize_fixed #(.LINE_PX(32)) scaler (
        .clk(clk),.reset(reset),.ce_in(ce),.ce2_in(ce),.size(size),.width(width),.height(fh),
        .rgb_in({r,g,b}),.hs_in(hs),.vs_in(vs),.hb_in(hb),.vb_in(vb),.field_in(field),
        .rgb_out(color),.ce_out(co),.ce2_out(c2o),.hs_out(ho),.vs_out(vo),.hb_out(hbo),.vb_out(vbo),
        .field_out(fo),.picture_height(pic_height),.running(running),.underrun(underrun));
    reg [4:0] timing[0:4];
    reg checking=0;
    integer i,fields=0,phase0=-1,phase1=-1,pixels=0;
    reg old_vs=0;
    always @(posedge clk) begin
        old_vs<=vs;
        if(reset) begin fields=0; phase0=-1; phase1=-1; pixels=0; end
        else if(vs && !old_vs) begin
            fields=fields+1;
            if(field) phase1=native_video.h_cnt; else phase0=native_video.h_cnt;
        end
        for(i=4;i>0;i=i-1) timing[i]=timing[i-1];
        timing[0]={ce,hs,vs,hb,field};
        #1;
        if(checking && !reset) begin
            if(!running) begin
                if({co,ho,vo,hbo,vbo,fo,color} !== {ce,hs,vs,hb,vb,field,r,g,b}) $fatal(1,"native bypass changed");
            end else begin
                if({co,ho,vo,hbo,fo} !== timing[4]) $fatal(1,"native timing changed");
                if(underrun) $fatal(1,"native vga field row unavailable: field=%d count=%d source=%d",field,vcount,scaler.src_now);
                if(co && !hbo && !vbo) pixels=pixels+1;
            end
        end
    end
    task mode(input integer il, sz, div, h);
        begin
            checking=0;
            @(negedge clk); reset=1; interlace=il; size=sz; ratio=div; height=h;
            repeat(20) @(negedge clk);
            reset=0;
            wait(fields==2); checking=1;
            wait(fields==8); checking=0;
            if(sz!=0 && pixels==0) $fatal(1,"no resized pixels");
            if(il && (phase0<0 || phase1<0 || phase0==phase1)) $fatal(1,"no alternating half-line sync phases=%0d/%0d field=%0d",phase0,phase1,field);
            $display("PASS: actual Groovy vga: interlace=%0d size=%0d ratio=%0d height=%0d VS phases=%0d/%0d",il,sz,div,h,phase0,phase1);
        end
    endtask
    initial begin
        mode(0,0,8,240);
        mode(0,7,8,240);
        mode(0,-7,12,288);
        mode(1,0,4,480);
        mode(1,7,4,480);
        mode(1,-7,6,480);
        mode(1,3,8,481);
        $display("PASS: original timing generator, runtime modes, reset and half-line fields");
        $finish;
    end
    initial begin #1000000000; $fatal(1,"timeout"); end
endmodule
