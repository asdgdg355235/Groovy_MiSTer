// SPDX-License-Identifier: GPL-3.0-or-later
// Core-side glue for rmonic79's CRT Adjust & Cabinet photometric stage.
// Reference: MiSTer-CRT-Adjust c682de9f4acc61d8f4c7779efb48149d3baa3a8e.
module groovy_crt #(
    parameter HPOS_MODE = 1,
    parameter LINE_PX = 640,
    parameter RING_LINES = 46
)(
    input clk, reset,
    input request, unsupported,
    input [7:0] pixel_period,
    input [15:0] width, height, htotal, vtotal,
    input signed [4:0] hsize,
    input signed [8:0] hpos,
    input signed [5:0] vshift, vsize,
    input ce_in,
    input [23:0] rgb_in,
    input hs_in, vs_in, hb_in, vb_in, de_in,
    output selected,
    output supported,
    output reg ce_out = 0,
    output reg [23:0] rgb_out = 0,
    output reg hs_out = 0, vs_out = 0, de_out = 0,
    output reg de_osd = 0
);
    // Upstream counters are 10-bit pixels, 22-bit frame clocks, 5-bit CE.
    // These limits cover 240p/288p up to 640 active pixels. Interlace,
    // scandoubling, nonuniform CE & modes outside this envelope use legacy.
    wire eligible = !unsupported && pixel_period >= 8 && pixel_period <= 16
                  && width > 32 && width <= LINE_PX
                  && height >= 64 && height <= 288 && height < vtotal
                  && htotal > width && htotal <= 800
                  && vtotal >= 200 && vtotal <= 312;
    assign supported = eligible;
    reg [71:0] config_q = 0;
    wire [71:0] config_now = {width, height, htotal, vtotal, pixel_period};
    reg vs_d = 0;
    wire frame_edge = ce_in && vs_in && !vs_d;
    reg [2:0] stable_frames = 0;
    reg ready = 0;
    reg [5:0] ce_age = 0;
    reg ce_seen = 0;
    reg ce_good = 0;
    always @(posedge clk) begin
        if (ce_in) vs_d <= vs_in;
        if (reset || config_now != config_q) begin
            config_q <= config_now;
            stable_frames <= 0;
            ready <= 0;
            ce_age <= 0;
            ce_seen <= 0;
            ce_good <= 0;
        end else begin
            if (ce_in) begin
                ce_age <= 0;
                ce_seen <= 1;
                ce_good <= ce_seen && ({2'd0,ce_age} + 8'd1 == pixel_period);
            end else if (!(&ce_age)) ce_age <= ce_age + 1'b1;
            if (!eligible || !request || (ce_in && ce_seen && {2'd0,ce_age} + 8'd1 != pixel_period)) begin
                stable_frames <= 0;
                ready <= 0;
            end else if (frame_edge && ce_good) begin
                if (stable_frames != 6) stable_frames <= stable_frames + 1'b1;
                ready <= stable_frames >= 5;
            end
        end
    end
    // Remove selection immediately on reset/configuration changes. Re-entry
    // waits for six complete native frame boundaries, clearing old metadata.
    assign selected = ready && request && eligible && !reset
                    && config_now == config_q && ce_good;

    wire [23:0] vz_rgb;
    wire vz_hs, vz_vs, vz_de, vz_vb, vz_ce;
    wire cabinet = selected && vsize != 0;
    crt_vsize #(.LINE_PX(LINE_PX), .RING_LINES(RING_LINES)) u_vsize (
        .clk(clk), .pxl_cen(ce_in), .active(cabinet), .tube_mode(1'b1),
        .vsize(vsize), .r_in(rgb_in[23:16]), .g_in(rgb_in[15:8]), .b_in(rgb_in[7:0]),
        .hs_in(hs_in), .vs_in(vs_in), .de_in(de_in), .vb_in(vb_in),
        .r_out(vz_rgb[23:16]), .g_out(vz_rgb[15:8]), .b_out(vz_rgb[7:0]),
        .hs_out(vz_hs), .vs_out(vz_vs), .de_out(vz_de), .vb_out(vz_vb), .ce_out(vz_ce)
    );
    // Zero-size has no Cabinet latency. The V-Size stage owns regenerated VB.
    wire wr_ce = cabinet ? vz_ce : ce_in;
    wire [23:0] wr_rgb = cabinet ? vz_rgb : rgb_in;
    wire wr_hs = cabinet ? vz_hs : hs_in;
    wire wr_vs = cabinet ? vz_vs : vs_in;
    wire wr_vb = cabinet ? vz_vb : vb_in;
    wire wr_de = cabinet ? vz_de : de_in;

    wire hs_ref;
    reg hs_ref_d = 0;
    wire hs_ref_rise = hs_ref && !hs_ref_d;
    reg [8:0] rd_acc = 0;
    wire signed [10:0] period_s = $signed({1'b0,pixel_period,2'b00}) + 11'(hsize);
    wire [8:0] rd_period = period_s < 8 ? 9'd8 : period_s[8:0];
    wire [9:0] rd_sum = {1'b0, rd_acc} + 10'd4;
    wire rd_tick = rd_sum >= {1'b0, rd_period};
    wire [9:0] rd_next = rd_tick ? rd_sum - {1'b0,rd_period} : rd_sum;
    wire rd_ce = selected ? rd_tick : wr_ce;
    always @(posedge clk) begin
        hs_ref_d <= hs_ref;
        if (reset || !selected || hs_ref_rise) rd_acc <= 0;
        else rd_acc <= rd_next[8:0];
    end

    wire [23:0] str_rgb;
    wire str_hs, str_vs, str_hb, str_vb;
    crt_adjust #(.AW(11), .HTOTAL(1024), .VTOTAL(512),
                 .DYNAMIC_TOTALS(1), .HPOS_MODE(HPOS_MODE)) u_adjust (
        .clk(clk), .pxl_cen(wr_ce), .pxl2_cen(rd_ce), .active(selected),
        .htotal(htotal), .vtotal(vtotal), .hsize(hsize), .hoffset(hpos), .voffset(vshift),
        .r_in(wr_rgb[23:16]), .g_in(wr_rgb[15:8]), .b_in(wr_rgb[7:0]),
        .hs_in(wr_hs), .vs_in(wr_vs),
        .hb_in(!wr_de), .vb_in(wr_vb),
        .r_out(str_rgb[23:16]), .g_out(str_rgb[15:8]), .b_out(str_rgb[7:0]),
        .hs_out(str_hs), .vs_out(str_vs), .hb_out(str_hb), .vb_out(str_vb),
        .hs_ref_out(hs_ref)
    );

    // Native horizontal anchor, regenerated vertical window, previous line.
    // Same line reference & one-line VB alignment as u_adjust.vb_active.
    reg wr_hs_d = 0;
    reg vb_active = 1;
    reg native_blank_d = 1, str_d = 0, osd_window = 0;
    // Only an actual native HBlank falling edge can open the OSD window.
    // In SYNCSHIFT, regenerated VB can change inside native active pixels;
    // treating that as a native DE rise would move the OSD horizontally.
    wire native_rise = !hb_in && native_blank_d && !vb_active;
    wire str_active = !str_hb;
    wire str_fall = str_d && !str_active;
    reg rd_ce_q = 0;
    always @(posedge clk) begin
        if (wr_ce) begin
            wr_hs_d <= hs_ref;
            if (hs_ref && !wr_hs_d) begin
                vb_active <= wr_vb;
            end
        end
        if (ce_in) native_blank_d <= hb_in;
        // Observe the registered image window at full clock rate: a shrunk
        // window can close between native pixel enables.
        str_d <= str_active;
        if (reset || !selected || vb_active) osd_window <= 0;
        else if (native_rise) osd_window <= 1;
        else if (str_fall) osd_window <= 0;

        rd_ce_q <= rd_ce;
        ce_out <= rd_ce_q;
        rgb_out <= str_rgb;
        hs_out <= str_hs;
        vs_out <= str_vs;
        de_out <= str_active;
        // Window changes & RGB are observed after u_adjust's output register.
        de_osd <= osd_window;
    end
endmodule
