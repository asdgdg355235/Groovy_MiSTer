`timescale 1ns/1ps
module tb_osd_anchor;
    reg clk=0;
    always #5 clk=~clk;
    reg io=0, strobe=0;
    reg [15:0] command=0;
    integer x=0,y=0,frames=0;
    always @(posedge clk) begin
        x<=x==399 ? 0 : x+1;
        if(x==399) begin
            y<=y==261 ? 0 : y+1;
            if(y==261) frames<=frames+1;
        end
    end
    wire de=x<320 && y<240, hs=x>=336 && x<368, vs=y>=244 && y<247;
    wire [23:0] rgb={8'(x),8'(y),8'h35};
    wire [27:0] before_video,after_video;
    reg signed [12:0] adjust=0;
    osd_reference before_osd(.clk_sys(clk),.clk_video(clk),.io_osd(io),.io_strobe(strobe),.io_din(command),
        .din(rgb),.de_in(de),.hs_in(hs),.vs_in(vs),
        .dout(before_video[23:0]),.de_out(before_video[24]),.hs_out(before_video[25]),.vs_out(before_video[26]),.osd_status(before_video[27]));
    osd after_osd(.clk_sys(clk),.clk_video(clk),.io_osd(io),.io_strobe(strobe),.io_din(command),
`ifdef GROOVY_CRT_GEOMETRY
        .vpos_adjust(adjust),
`endif
        .din(rgb),.de_in(de),.hs_in(hs),.vs_in(vs),
        .dout(after_video[23:0]),.de_out(after_video[24]),.hs_out(after_video[25]),.vs_out(after_video[26]),.osd_status(after_video[27]));
`ifdef GROOVY_CRT_GEOMETRY
    wire [23:0] enlarged_rgb, reduced_rgb;
    osd enlarged(.clk_sys(clk),.clk_video(clk),.io_osd(io),.io_strobe(strobe),.io_din(command),
        .din(rgb),.de_in(x<320 && y>=2 && y<249),.hs_in(hs),.vs_in(vs),.vpos_adjust(-13'sd5),.dout(enlarged_rgb));
    osd reduced(.clk_sys(clk),.clk_video(clk),.io_osd(io),.io_strobe(strobe),.io_din(command),
        .din(rgb),.de_in(x<320 && y>=9 && y<242),.hs_in(hs),.vs_in(vs),.vpos_adjust(-13'sd5),.dout(reduced_rgb));
    integer overlay_samples=0;
    always @(negedge clk) if(frames>=4 && adjust==0) begin
        if(enlarged_rgb!==before_video[23:0] || reduced_rgb!==before_video[23:0])
            $fatal(1,"rendered OSD shifted after vertical scaling at y=%0d x=%0d",y,x);
        if(before_video[23:0] != rgb) overlay_samples=overlay_samples+1;
    end
`endif
    always @(negedge clk) if(frames>=4 && adjust==0 && before_video!==after_video)
        $fatal(1,"OSD default behavior changed");
    integer delta,mult,a,o,top,expected,base;
    initial begin
        repeat(8) @(negedge clk);
        io=1; command=16'h41;
        repeat(2) @(negedge clk); strobe=1;
        repeat(2) @(negedge clk); strobe=0;
        repeat(2) @(negedge clk); io=0;
        wait(frames==12);
`ifdef GROOVY_CRT_GEOMETRY
        if(overlay_samples==0) $fatal(1,"no rendered OSD samples");
        for(mult=1;mult<=2;mult=mult+1) begin
            for(delta=-7;delta<=7;delta=delta+1) begin
                a=240*mult; o=(240+delta)*mult; top=(2+(delta<0?-delta:0))*mult;
                expected=a/2-o/2-top; adjust=expected; base=(o-64)/2;
                #1;
                if(after_osd.anchor_vpos(base)+top != (a-64)/2) $fatal(1,"OSD center moved");
            end
        end
        adjust=-13'sd99; #1;
        if(after_osd.anchor_vpos(22'd4)!=0) $fatal(1,"OSD position underflow");
`endif
        $display("PASS: OSD default matches integration base; optional signed anchor keeps resized/scandoubled menu centered");
        $finish;
    end
endmodule
