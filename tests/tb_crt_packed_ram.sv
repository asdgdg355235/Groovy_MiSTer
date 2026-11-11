`timescale 1ns/1ps
module tb_crt_packed_ram;
    reg clk=0, we=0;
    reg [11:0] wa=0, ra=0;
    reg [39:0] d=0;
    wire [39:0] qm,ql;
    crt_packed_ram #(.USE_MLAB(0)) m10k(clk,we,wa,ra,d,qm);
    crt_packed_ram #(.USE_MLAB(1)) mlab(clk,we,wa,ra,d,ql);
    integer i;
    reg [39:0] word;
    initial begin
        // Noncolliding read addresses for deterministic hardware behavior.
        for(i=0;i<3072;i=i+1) begin
            @(negedge clk);
            we=1; wa=i[11:0]; ra=12'(3071-i);
            d=40'(i) ^ 40'hA52CDEF98A;
        end
        @(negedge clk); we=0;
        for(i=0;i<3072;i=i+1) begin
            @(negedge clk);
            ra=i[11:0];
            word=40'(i) ^ 40'hA52CDEF98A;
            @(negedge clk);
            // q values reflect preceding posedge's address.
            if(qm !== word || ql !== word) begin
                $display("RAM mismatch at %0d: M10K=%h MLAB=%h expected=%h",i,qm,ql,word);
                $fatal(1);
            end
        end
        $display("PASS: 3072x40 synchronous RAM, M10K and MLAB branches");
        $finish;
    end
    always #5 clk=~clk;
endmodule
