// SPDX-License-Identifier: GPL-3.0-or-later
// RGB-only overscan mask. Blanking, sync, CE and picture geometry are untouched.
module crt_edge_mask (
    input clk, reset, ce,
    input enable,
    input [7:0] horizontal, vertical,
    input [15:0] width, height,
    input hb, vb, field,
    input [23:0] rgb_in,
    output [23:0] rgb_out
);
    reg hb_d = 1, vb_d = 1, seen = 0;
    reg [15:0] x = 0, y = 0;
    reg [15:0] observed_height[0:1];
    reg active_field = 0;
    initial begin observed_height[0]=0; observed_height[1]=0; end
    wire [15:0] edge_height = observed_height[field] != 0 ? observed_height[field] : height;
    wire start_line = !hb && hb_d;
    wire [15:0] px = start_line ? 16'd0 : x;
    wire [15:0] py = !seen || vb_d ? 16'd0 : (start_line ? y + 1'b1 : y);
    always @(posedge clk) begin
        if (ce) begin
            hb_d <= hb;
            vb_d <= vb;
            if(vb && !vb_d && seen) observed_height[active_field] <= y+1'b1;
            if (vb) begin y <= 0; seen <= 0; end
            else if (start_line) begin
                y <= py; seen <= 1;
                if(!seen) active_field <= field;
            end
            if (hb) x <= 0;
            else if (x != 16'hffff) x <= px + 1'b1;
        end
        if (reset) begin
            x<=0; y<=0; hb_d<=1; vb_d<=1; seen<=0; active_field<=0;
            observed_height[0]<=0; observed_height[1]<=0;
        end
    end
    // Addition comparisons avoid unsigned underflow on very small pictures.
    wire masked = (horizontal != 0 && (px < {8'd0,horizontal}
                  || {1'b0,px}+{9'd0,horizontal} >= {1'b0,width}))
               || (vertical != 0 && (py < {8'd0,vertical}
                  || {1'b0,py}+{9'd0,vertical} >= {1'b0,edge_height}));
    assign rgb_out = enable && !hb && !vb && masked ? 24'd0 : rgb_in;
endmodule
