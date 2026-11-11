// Simulation-only models for Intel FIFOs/PLLs and the VHDL debug overlay.
module pll (
		input  wire        refclk,            //            refclk.clk
		input  wire        rst,               //             reset.reset
		output wire        outclk_0,          //           outclk0.clk
		output wire        locked,            //            locked.export
		input  wire [63:0] reconfig_to_pll,   //   reconfig_to_pll.reconfig_to_pll
		output wire [63:0] reconfig_from_pll  // reconfig_from_pll.reconfig_from_pll
	);
endmodule

module pll_cfg #(
		parameter ENABLE_BYTEENABLE   = 0,
		parameter BYTEENABLE_WIDTH    = 4,
		parameter RECONFIG_ADDR_WIDTH = 6,
		parameter RECONFIG_DATA_WIDTH = 32,
		parameter reconf_width        = 64,
		parameter WAIT_FOR_LOCK       = 1
	) (
		input  wire        mgmt_clk,          //          mgmt_clk.clk
		input  wire        mgmt_reset,        //        mgmt_reset.reset
		output wire        mgmt_waitrequest,  // mgmt_avalon_slave.waitrequest
		input  wire        mgmt_read,         //                  .read
		input  wire        mgmt_write,        //                  .write
		output wire [31:0] mgmt_readdata,     //                  .readdata
		input  wire [5:0]  mgmt_address,      //                  .address
		input  wire [31:0] mgmt_writedata,    //                  .writedata
		output wire [63:0] reconfig_to_pll,   //   reconfig_to_pll.reconfig_to_pll
		input  wire [63:0] reconfig_from_pll  // reconfig_from_pll.reconfig_from_pll
	);
endmodule

module fifo_sound (
	aclr,
	data,
	rdclk,
	rdreq,
	wrclk,
	wrreq,
	q,
	rdempty,
	wrfull,
	wrusedw);

	input	  aclr;
	input	[15:0]  data;
	input	  rdclk;
	input	  rdreq;
	input	  wrclk;
	input	  wrreq;
	output	[15:0]  q;
	output	  rdempty;
	output	  wrfull;
	output	[12:0]  wrusedw;

endmodule

module vga_overlay #(parameter COLS=3, OFFSETX=0, OFFSETY=0, RGB_FRONT=0)(input clk,ce,ena,input [10:0] i_pixel_out_x,input [9:0] i_pixel_out_y,output [23:0] o_pixel_out_data,output o_pixel_out_ena,input [COLS*8-1:0] textstring); assign o_pixel_out_data=0; assign o_pixel_out_ena=0; endmodule
module fifo_vga(input aclr,input [7:0] data,input rdclk,rdreq,wrclk,wrreq,output reg [7:0] q=0,output rdempty,wrfull,output [14:0] wrusedw);
reg [7:0] mem[0:16383]; reg [14:0] wp=0,rp=0;
assign rdempty=wp==rp; assign wrfull=wp-rp==16384; assign wrusedw=wp-rp;
always @(posedge wrclk or posedge aclr) if(aclr) wp<=0; else if(wrreq && !wrfull) begin mem[wp[13:0]]<=data; wp<=wp+1'b1; end
always @(posedge rdclk or posedge aclr) if(aclr) begin rp<=0; q<=0; end else if(rdreq && !rdempty) begin q<=mem[rp[13:0]]; rp<=rp+1'b1; end
endmodule
