`timescale 1ns/1ps
module tb_video_pipeline;
    parameter ENABLED=0;
    reg clk=0;always #5 clk=~clk;
    reg ce=0,ce2=0,reset=0,interlaced=0;
    reg [127:0] status=0;
    reg [23:0] rgb=0;
    reg hs=0,vs=0,hb=1,vb=1;
    wire [55:0] got,expected;
    original_pipeline original(.clk_sys(clk),.ce_pix(ce),.ce_pix2(ce2),.RESET(reset),
        .status(status),.PoC_interlaced(interlaced),.PoC_FB_interlaced(1'b0),
        .r_core(rgb[23:16]),.g_core(rgb[15:8]),.b_core(rgb[7:0]),
        .hsync_core(hs),.vsync_core(vs),.hblank_core(hb),.vblank_core(vb),
        .VGA_R(expected[55:48]),.VGA_G(expected[47:40]),.VGA_B(expected[39:32]),
        .VGA_HS(expected[31]),.VGA_VS(expected[30]),.VGA_DE(expected[29]),.CE_PIXEL(expected[28]),
        .VIDEO_ARX(expected[25:13]),.VIDEO_ARY(expected[12:0]));
    changed_pipeline changed(.clk_sys(clk),.ce_pix(ce),.ce_pix2(ce2),.RESET(reset),
        .status(status),.PoC_interlaced(interlaced),.PoC_FB_interlaced(1'b0),
        .r_core(rgb[23:16]),.g_core(rgb[15:8]),.b_core(rgb[7:0]),
        .hsync_core(hs),.vsync_core(vs),.hblank_core(hb),.vblank_core(vb),
        .VGA_R(got[55:48]),.VGA_G(got[47:40]),.VGA_B(got[39:32]),
        .VGA_HS(got[31]),.VGA_VS(got[30]),.VGA_DE(got[29]),.CE_PIXEL(got[28]),
        .VIDEO_ARX(got[25:13]),.VIDEO_ARY(got[12:0]));
    assign got[27:26]=0;assign expected[27:26]=0;
    integer age=0,x=0,y=0,frame=0,checks=0,active_pixels=0,enabled_checks=0;
    always @(negedge clk) begin
        ce=age==0;ce2=age==3;age=(age+1)%8;
        if(ce) begin
            hs=x>=68 && x<76;vs=y>=242 && y<245;hb=x>=64;vb=y>=240;
            rgb={8'(x),8'(y),8'(x^y)};
            x=x+1;if(x==96) begin x=0;y=y+1;end
            if(y==264) begin
                y=0;frame=frame+1;
                case(frame)
                    6:status[21:17]=3;
                    7:status[26:22]=29;
                    8:begin interlaced=1;status[60]=1;end
                    10:begin status[47]=1;status[51:48]=2;end
                    12:begin status[21:17]=30;status[26:22]=2;end
                    14:begin interlaced=0;status[60]=0;end
                    16:if(ENABLED) begin status[60]=1;status[47]=0;status[21:17]=0;status[26:22]=0;end
                    25:if(ENABLED) status[64:61]=1;
                endcase
            end
        end
    end
    always @(posedge clk) begin
        #1;
        if(frame>=5 && frame<16) begin
            if(got!==expected) $fatal(1,"bypass changed frame=%0d got=%h expected=%h",frame,got,expected);
            if(^got===1'bx) $fatal(1,"bypass comparison contains unknown output");
            checks=checks+1;
            if(got[28] && got[29]) active_pixels=active_pixels+1;
`ifdef GROOVY_CRT_CABINET
            if(changed.crt_selected) $fatal(1,"Cabinet selected during disabled/unsupported bypass");
`endif
        end
`ifdef GROOVY_CRT_CABINET
        if(ENABLED && changed.crt_selected) begin
            if(changed.mixer_ce && changed.VGA_DE_MIXER!==!(changed.mixer_hblank || changed.mixer_vblank))
                $fatal(1,"true-blank sideband differs from the actual native mixer output");
            enabled_checks=enabled_checks+1;
        end
`endif
        if(frame==(ENABLED?28:16)) begin
            if(active_pixels==0) $fatal(1,"no video through mixer/freak");
            if(ENABLED && enabled_checks<1000) $fatal(1,"enabled pipeline not exercised");
            $display("PASS: actual emu video bypass %0d clocks, %0d active pixels, original H/V/scale controls & unsupported interlace",checks,active_pixels);
            if(ENABLED) $display("PASS: actual enabled emu mixer/CRT/freak pipeline, %0d true-blank alignment checks",enabled_checks);
            $finish;
        end
    end
endmodule
