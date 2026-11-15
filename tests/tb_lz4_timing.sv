`timescale 1ns/1ps
module tb_lz4_timing;
    reg clk=0;
    always #5 clk=~clk;
    reg reset=1, mode64=0, run=0, stop=0, write_long=0;
    reg [31:0] compressed_bytes=0;
    reg [63:0] compressed_long=0, delta=0;
    wire ready, byte_valid, long_valid, paused, done, error, read_ready;
    wire [7:0] byte_out;
    wire [63:0] long_out;
    wire [31:0] count, written, read_count;
    wire [3:0] state;
    wire ref_ready, ref_byte_valid, ref_long_valid, ref_paused, ref_done, ref_error, ref_read_ready;
    wire [7:0] ref_byte;
    wire [63:0] ref_long;
    wire [31:0] ref_count, ref_written, ref_read_count;
    wire [3:0] ref_state;
    lz4 dut(.lz4_clk(clk),.lz4_reset(reset),.lz4_mode_64(mode64),.lz4_run(run),
        .lz4_stop(stop),.lz4_compressed_bytes(compressed_bytes),.lz4_compressed_long(compressed_long),
        .lz4_write_long(write_long),.lz4_delta_long(delta),.lz4_write_ready(ready),
        .lz4_uncompressed_byte(byte_out),.lz4_byte_valid(byte_valid),.lz4_uncompressed_long(long_out),
        .lz4_long_valid(long_valid),.lz4_uncompressed_bytes(count),.lz4_paused(paused),
        .lz4_done(done),.lz4_error(error),.lz4_state(state),.lz4_writed_bytes(written),
        .lz4_readed_bytes(read_count),.lz4_read_ready(read_ready));
    lz4_reference baseline(.lz4_clk(clk),.lz4_reset(reset),.lz4_mode_64(mode64),.lz4_run(run),
        .lz4_stop(stop),.lz4_compressed_bytes(compressed_bytes),.lz4_compressed_long(compressed_long),
        .lz4_write_long(write_long),.lz4_delta_long(delta),.lz4_write_ready(ref_ready),
        .lz4_uncompressed_byte(ref_byte),.lz4_byte_valid(ref_byte_valid),.lz4_uncompressed_long(ref_long),
        .lz4_long_valid(ref_long_valid),.lz4_uncompressed_bytes(ref_count),.lz4_paused(ref_paused),
        .lz4_done(ref_done),.lz4_error(ref_error),.lz4_state(ref_state),.lz4_writed_bytes(ref_written),
        .lz4_readed_bytes(ref_read_count),.lz4_read_ready(ref_read_ready));
    integer cycles=0, packets=0, received=0, n=0, expected_n=0;
    integer i,j,k,m,st,low,ll,rr,rst,gate,counter_seed;
    integer states_seen=0;
    reg [7:0] packet[0:4095], expected[0:131071];
    reg checking=0, emitted;
    reg [31:0] old_count;
    reg old_window_write;
    reg [12:0] old_window_write_addr;
    reg [3:0] increment;
    reg [7:0] expected_sum;
    always @(posedge clk) begin
        old_count=count;
        old_window_write=dut.window_write_enable;
        old_window_write_addr=dut.window_addr13;
        emitted=run && (!long_valid || !stop);
        #1;
        if (old_window_write &&
            dut.window[old_window_write_addr] !== baseline.window[old_window_write_addr])
            $fatal(1,"LZ4 window mismatch cycle=%0d address=%0d",cycles,old_window_write_addr);
        cycles=cycles+1;
        states_seen=states_seen | (1 << state);
        if ({ready,byte_out,byte_valid,long_out,long_valid,count,paused,done,error,state,written,read_count,read_ready}
            !== {ref_ready,ref_byte,ref_byte_valid,ref_long,ref_long_valid,ref_count,ref_paused,ref_done,ref_error,ref_state,ref_written,ref_read_count,ref_read_ready})
            $fatal(1,"LZ4 output mismatch cycle=%0d state=%0d count=%h/%h",cycles,state,count,ref_count);
        if ({dut.block_read_addr,dut.block_read_index,dut.block_read_total,dut.LL,dut.ML,
             dut.LL_W,dut.ML_W,dut.MP,dut.MP3,dut.MP13,dut.window_addr,dut.window_addr3,dut.window_addr13}
            !== {baseline.block_read_addr,baseline.block_read_index,baseline.block_read_total,baseline.LL,baseline.ML,
             baseline.LL_W,baseline.ML_W,baseline.MP,baseline.MP3,baseline.MP13,baseline.window_addr,baseline.window_addr3,baseline.window_addr13})
            $fatal(1,"LZ4 internal state mismatch cycle=%0d",cycles);
        if(checking && emitted && count != old_count) begin
            if(mode64) begin
                increment=count-old_count;
                if(!long_valid || increment>8) $fatal(1,"invalid long update");
                for(integer b=0;b<increment;b=b+1) begin
                    if(received>=expected_n || long_out[8*b +:8] !== expected[received])
                        $fatal(1,"decoded long byte %0d got=%h expected=%h",received,long_out[8*b +:8],expected[received]);
                    received=received+1;
                end
            end else begin
                if(!byte_valid || byte_out !== expected[received])
                    $fatal(1,"decoded byte %0d",received);
                received=received+1;
            end
        end
    end
    task tick;
        @(negedge clk);
    endtask
    task clear_stream;
        begin
            checking=0; run=0; reset=1; write_long=0; stop=0; delta=0;
            repeat(2) tick(); reset=0;
        end
    endtask
    task put(input integer value);
        begin packet[n]=value; n=n+1; end
    endtask
    task length_extra(input integer value);
        integer left;
        begin left=value; while(left>=255) begin put(255); left=left-255; end put(left); end
    endtask
    task make_packet(input integer literals, distance, match_count);
        integer x;
        begin
            n=0; expected_n=0;
            put(((literals<15?literals:15)<<4) | (match_count==0?0:(match_count-4<15?match_count-4:15)));
            if(literals>=15) length_extra(literals-15);
            for(x=0;x<literals;x=x+1) begin
                put((x*37+19)&255); expected[expected_n]=packet[n-1]; expected_n=expected_n+1;
            end
            if(match_count!=0) begin
                put(distance&255); put(distance>>8);
                if(match_count-4>=15) length_extra(match_count-19);
                for(x=0;x<match_count;x=x+1) begin
                    expected[expected_n]=expected[expected_n-distance]; expected_n=expected_n+1;
                end
                put(8'h50);
                for(x=0;x<5;x=x+1) begin put(8'h91+x); expected[expected_n]=packet[n-1]; expected_n=expected_n+1; end
            end
        end
    endtask
    task decode_packet;
        integer word_index, timeout, timeout_limit;
        begin
            clear_stream(); compressed_bytes=n; received=0;
            // Feed input with gaps while the decoder runs; test paused/ready.
            word_index=0; timeout=0; timeout_limit=12000+expected_n*4; run=1; checking=1;
            while(!done && timeout<timeout_limit) begin
                write_long=0;
                if(word_index<(n+7)/8 && ready && timeout%5==0) begin
                    for(integer b=0;b<8;b=b+1) compressed_long[8*b +:8]=word_index*8+b<n?packet[word_index*8+b]:0;
                    write_long=1; word_index=word_index+1;
                end
                run=(timeout%7!=3); stop=(timeout%11==2 || timeout%11==3);
                tick(); timeout=timeout+1;
            end
            write_long=0; checking=0; run=0;
            if(!done || error || received!=expected_n || count!=expected_n)
                $fatal(1,"packet failure mode64=%0d done=%0b error=%0b bytes=%0d/%0d count=%0d",mode64,done,error,received,expected_n,count);
            packets=packets+1;
        end
    endtask
    initial begin
        for(i=0;i<8192;i=i+1) begin dut.window[i]=0; baseline.window[i]=0; end
        for(i=0;i<128;i=i+1) begin dut.blocks[i]=0; baseline.blocks[i]=0; end
        dut.window_data=0; baseline.window_data=0;
        repeat(2) tick();
        // Exhaust all modulo-256 input pairs through the actual output assignments.
        for(i=0;i<256;i=i+1) for(j=0;j<256;j=j+1) begin
            expected_sum=i+j;
            dut.uncompressed_long={8{i[7:0]}}; baseline.uncompressed_long={8{i[7:0]}};
            delta={8{j[7:0]}}; #1;
            if(long_out!=={8{expected_sum}}) $fatal(1,"delta arithmetic %0d/%0d",i,j);
        end
        for(m=0;m<2;m=m+1) begin
            mode64=m;
            for(k=0;k<7;k=k+1) begin
                case(k) 0: ll=1; 1: ll=7; 2: ll=8; 3: ll=15; 4: ll=16; 5: ll=255; 6: ll=270; endcase
                make_packet(ll,0,0); decode_packet();
            end
            make_packet(1400,0,0); decode_packet(); // input ring wraps at 1024 bytes
            for(k=1;k<=8;k=k+1) begin make_packet(40,k,80); decode_packet(); end
            make_packet(64,17,160); decode_packet();
            make_packet(64,32,160); decode_packet();
            // More than 65536 output bytes: exercise the complete 8192-word window rollover.
            make_packet(64,8,65500); decode_packet();
        end
        // All state/mode/offset combinations; rollover and concurrent reset/run.
        // Deliberate state injection supplements valid packet tests, it does
        // not claim all these combinations are reachable on the protocol.
        checking=0;
        for(st=0;st<16;st=st+1) for(m=0;m<2;m=m+1)
        for(low=0;low<8;low=low+1) for(ll=0;ll<2;ll=ll+1)
        for(counter_seed=0;counter_seed<2;counter_seed=counter_seed+1)
        for(rr=0;rr<3;rr=rr+1) for(rst=0;rst<2;rst=rst+1) for(gate=0;gate<3;gate=gate+1) begin
            run=gate!=0; stop=gate==2; reset=rst; mode64=m; write_long=0;
            dut.state=st; baseline.state=st;
            dut.LL=ll; baseline.LL=ll;
            dut.window_addr3=low; baseline.window_addr3=low;
            dut.block_read_total=counter_seed==0?8:32'hffffffff; baseline.block_read_total=dut.block_read_total;
            dut.block_write_total=rr==0?8:16; baseline.block_write_total=rr==0?8:16;
            compressed_bytes=rr==2?8:32;
            dut.uncompressed_bytes=counter_seed==0?32'hfffffffc:32'hffffffff; baseline.uncompressed_bytes=dut.uncompressed_bytes;
            dut.long_valid=1; baseline.long_valid=1;
            delta={32'h8137ffff,cycles[31:0]};
            tick();
        end
        clear_stream();
        // Compressed write-total and 128-word write-address rollover.
        dut.block_read_total=32'hfffffff8; baseline.block_read_total=32'hfffffff8;
        dut.block_write_total=32'hfffffff8; baseline.block_write_total=32'hfffffff8;
        dut.block_write_addr=127; baseline.block_write_addr=127;
        write_long=1; tick(); write_long=0;
        if(written!=0 || dut.block_write_addr!=0) $fatal(1,"compressed write rollover");
        clear_stream(); mode64=1; make_packet(33,8,80); decode_packet();
        $display("PASS: LZ4 %0d clocks, %0d golden packets, all counter states/reset/stalls/rollover; delta 65536 pairs",cycles,packets);
        $display("LZ4 visited state mask=%h",states_seen);
        $finish;
    end
endmodule
