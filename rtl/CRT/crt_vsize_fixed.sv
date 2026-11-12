// SPDX-License-Identifier: GPL-3.0-or-later
// Cabinet adaptation of rmonic79's crt_vsize.sv (2026).
// Retains its two-neighbour, gamma-2 light redistribution and square-root
// encoder. Uses a pipelined, even/odd bank pair instead of eight CE subphases.
// Sync and field metadata pass through together, including half-line edges.
// No VSync reconstruction, no clock divider, no full-frame storage.
module crt_vsize_fixed #(
    parameter LINE_PX = 2560,
    parameter MAX_DELTA = 7,
    parameter RING_LINES = MAX_DELTA + 5,
    parameter MLAB_PARTS = 0 // 0..3 packed lanes per bank in distributed RAM
)(
    input clk, reset,
    input ce_in, ce2_in,
    input signed [5:0] size, // positive enlarges by this many physical scanlines
    input [15:0] width, height, // source pixels / lines IN THIS FIELD
    input [23:0] rgb_in,
    input hs_in, vs_in, hb_in, vb_in, field_in,
    output [23:0] rgb_out,
    output ce_out, ce2_out, hs_out, vs_out, hb_out, vb_out, field_out,
    output reg [15:0] picture_height = 0,
    output [5:0] picture_top,
    output reg running = 0,
    output reg underrun = 0
);
    localparam SW = $clog2(RING_LINES);
    // Five RGB888 pixels occupy exactly three 40-bit M10K words. Separate
    // 40-bit lanes avoid wasting the unused bits of a 24-bit-wide RAM mode.
    // Keep rows independently aligned so partial groups cannot cross fields.
    localparam GROUP_PX = 5;
    localparam GROUP_BITS = GROUP_PX*24;
    localparam LINE_WORDS = (LINE_PX+GROUP_PX-1)/GROUP_PX;
    localparam BANK_WORDS = (RING_LINES/2)*LINE_WORDS;
    localparam AW = $clog2(BANK_WORDS);
    // Adjacent source rows occupy different banks. Each bank needs one write
    // and one synchronous read port; the RGB store is not replicated for reads.
    reg [15:0] tag [0:RING_LINES-1];
    reg [RING_LINES-1:0] complete = 0;
    reg hb_d = 1, vs_d = 0, started = 0;
    wire line_begin = ce_in && !hb_in && hb_d;
    wire field_begin = ce_in && vs_in && !vs_d;
    reg [15:0] wcol = 0, wrow = 0, line_no = 0;
    // Track the exact quotient/remainder of wcol/5 on the same CE cycles.
    // The original wcol counter is retained for pixel/window comparisons.
    reg [AW-1:0] group_col = 0;
    reg [2:0] pixel_lane = 0;
    reg [SW-1:0] wslot = 0;
    reg [15:0] width_q = 0, height_q = 0, out_height = 0;
    reg [5:0] delay_lines = 0;
    reg [31:0] step = 0, position = 0;
    reg [SW-1:0] aslot = 0;
    reg [15:0] source_row = 0;
    reg line_active = 0;
    reg [15:0] displayed_rows = 0;

    function [SW-1:0] next_slot(input [SW-1:0] s);
        next_slot = (s == RING_LINES-1) ? SW'(0) : s + 1'b1;
    endfunction
    function [AW-1:0] address_word(input [SW-1:0] s, input [AW-1:0] word);
        // LINE_WORDS is constant; no pixel-clock division remains.
        address_word = AW'((32'(s) >> 1)*LINE_WORDS + 32'(word));
    endfunction

    // A restoring division runs once per field, in blanking. No pixel-rate
    // divider. Q16 error is less than one source line / 65536 per output row.
    reg [31:0] dividend = 0, quotient = 0;
    reg [16:0] remainder = 0;
    reg [5:0] div_bit = 0;
    reg dividing = 0;
    wire signed [16:0] requested_height = $signed({1'b0,height}) + 17'($signed(size));
    wire eligible = size != 0 && size >= -MAX_DELTA && size <= MAX_DELTA
                 && width != 0 && width <= LINE_PX && height >= 32
                 && height <= 1024 && requested_height >= 32;
    wire [16:0] shifted_rem = {remainder[15:0],dividend[div_bit[4:0]]};
    wire [31:0] position_next = position + step;
    wire [16:0] advance_rows = {1'b0,position_next[31:16]} - {1'b0,position[31:16]};
    wire [SW-1:0] next_aslot = (advance_rows == 2) ? next_slot(next_slot(aslot))
                                             : (advance_rows == 1) ? next_slot(aslot) : aslot;
    wire first_source = !started && !vb_in;
    wire [15:0] line_now = line_begin ? (first_source ? 16'd0 : line_no + 1'b1) : line_no;
    wire [15:0] row_now = line_begin && !vb_in ? (first_source ? 16'd0 : wrow + 1'b1) : wrow;
    wire [SW-1:0] write_slot = line_begin && !vb_in ? (first_source ? SW'(0) : next_slot(wslot)) : wslot;
    wire [15:0] col_now = line_begin ? 16'd0 : wcol;
    wire first_output = line_begin && line_now == {10'd0,delay_lines};
    wire output_now = line_begin ? ((started || first_source) && line_now >= {10'd0,delay_lines}
                               && {1'b0,line_now} < {1'b0,out_height}+{11'd0,delay_lines}) : line_active;
    wire [31:0] pos_now = line_begin ? (first_output ? 32'd0 : position_next) : position;
    wire [15:0] src_now = first_output ? 16'd0 : (line_begin ? source_row + advance_rows[15:0] : source_row);
    wire [SW-1:0] slot_now = first_output ? SW'(0) : (line_begin ? next_aslot : aslot);
    wire last_row = src_now >= height_q-1'b1;
    wire [SW-1:0] bslot = next_slot(slot_now);
    wire pair_ready = complete[slot_now] && tag[slot_now] == src_now
                   && (last_row || (complete[bslot] && tag[bslot] == src_now+1'b1));

    always @(posedge clk) begin
        if (ce_in) begin
            hb_d <= hb_in;
            vs_d <= vs_in;
            if (line_begin && (started || first_source)) begin
                started <= 1;
                line_no <= line_now;
                wcol <= 1;
                group_col <= 0;
                pixel_lane <= 3'd1;
                if (!vb_in) begin
                    wrow <= row_now;
                    wslot <= write_slot;
                    complete[write_slot] <= 0;
                    tag[write_slot] <= row_now;
                end
                line_active <= output_now;
                if(output_now && !vs_in) displayed_rows <= displayed_rows + 1'b1;
                if (output_now) begin
                    position <= pos_now;
                    source_row <= src_now;
                    aslot <= slot_now;
                end
            end else if (!hb_in && wcol < LINE_PX) begin
                wcol <= wcol + 1'b1;
                if (pixel_lane == GROUP_PX-1) begin
                    pixel_lane <= 0;
                    group_col <= group_col + 1'b1;
                end else pixel_lane <= pixel_lane + 1'b1;
            end
            if (running && !hb_in && !vb_in && col_now < LINE_PX && col_now < width_q && col_now == width_q-1'b1)
                complete[write_slot] <= 1;
            if (running && !hb_in && output_now && !vs_in && !pair_ready) underrun <= 1;
        end
        if (field_begin) begin
            started <= 0;
            line_active <= 0;
            complete <= 0;
            position <= 0;
            source_row <= 0;
            aslot <= 0;
            wslot <= 0;
            wrow <= 0;
            line_no <= 0;
            width_q <= width;
            height_q <= height;
            out_height <= requested_height[15:0];
            // Tell the edge mask the observed window height, including clipping
            // at native VSync. On a new geometry use the requested height until
            // the first field has completed; never wait a field to show video.
            picture_height <= !eligible ? height :
                (running && displayed_rows != 0 && width_q == width && height_q == height
                 && out_height == requested_height[15:0] ? displayed_rows : requested_height[15:0]);
            displayed_rows <= 0;
            // Two completed rows ahead of the reader; shrinking needs the
            // additional lead consumed as it advances through the field.
            delay_lines <= 6'd2 + (size < 0 ? 6'(-size) : 6'd0);
            dividend <= {height,16'd0};
            quotient <= 0;
            remainder <= 0;
            div_bit <= 31;
            dividing <= eligible;
            running <= eligible;
            underrun <= 0;
        end else if (dividing) begin
            remainder <= shifted_rem >= {1'b0,out_height} ? shifted_rem-{1'b0,out_height} : shifted_rem;
            quotient <= {quotient[30:0], shifted_rem >= {1'b0,out_height}};
            if (div_bit == 0) begin
                step <= {quotient[30:0], shifted_rem >= {1'b0,out_height}};
                dividing <= 0;
            end else div_bit <= div_bit-1'b1;
        end
        if (reset) begin
            running <= 0;
            displayed_rows <= 0;
            dividing <= 0;
            started <= 0;
            complete <= 0;
            line_active <= 0;
            hb_d <= 1;
            vs_d <= 0;
            underrun <= 0;
        end
    end

    // These are the gamma-2 decoder and split integer square-root encoder
    // from crt_vsize.sv's Cabinet path. Values are blended in linear light.
    function [31:0] isqrt_h(input [15:0] x0);
        reg [15:0] x, res;
        begin
            x=x0; res=0;
            if(x >= res+16'h4000) begin x=x-(res+16'h4000); res=(res>>1)+16'h4000; end else res=res>>1;
            if(x >= res+16'h1000) begin x=x-(res+16'h1000); res=(res>>1)+16'h1000; end else res=res>>1;
            if(x >= res+16'h0400) begin x=x-(res+16'h0400); res=(res>>1)+16'h0400; end else res=res>>1;
            if(x >= res+16'h0100) begin x=x-(res+16'h0100); res=(res>>1)+16'h0100; end else res=res>>1;
            isqrt_h={x,res};
        end
    endfunction
    function [7:0] isqrt_l(input [31:0] xr);
        reg [15:0] x, res;
        begin
            x=xr[31:16]; res=xr[15:0];
            if(x >= res+16'h0040) begin x=x-(res+16'h0040); res=(res>>1)+16'h0040; end else res=res>>1;
            if(x >= res+16'h0010) begin x=x-(res+16'h0010); res=(res>>1)+16'h0010; end else res=res>>1;
            if(x >= res+16'h0004) begin x=x-(res+16'h0004); res=(res>>1)+16'h0004; end else res=res>>1;
            if(x >= res+16'h0001) begin x=x-(res+16'h0001); res=(res>>1)+16'h0001; end else res=res>>1;
            isqrt_l=res[7:0];
        end
    endfunction
    // line_begin makes col_now zero immediately, before the first line-edge
    // register update. The bypasses below retain that same-cycle behavior.
    wire [AW-1:0] word_now = line_begin ? AW'(0) : group_col;
    wire [2:0] lane_now = line_begin ? 3'd0 : pixel_lane;
    wire [AW-1:0] read_word = col_now < LINE_PX ? word_now : AW'(0);
    // Precompute the write-slot and word-add cases before line_begin as well.
    // Keep the ungated current word, including non-writing saturated columns.
    wire [SW-1:0] write_line_slot = vb_in ? wslot : (first_source ? SW'(0) : next_slot(wslot));
    wire [AW-1:0] wa_line = address_word(write_line_slot, AW'(0));
    wire [AW-1:0] wa_current = address_word(wslot, group_col);
    wire [AW-1:0] wa = line_begin ? wa_line : wa_current;
    // Calculate both address cases before the CE-qualified line-start mux.
    // When line_begin is true, line_now is exactly this next line number,
    // and read_word is zero. Keeping the bank wrap/selection and word add
    // ahead of that final mux removes ce_in from their combinational cone.
    // No register or RAM read cycle is added; blanking reads are preserved.
    wire [15:0] read_line_no = first_source ? 16'd0 : line_no + 16'd1;
    wire [SW-1:0] read_line_slot = read_line_no == {10'd0,delay_lines} ? SW'(0) : next_aslot;
    wire [SW-1:0] read_line_bslot = next_slot(read_line_slot);
    wire [SW-1:0] read_bslot = next_slot(aslot);
    wire [AW-1:0] read_current_word = wcol < LINE_PX ? group_col : AW'(0);
    wire [AW-1:0] ra_even_line = address_word(read_line_slot[0] ? read_line_bslot : read_line_slot, AW'(0));
    wire [AW-1:0] ra_odd_line = address_word(read_line_slot[0] ? read_line_slot : read_line_bslot, AW'(0));
    wire [AW-1:0] ra_even_current = address_word(aslot[0] ? read_bslot : aslot, read_current_word);
    wire [AW-1:0] ra_odd_current = address_word(aslot[0] ? aslot : read_bslot, read_current_word);
    wire [AW-1:0] ra_even = line_begin ? ra_even_line : ra_even_current;
    wire [AW-1:0] ra_odd = line_begin ? ra_odd_line : ra_odd_current;
    wire write_pixel = running && !reset && ce_in && !hb_in && !vb_in
                    && col_now < LINE_PX && col_now < width_q;
    wire [2:0] write_lane = lane_now;
    wire flush_group = write_lane == GROUP_PX-1 || col_now == width_q-1'b1;
    wire write_even = write_pixel && flush_group && !write_slot[0];
    wire write_odd  = write_pixel && flush_group &&  write_slot[0];
    reg [GROUP_BITS-1:0] pack_q, pack_next;
    always @* begin
        pack_next = write_lane == 0 ? {GROUP_BITS{1'b0}} : pack_q;
        pack_next[write_lane*24 +: 24] = rgb_in;
    end
    always @(posedge clk) if(write_pixel) pack_q <= pack_next;
    wire [GROUP_BITS-1:0] qe, qo;
    genvar part;
    generate for(part=0;part<3;part=part+1) begin : packed_ram
        // A separate combinational mux output for each physical RAM read port.
        // Keep only these final drivers; arithmetic, memory inference and all
        // registers remain unchanged. Quartus must still be checked for merging.
        (* keep = "true" *) wire [AW-1:0] local_ra_even = line_begin ? ra_even_line : ra_even_current;
        (* keep = "true" *) wire [AW-1:0] local_ra_odd = line_begin ? ra_odd_line : ra_odd_current;
        // Reuse the stand-alone 3072x40 synchronous RAM inference pattern.
        // One even/odd pair per 40-bit slice; no replicated pixel storage.
        crt_packed_ram #(
            .BANK_WORDS(BANK_WORDS),
            .ADDR_WIDTH(AW),
            .USE_MLAB(part < MLAB_PARTS)
        ) even_ram (
            .clk(clk),
            .we(write_even),
            .wa(wa),
            .ra(local_ra_even),
            .d(pack_next[part*40 +: 40]),
            .q(qe[part*40 +: 40])
        );
        crt_packed_ram #(
            .BANK_WORDS(BANK_WORDS),
            .ADDR_WIDTH(AW),
            .USE_MLAB(part < MLAB_PARTS)
        ) odd_ram (
            .clk(clk),
            .we(write_odd),
            .wa(wa),
            .ra(local_ra_odd),
            .d(pack_next[part*40 +: 40]),
            .q(qo[part*40 +: 40])
        );
    end endgenerate
    reg [2:0] read_lane;
    always @(posedge clk) begin
        read_lane <= col_now < LINE_PX ? lane_now : 3'd0;
    end
    reg swap0;
    reg [7:0] alpha0, alpha1;
    wire [23:0] pe = qe[read_lane*24 +: 24];
    wire [23:0] po = qo[read_lane*24 +: 24];
    wire [23:0] a = swap0 ? po : pe;
    wire [23:0] b = alpha0 == 0 ? a : (swap0 ? pe : po);
    reg [15:0] ar,ag,ab,br,bg,bb;
    reg [24:0] mr,mg,mb;
    wire [8:0] wa_mix = 9'd256 - {1'b0,alpha1};
    wire [8:0] wb_mix = {1'b0,alpha1};
    reg [31:0] sr,sg,sb;
    reg [23:0] color;
    // ce, ce2, hs, vs, hb, vb, field, valid, in identical full-clock stages.
    reg [7:0] control [0:4];
    integer j;
    initial for(j=0;j<5;j=j+1) control[j]=8'b00001100;
    always @(posedge clk) begin
        swap0 <= slot_now[0];
        alpha0 <= last_row ? 8'd0 : pos_now[15:8];
        control[0] <= {ce_in,ce2_in,hs_in,vs_in,hb_in,(~output_now | vs_in),field_in,
                       output_now && !hb_in && !vs_in && pair_ready && !dividing};
        for(j=1;j<5;j=j+1) control[j] <= control[j-1];
        ar<=a[23:16]*a[23:16]; ag<=a[15:8]*a[15:8]; ab<=a[7:0]*a[7:0];
        br<=b[23:16]*b[23:16]; bg<=b[15:8]*b[15:8]; bb<=b[7:0]*b[7:0];
        alpha1<=alpha0;
        mr<=wa_mix*ar+wb_mix*br;
        mg<=wa_mix*ag+wb_mix*bg;
        mb<=wa_mix*ab+wb_mix*bb;
        sr<=isqrt_h(mr[23:8]); sg<=isqrt_h(mg[23:8]); sb<=isqrt_h(mb[23:8]);
        color<={isqrt_l(sr),isqrt_l(sg),isqrt_l(sb)};
    end
    assign picture_top = running ? delay_lines : 6'd0;
    assign rgb_out = running ? (control[4][0] ? color : 24'd0) : rgb_in;
    assign {ce_out,ce2_out,hs_out,vs_out,hb_out,vb_out,field_out} = running ? control[4][7:1]
                                                       : {ce_in,ce2_in,hs_in,vs_in,hb_in,vb_in,field_in};
`ifndef SYNTHESIS
    initial begin
        if (RING_LINES < MAX_DELTA+4 || RING_LINES%2 != 0) $fatal(1,"invalid Cabinet ring depth");
        if (MLAB_PARTS < 0 || MLAB_PARTS > 3) $fatal(1,"invalid distributed RAM allocation");
    end
`endif
endmodule
