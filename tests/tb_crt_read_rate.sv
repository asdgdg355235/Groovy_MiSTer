`timescale 1ns/1ps
module tb_crt_read_rate;
    parameter MODE=1;
    reg clk=0;always #5 clk=~clk;
    reg [7:0] period=8;
    reg signed [4:0] size=0;
    reg signed [8:0] hp=0;
    reg ce=0,hs=0;
    wire selected;
    groovy_crt #(.HPOS_MODE(MODE),.LINE_PX(80)) dut(
        .clk(clk),.reset(1'b0),.request(1'b1),.unsupported(1'b0),
        .pixel_period(period),.width(16'd64),.height(16'd240),.htotal(16'd96),.vtotal(16'd264),
        .hsize(size),.hpos(hp),.vshift(6'sd0),.vsize(6'sd0),
        .ce_in(ce),.rgb_in(24'd0),.hs_in(hs),.vs_in(1'b0),
        .hb_in(1'b0),.vb_in(1'b0),.de_in(1'b1),.selected(selected));
    integer age=0,x=0,clocks=0,last_tick=-1,settle=0,checks=0,refs=0;
    integer expected_quarters;
    reg reference_edge,tick;
    always @(negedge clk) begin
        ce=age==0;age=(age+1)%period;
        if(ce) begin hs=x>=68 && x<76;x=(x+1)%96;end
    end
    always @(posedge clk) begin
        reference_edge=dut.hs_ref_rise;tick=dut.rd_ce;
        clocks=clocks+1;
        if(reference_edge || !selected) begin last_tick=-1;settle=3;end
        else if(tick) begin
            if(settle>0) settle=settle-1;
            else if(last_tick>=0) begin
                expected_quarters=4*int'(period)+int'(size);
                if(clocks-last_tick<expected_quarters/4 || clocks-last_tick>(expected_quarters+3)/4)
                    $fatal(1,"quarter-cycle CE spacing p=%0d size=%0d interval=%0d",period,size,clocks-last_tick);
                checks=checks+1;
            end
            last_tick=clocks;
        end
        #1;
        if(reference_edge && selected) begin
            if(dut.rd_acc!==0) $fatal(1,"read phase not reset on hs_ref_out");
            refs=refs+1;
        end
    end
    initial begin
        // Isolate read-rate scheduling from the separately tested six-frame
        // qualification state. Both real HS-reference modes remain live.
        force dut.ready=1;force dut.ce_good=1;
        for(integer p=8;p<=16;p=p+1) begin
            period=p;
            for(integer s=-8;s<=8;s=s+8) begin
                @(negedge hs);@(negedge clk);size=s;hp=s*2;
                last_tick=-1;settle=3;
                repeat(96*p*3) @(negedge clk);
            end
        end
        if(checks<1000 || refs<30) $fatal(1,"read-rate coverage");
        $display("PASS: read-rate mode=%0d, all integer ratios 8..16, %0d intervals & %0d hs_ref resets",MODE,checks,refs);
        $finish;
    end
endmodule
