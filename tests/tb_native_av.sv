`timescale 1ns/1ps
module tb_native_av;
    reg clk=0;always #5 clk=~clk;
    reg audio_clk=0;always #7 audio_clk=~audio_clk;
    reg reset=1,ce=0,interlaced=0;
    wire hs,vs,hb,vb,field;
    wire [15:0] vcount;
    vga video(.clk_sys(clk),.ce_pix(ce),.vga_reset(reset),.vga_frame_reset(1'b0),
        .vga_soft_reset(1'b0),.vga_wait_vblank(1'b0),
        .H(16'd64),.HFP(8'd4),.HS(8'd8),.HBP(8'd20),
        .V(interlaced?16'd480:16'd240),.VFP(8'd2),.VS(8'd3),.VBP(interlaced?8'd40:8'd19),
        .interlaced(interlaced),.FB_interlaced(interlaced),
        .vram_active(1'b0),.vram_reset(reset),
        .vram_wren1(1'b0),.vram_wren2(1'b0),.vram_wren3(1'b0),.vram_wren4(1'b0),
        .r_vram_in1(8'd0),.g_vram_in1(8'd0),.b_vram_in1(8'd0),
        .r_vram_in2(8'd0),.g_vram_in2(8'd0),.b_vram_in2(8'd0),
        .r_vram_in3(8'd0),.g_vram_in3(8'd0),.b_vram_in3(8'd0),
        .r_vram_in4(8'd0),.g_vram_in4(8'd0),.b_vram_in4(8'd0),
        .r_in(8'h12),.g_in(8'h34),.b_in(8'h56),
        .cmd_blit_vsync(1'b0),.vsync_skip(1'b0),.vsync_overlay(1'b0),
        .hsync(hs),.vsync(vs),.hblank(hb),.vblank(vb),.vga_f1(field),.vcount(vcount));
    integer age=0,changes=0,frames=0,hs_count=0,last_field_hs=0;
    integer half_edges=0,whole_edges=0;
    reg oldhs=0,oldvs=0,oldfield=0;
    reg video_done=0;
    always @(negedge clk) begin ce=age==0;age=(age+1)%4;end
    always @(posedge clk) begin
        #1;
        if(!reset) begin
            if(hs&&!oldhs) hs_count=hs_count+1;
            if(vs&&!oldvs) begin
                frames=frames+1;
                if(interlaced) begin
                    if(video.h_cnt==35) half_edges=half_edges+1;
                    else if(video.h_cnt==69) whole_edges=whole_edges+1;
                    else $fatal(1,"interlace VSync phase %0d",video.h_cnt);
                end
            end
            if(field!=oldfield && interlaced) begin
                changes=changes+1;
                if(changes>2 && hs_count-last_field_hs!=262 && hs_count-last_field_hs!=263)
                    $fatal(1,"interlace field cadence %0d",hs_count-last_field_hs);
                last_field_hs=hs_count;
            end
        end
        oldhs=hs;oldvs=vs;oldfield=field;
    end

    reg sound_reset=1,wren=0;
    reg [1:0] rate=3,channels=2;
    reg [15:0] vc=240,s1=0,s2=0,s3=0,s4=0;
    wire [15:0] left,right;
    wire [15:0] refleft,refright;
    sound audio(.clk_sys(clk),.clk_audio(audio_clk),.vga_frame(32'd1),.vga_vcount(vc),.vga_interlaced(8'd0),
        .sound_reset(sound_reset),.sound_synced(1'b0),.sound_enabled(1'b1),
        .sound_rate(rate),.sound_chan(channels),.sound_buffer(2'd0),
        .sound_wren1(wren),.sound_wren2(wren),.sound_wren3(wren),.sound_wren4(wren),
        .sound_in1(s1),.sound_in2(s2),.sound_in3(s3),.sound_in4(s4),
        .sound_l_out(left),.sound_r_out(right));
    sound_reference baseline_audio(.clk_sys(clk),.clk_audio(audio_clk),.vga_frame(32'd1),.vga_vcount(vc),.vga_interlaced(8'd0),
        .sound_reset(sound_reset),.sound_synced(1'b0),.sound_enabled(1'b1),
        .sound_rate(rate),.sound_chan(channels),.sound_buffer(2'd0),
        .sound_wren1(wren),.sound_wren2(wren),.sound_wren3(wren),.sound_wren4(wren),
        .sound_in1(s1),.sound_in2(s2),.sound_in3(s3),.sound_in4(s4),
        .sound_l_out(refleft),.sound_r_out(refright));
    always @(negedge audio_clk) if({left,right}!=={refleft,refright})
        $fatal(1,"audio differs from analog-triggers baseline");
    integer j,received,timeout;
    reg [15:0] last_left;
    task audio_case(input integer r,ch);
        begin
            rate=r;channels=ch;sound_reset=1;vc=240;wren=0;
            repeat(4) @(negedge clk);
            sound_reset=0;
            for(j=0;j<8;j=j+1) begin
                if(ch==2) begin s1=1000+j*2;s2=2000+j*2;s3=1001+j*2;s4=2001+j*2;end
                else begin s1=1000+j*4;s2=1001+j*4;s3=1002+j*4;s4=1003+j*4;end
                wren=1;@(negedge clk);wren=0;repeat(3) @(negedge clk);
            end
            vc=0;received=0;timeout=0;last_left=(^left===1'bx)?16'd0:left;
            while(received<(ch==2?16:32) && timeout<60000) begin
                @(negedge audio_clk);timeout=timeout+1;
                if(left>=1000 && left!=last_left) begin
                    // Exact ordering is compared against the frozen native
                    // implementation above, including its FIFO startup phase.
                    if((ch==1 && right!==left) || (ch==2 && right-left!=1000))
                        $fatal(1,"audio channels rate=%0d chan=%0d got=%0d/%0d",r,ch,left,right);
                    last_left=left;received=received+1;
                end
            end
            if(received!=(ch==2?16:32)) $fatal(1,"audio timeout rate=%0d ch=%0d received=%0d last=%0d",r,ch,received,left);
            $display("PASS: native audio rate selector=%0d channels=%0d, %0d samples",r,ch,received);
        end
    endtask
    initial begin
        repeat(4) @(negedge clk);reset=0;
        wait(frames==3);
        reset=1;interlaced=1;repeat(4) @(negedge clk);reset=0;
        changes=0;frames=0;hs_count=0;last_field_hs=0;
        wait(changes==8);
        if(half_edges<2 || whole_edges<2) $fatal(1,"both interlace phases not observed");
        $display("PASS: native 240p/480i, eight field changes, alternating half-line VSync phases");
        video_done=1;
    end
    initial begin
        repeat(8) @(negedge clk);
        for(integer r=1;r<=3;r=r+1) for(integer ch=1;ch<=2;ch=ch+1) audio_case(r,ch);
        wait(video_done);$finish;
    end
    initial begin #200000000;$fatal(1,"native A/V watchdog");end
endmodule
