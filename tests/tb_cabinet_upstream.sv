`timescale 1ns/1ps
module tb_cabinet_upstream;
    parameter PERIOD=8;
    parameter CAPACITY=80;
    parameter WIDTH=64;
    parameter DIFFERENTIAL=1;
    parameter END_FRAMES=114;
    parameter TOP=8;
    reg clk=0;always #5 clk=~clk;
    reg ce=0,active=0;
    reg [23:0] rgb=0;
    reg hs=0,vs=0,de=0,vb=1;
    reg signed [5:0] size=0;
    wire [29:0] got,refout;
    crt_vsize #(.LINE_PX(CAPACITY)) dut(
        .clk(clk),.pxl_cen(ce),.active(active),.tube_mode(1'b1),.vsize(size),
        .r_in(rgb[23:16]),.g_in(rgb[15:8]),.b_in(rgb[7:0]),
        .hs_in(hs),.vs_in(vs),.de_in(de),.vb_in(vb),
        .r_out(got[29:22]),.g_out(got[21:14]),.b_out(got[13:6]),
        .hs_out(got[5]),.vs_out(got[4]),.de_out(got[3]),.vb_out(got[2]),.ce_out(got[1]));
    assign got[0]=0;assign refout[0]=0;
    crt_vsize_reference #(.LINE_PX(CAPACITY)) original(
        .clk(clk),.pxl_cen(ce),.active(active),.tube_mode(1'b1),.vsize(size),
        .r_in(rgb[23:16]),.g_in(rgb[15:8]),.b_in(rgb[7:0]),
        .hs_in(hs),.vs_in(vs),.de_in(de),.vb_in(vb),
        .r_out(refout[29:22]),.g_out(refout[21:14]),.b_out(refout[13:6]),
        .hs_out(refout[5]),.vs_out(refout[4]),.de_out(refout[3]),.vb_out(refout[2]),.ce_out(refout[1]));
    integer age=0,x=0,y=0,frame=0,checks=0,n,root;
    integer pixels=0,blends=0,vsdel_seen=0,wraps=0,clamps=0;
    reg [7:0] a[0:2],b[0:2];
    integer weights[0:2],expected[0:2];
    reg [4:0] phase;
    reg [23:0] oldring;
    reg oldtube,oldce,oldhs;
    integer upstream_clamp_cycles=0;
    integer max_vsdel=0;
    reg [3:0] reference_bad_pipe=0;
    initial begin
        for(n=0;n<65536;n=n+1) begin
            root=$rtoi($sqrt(n));
            if(dut.isqrt_l(dut.isqrt_h(16'(n)))!==8'(root)) $fatal(1,"integer sqrt %0d",n);
        end
    end
    always @(negedge clk) begin
        ce=(age==0);age=(age+1)%PERIOD;
        if(ce) begin
            hs=x<8;vs=y<3;vb=y<TOP || y>=124;de=!vb && x>=16 && x<16+WIDTH;
            case(frame%4)
                0: rgb={8'(x*3+y),8'(255-x*2),8'(y*7)};
                1: rgb=(y%2) ? 24'hffffff : 0;
                2: rgb={8'(y%2 ? 255 : 0),8'(x),8'(255-y)};
                3: rgb={8'(x),8'(y),8'(x^y)};
            endcase
            x=x+1;
            if(x==WIDTH+32) begin x=0;y=y+1;end
            if(y==128) begin
                y=0;frame=frame+1;
                active=frame>=1 && frame!=113;
                case(frame)
                    1:size=-24;29:size=24;82:size=-6;
                    110:size=0;111:size=3;112:size=-3;113:size=0;
                endcase
            end
        end
    end
    always @(posedge clk) begin
        phase=dut.p_cnt;oldring=dut.ring_q;oldtube=dut.tube_on;
        oldce=ce;oldhs=dut.hs_q;
        if(ce) reference_bad_pipe={reference_bad_pipe[2:0],original.t_active && original.t_src>=original.a_nat};
        if(phase==3) begin a[0]=oldring[23:16];a[1]=oldring[15:8];a[2]=oldring[7:0];end
        if(phase==4) begin b[0]=oldring[23:16];b[1]=oldring[15:8];b[2]=oldring[7:0];end
        if(phase==5) for(integer c=0;c<3;c=c+1) begin
            weights[c]=((256-dut.t_al)*a[c]*a[c]+dut.t_al*b[c]*b[c])>>8;
            expected[c]=$rtoi($sqrt(weights[c]));
        end
        if(dut.t_vsdel>0) vsdel_seen=vsdel_seen+1;
        if(dut.t_vsdel>max_vsdel) max_vsdel=dut.t_vsdel;
        if(dut.hs_rise && dut.wl==45) wraps=wraps+1;
        if(dut.t_active && dut.t_src>=dut.a_nat-1 && dut.alpha_eff==0) clamps=clamps+1;
        #1;
        // Upstream advances beyond a_nat during some live slew transitions.
        // Controls must still match; only those invalid source RGB reads are
        // excluded from byte equivalence & checked by the absolute clamp test.
        if(DIFFERENTIAL && got[5:0]!==refout[5:0]) $fatal(1,"Cabinet timing mismatch frame=%0d",frame);
        if(DIFFERENTIAL && got[29:6]!==refout[29:6]) begin
            if(!reference_bad_pipe && !(original.t_active && original.t_src>=original.a_nat))
                $fatal(1,"Cabinet upstream RGB mismatch frame=%0d src=%0d/%0d",frame,dut.t_src,original.t_src);
            upstream_clamp_cycles=upstream_clamp_cycles+1;
        end
        if(phase==7 && dut.t_out_v) begin
            if(dut.t_out!=={8'(expected[0]),8'(expected[1]),8'(expected[2])})
                $fatal(1,"photometric blend got=%h expected=%h/%h/%h",dut.t_out,expected[0],expected[1],expected[2]);
            blends=blends+1;
        end
        if(oldtube && oldce && got[5]!==oldhs) $fatal(1,"Cabinet HSync cadence");
        if(dut.t_vsdel>24) $fatal(1,"VSync delay bounds");
        if(dut.t_active && dut.t_src>=dut.a_nat) $fatal(1,"source line clamp frame=%0d src=%0d active=%0d",frame,dut.t_src,dut.a_nat);
        if(dut.rd_addr_m>=46*CAPACITY) $fatal(1,"ring read wrap");
        if(dut.tube_on && got[3]) pixels=pixels+1;
        if(!DIFFERENTIAL && frame>5 && dut.px_count_nat!=WIDTH)
            $fatal(1,"full-width line count got=%0d expected=%0d",dut.px_count_nat,WIDTH);
        checks=checks+1;
        if(frame==END_FRAMES) begin
            if(DIFFERENTIAL && (blends<100 || vsdel_seen==0 || wraps==0 || clamps==0)) $fatal(1,"Cabinet coverage %0d %0d %0d %0d",blends,vsdel_seen,wraps,clamps);
            if(TOP==32 && max_vsdel!=24) $fatal(1,"full VSync-delay range not exercised");
            $display("PASS: Cabinet period=%0d width=%0d capacity=%0d, %0d clocks, %0d photometric pixels, max VSync delay=%0d/ring wrap/clamp; corrected upstream RGB cycles=%0d",PERIOD,WIDTH,CAPACITY,checks,blends,max_vsdel,upstream_clamp_cycles);
            $finish;
        end
    end
endmodule
