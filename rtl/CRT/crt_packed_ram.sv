// SPDX-License-Identifier: GPL-3.0-or-later
// Isolated, synchronous simple dual-port memory based on the Quartus 17
// ram_probe experiment. No resets or initialization of pixel storage.
module crt_packed_ram #(
    parameter integer BANK_WORDS = 3072,
    parameter integer ADDR_WIDTH = 12,
    parameter integer USE_MLAB = 0
)(
    input  wire                    clk,
    input  wire                    we,
    input  wire [ADDR_WIDTH-1:0]   wa,
    input  wire [ADDR_WIDTH-1:0]   ra,
    input  wire [39:0]             d,
    output reg  [39:0]             q
);
    // The M10K branch deliberately retains the successful probe's
    // array declaration and read/write always block without alterations.
    generate if (USE_MLAB) begin : distributed
        (* ramstyle = "MLAB, no_rw_check" *) reg [39:0] mem [0:BANK_WORDS-1];

        always @(posedge clk) begin
            if (we)
                mem[wa] <= d;
            q <= mem[ra];
        end
    end else begin : block_ram
        (* ramstyle = "M10K, no_rw_check" *) reg [39:0] mem [0:BANK_WORDS-1];

        always @(posedge clk) begin
            if (we)
                mem[wa] <= d;
            q <= mem[ra];
        end
    end endgenerate
endmodule
