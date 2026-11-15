`timescale 1ns/1ps
module tb_groovy_crt;
    parameter MODE=1;
    reg clk=0;always #5 clk=~clk;
    reg reset=1,request=0,unsupported=0,ce=0;
    reg [7:0] period=8;
    reg [15:0] width=64,height=240,htotal=96,vtotal=264;
    reg signed [4:0] size=0;
    reg signed [8:0] hp=0;
    reg signed [5:0] vp=0,vsize=0;
    reg [23:0] rgb=0;
    reg hs=0,vs=0,hb=1,vb=1,de=0;
    wire selected,ce_out,ohs,ovs,ode,osd;
    wire [23:0] out;
    groovy_crt #(.HPOS_MODE(MODE),.LINE_PX(80)) dut(
        .clk(clk),.reset(reset),.request(request),.unsupported(unsupported),
        .pixel_period(period),.width(width),.height(height),.htotal(htotal),.vtotal(vtotal),
        .hsize(size),.hpos(hp),.vshift(vp),.vsize(vsize),
        .ce_in(ce),.rgb_in(rgb),.hs_in(hs),.vs_in(vs),.hb_in(hb),.vb_in(vb),.de_in(de),
        .selected(selected),.ce_out(ce_out),.rgb_out(out),.hs_out(ohs),.vs_out(ovs),.de_out(ode),.de_osd(osd));
    integer age=0,x=0,y=0,frame=0,clock_count=0;
    integer selected_clocks=0,resets=0,anchored=0,phase0=-1;
    integer seen_first=0,seen_last=0,enlarge=0,shrink=0;
    integer changed_mode=0,last_hs_clock=-1;
    reg last_hs=0;
    reg [63:0] expanded_pixels=0,shrunk_pixels=0;
    reg oldref,oldsel,oldosd=0;
    reg [7:0] oldperiod;
    always @(negedge clk) begin
        reset=0;ce=age==0;age=(age+1)%period;
        if(ce) begin
            hs=x>=width+12 && x<width+20;vs=y>=height+2 && y<height+5;
            hb=x>=width;vb=y>=height;de=!hb && !vb;
            rgb={8'(y),8'(x),8'(y^x)};
            x=x+1;if(x==htotal) begin x=0;y=y+1;end
            if(y==vtotal) begin
                y=0;frame=frame+1;
                case(frame)
                    1:request=1;
                    10:size=1;
                    12:size=-1;
                    14:hp=16;
                    16:hp=-16;
                    18:vp=-8;
                    20:begin vp=8;size=0;hp=0;end
                    22:vsize=-3;
                    26:vsize=3;
                    30:begin unsupported=1;vsize=0;end
                    31:unsupported=0;
                    38:begin width=80;height=224;htotal=112;vtotal=262;end
                    46:period=4;
                    47:period=16;
                    48:reset=1;
                    49:request=0;
                endcase
            end
        end
    end
    always @(posedge clk) begin
        oldref=dut.hs_ref_rise;oldsel=selected;oldperiod=period;
        #1;
        clock_count=clock_count+1;
        if(oldref && oldsel) begin
            if(dut.rd_acc!==0) $fatal(1,"read CE did not reset on hs_ref_out");
            resets=resets+1;
        end
        if((unsupported || period<8 || reset) && selected) $fatal(1,"unsupported selection");
        if(frame>=38 && frame<43 && selected) $fatal(1,"mode change did not flush qualification");
        if(selected) begin
            if(frame>=44 && frame<46) changed_mode=changed_mode+1;
            if(MODE==1 && ohs && !last_hs) begin
                if(last_hs_clock>=0 && (clock_count-last_hs_clock<htotal*period-32 || clock_count-last_hs_clock>htotal*period+32))
                    $fatal(1,"native HSync cadence changed");
                last_hs_clock=clock_count;
            end
            selected_clocks=selected_clocks+1;
            if(osd && !oldosd && frame>=9 && frame<18) begin
                if(phase0==-1) phase0=clock_count%(96*8);
                if(clock_count%(96*8)!=phase0) $fatal(1,"OSD anchor moved mode=%0d phase=%0d expected=%0d frame=%0d",MODE,clock_count%(96*8),phase0,frame);
                anchored=anchored+1;
            end
            if(ce_out && ode && frame>=9 && frame<10) begin
                if(out[23:16]==0) seen_first=seen_first+1;
                if(out[23:16]==239) seen_last=seen_last+1;
            end
            if(ce_out && ode && osd && frame==11 && out[23:16]==100 && out[15:8]<64)
                expanded_pixels[out[15:8]]=1;
            if(ce_out && ode && osd && frame==13 && out[23:16]==100 && out[15:8]<64)
                shrunk_pixels[out[15:8]]=1;
            if(dut.u_vsize.tube_on && vsize<0) enlarge=enlarge+1;
            if(dut.u_vsize.tube_on && vsize>0) shrink=shrink+1;
        end else last_hs_clock=-1;
        last_hs=ohs;
        oldosd=osd;
        if(frame==50) begin
            if(expanded_pixels!==64'hffffffffffffffff || shrunk_pixels!==64'hffffffffffffffff)
                $fatal(1,"source pixels clipped enlarge=%h shrink=%h",expanded_pixels,shrunk_pixels);
            if(selected_clocks==0 || resets==0 || anchored<100 || seen_first==0 || seen_last==0 || enlarge==0 || shrink==0 || changed_mode==0)
                $fatal(1,"integration coverage selected=%0d ref=%0d anchor=%0d rows=%0d/%0d cabinet=%0d/%0d",selected_clocks,resets,anchored,seen_first,seen_last,enlarge,shrink);
            $display("PASS: Groovy CRT mode=%0d, %0d clocks, hs_ref resets=%0d OSD anchors=%0d first/last=%0d/%0d; mode/reset/ratio guards",MODE,clock_count,resets,anchored,seen_first,seen_last);
            $finish;
        end
    end
endmodule
