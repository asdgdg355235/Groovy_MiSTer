`timescale 1ns/1ps
// Compare the candidate RTL against the exact pre-counter scaler revision.
// The runner extracts the reference from committed parent 9c27398 unchanged.
module tb_crt_group_address;
    parameter integer MLAB_PARTS = 2;
    reg clk = 0;
    always #5 clk = ~clk;

    reg reset = 1;
    reg ce_in = 0, ce2_in = 0;
    reg signed [5:0] size = 3;
    reg [15:0] width = 2560, height = 240;
    reg [23:0] rgb_in = 0;
    reg hs_in = 0, vs_in = 0, hb_in = 1, vb_in = 1, field_in = 0;
    wire [23:0] rgb_new, rgb_old;
    wire ce_new, ce2_new, hs_new, vs_new, hb_new, vb_new, field_new;
    wire ce_old, ce2_old, hs_old, vs_old, hb_old, vb_old, field_old;
    wire [15:0] height_new, height_old;
    wire [5:0] top_new, top_old;
    wire running_new, running_old, underrun_new, underrun_old;

    crt_vsize_fixed #(.MLAB_PARTS(MLAB_PARTS)) dut (
        .clk(clk), .reset(reset), .ce_in(ce_in), .ce2_in(ce2_in),
        .size(size), .width(width), .height(height), .rgb_in(rgb_in),
        .hs_in(hs_in), .vs_in(vs_in), .hb_in(hb_in), .vb_in(vb_in),
        .field_in(field_in), .rgb_out(rgb_new),
        .ce_out(ce_new), .ce2_out(ce2_new), .hs_out(hs_new), .vs_out(vs_new),
        .hb_out(hb_new), .vb_out(vb_new), .field_out(field_new),
        .picture_height(height_new), .picture_top(top_new),
        .running(running_new), .underrun(underrun_new)
    );
    crt_vsize_fixed_reference #(.MLAB_PARTS(MLAB_PARTS)) baseline (
        .clk(clk), .reset(reset), .ce_in(ce_in), .ce2_in(ce2_in),
        .size(size), .width(width), .height(height), .rgb_in(rgb_in),
        .hs_in(hs_in), .vs_in(vs_in), .hb_in(hb_in), .vb_in(vb_in),
        .field_in(field_in), .rgb_out(rgb_old),
        .ce_out(ce_old), .ce2_out(ce2_old), .hs_out(hs_old), .vs_out(vs_old),
        .hb_out(hb_old), .vb_out(vb_old), .field_out(field_old),
        .picture_height(height_old), .picture_top(top_old),
        .running(running_old), .underrun(underrun_old)
    );

    integer cycle;
    task automatic compare(input integer n);
    begin
        if (dut.wcol !== baseline.wcol ||
            dut.group_col !== dut.wcol/5 ||
            dut.pixel_lane !== dut.wcol%5)
            $fatal(1,"column counter mismatch at cycle %0d",n);
        if (dut.wa !== baseline.wa || dut.ra_even !== baseline.ra_even ||
            dut.ra_odd !== baseline.ra_odd ||
            dut.write_lane !== baseline.write_lane ||
            dut.write_even !== baseline.write_even ||
            dut.write_odd !== baseline.write_odd ||
            dut.flush_group !== baseline.flush_group ||
            dut.write_pixel !== baseline.write_pixel)
            $fatal(1,"address/write mismatch at cycle %0d col=%0d wa=%0d/%0d",
                   n,dut.col_now,dut.wa,baseline.wa);
        if (dut.pack_next !== baseline.pack_next || dut.pack_q !== baseline.pack_q)
            $fatal(1,"packed RGB mismatch at cycle %0d",n);
        if (dut.qe !== baseline.qe || dut.qo !== baseline.qo ||
            dut.read_lane !== baseline.read_lane)
            $fatal(1,"RAM read/latency mismatch at cycle %0d",n);
        if ({rgb_new,ce_new,ce2_new,hs_new,vs_new,hb_new,vb_new,field_new,
             height_new,top_new,running_new,underrun_new} !==
            {rgb_old,ce_old,ce2_old,hs_old,vs_old,hb_old,vb_old,field_old,
             height_old,top_old,running_old,underrun_old})
            $fatal(1,"video/control mismatch at cycle %0d",n);
    end
    endtask

    integer t, col, current_width, seed;
    initial begin
        seed = 32'h71452310;
        current_width = 2560;
        col = 0;
        for (cycle=0; cycle<57000; cycle=cycle+1) begin
            @(negedge clk);
            // CE stalls, varied line lengths, partial group ends, and resets.
            ce_in = (cycle%13 != 0 && cycle%17 != 0);
            ce2_in = (cycle%3 == 0);
            if (col == 0) begin
                case ((cycle/777)%8)
                    0: current_width = 2560;
                    1: current_width = 2559;
                    2: current_width = 639;
                    3: current_width = 640;
                    4: current_width = 319;
                    5: current_width = 320;
                    6: current_width = 5;
                    7: current_width = 1;
                endcase
                width = current_width;
            end
            vb_in = (cycle%8300 < 25);
            vs_in = (cycle%8300 < 4);
            hb_in = (col < 4 || col >= 2605);
            hs_in = (col > 2585 && col < 2597);
            field_in = ((cycle/8300)%2 != 0);
            rgb_in = $random(seed);
            reset = (cycle < 3 || cycle == 18000 || cycle == 36500);
            #1;
            compare(cycle);
            @(posedge clk);
            #1;
            compare(cycle);
            col=col+1;
            if (col == 2613) col=0;
        end
        $display("PASS: %0d RTL cycles, MLAB_PARTS=%0d", cycle, MLAB_PARTS);
        $finish;
    end
endmodule
