// Quartus synthesis-only top: all six memories are observable.
// Shared external addresses and data, but independent write enables.
module tb_six_packed_ram (
    input wire clk,
    input wire [5:0] we,
    input wire [11:0] wa,
    input wire [11:0] ra,
    input wire [39:0] d,
    output wire [39:0] q
);
    wire [39:0] q0,q1,q2,q3,q4,q5;
    crt_packed_ram #(.USE_MLAB(0)) bank0(clk,we[0],wa,ra,d,q0);
    crt_packed_ram #(.USE_MLAB(0)) bank1(clk,we[1],wa,ra,d,q1);
    crt_packed_ram #(.USE_MLAB(0)) bank2(clk,we[2],wa,ra,d,q2);
    crt_packed_ram #(.USE_MLAB(0)) bank3(clk,we[3],wa,ra,d,q3);
    crt_packed_ram #(.USE_MLAB(0)) bank4(clk,we[4],wa,ra,d,q4);
    crt_packed_ram #(.USE_MLAB(0)) bank5(clk,we[5],wa,ra,d,q5);
    assign q = q0 ^ q1 ^ q2 ^ q3 ^ q4 ^ q5;
endmodule
