`timescale 1ns/1ps
module tb_crt_read_address #(parameter LINE_PX=32);
    reg clk=0;
    always #5 clk=~clk;
    reg reset=1, ce=0, ce2=0, hs=0, vs=0, hb=1, vb=1, field=0;
    reg signed [5:0] size=0;
    reg [15:0] width=16, height=240;
    reg [23:0] rgb=0;
    wire [23:0] rgb_new, rgb_ref;
    wire [6:0] sync_new, sync_ref;
    wire [15:0] height_new, height_ref;
    wire [5:0] top_new, top_ref;
    wire running_new, running_ref, underrun_new, underrun_ref;
    crt_vsize_fixed #(.LINE_PX(LINE_PX),.MLAB_PARTS(2)) dut (
        .clk(clk),.reset(reset),.ce_in(ce),.ce2_in(ce2),.size(size),
        .width(width),.height(height),.rgb_in(rgb),.hs_in(hs),.vs_in(vs),
        .hb_in(hb),.vb_in(vb),.field_in(field),.rgb_out(rgb_new),
        .ce_out(sync_new[6]),.ce2_out(sync_new[5]),.hs_out(sync_new[4]),
        .vs_out(sync_new[3]),.hb_out(sync_new[2]),.vb_out(sync_new[1]),
        .field_out(sync_new[0]),.picture_height(height_new),.picture_top(top_new),
        .running(running_new),.underrun(underrun_new));
    crt_vsize_fixed_reference #(.LINE_PX(LINE_PX),.MLAB_PARTS(2)) baseline (
        .clk(clk),.reset(reset),.ce_in(ce),.ce2_in(ce2),.size(size),
        .width(width),.height(height),.rgb_in(rgb),.hs_in(hs),.vs_in(vs),
        .hb_in(hb),.vb_in(vb),.field_in(field),.rgb_out(rgb_ref),
        .ce_out(sync_ref[6]),.ce2_out(sync_ref[5]),.hs_out(sync_ref[4]),
        .vs_out(sync_ref[3]),.hb_out(sync_ref[2]),.vb_out(sync_ref[1]),
        .field_out(sync_ref[0]),.picture_height(height_ref),.picture_top(top_ref),
        .running(running_ref),.underrun(underrun_ref));

    // Check the actual inputs of all six RAM instances at the capture edge.
    // No CE qualification: synchronous reads occur during stalls and blanking.
    genvar bank_part;
    generate for(bank_part=0;bank_part<3;bank_part++) begin : check_ram_ports
        always @(posedge clk) begin
            if ({dut.packed_ram[bank_part].even_ram.ra,
                 dut.packed_ram[bank_part].odd_ram.ra,
                 dut.packed_ram[bank_part].even_ram.wa,
                 dut.packed_ram[bank_part].odd_ram.wa,
                 dut.packed_ram[bank_part].even_ram.we,
                 dut.packed_ram[bank_part].odd_ram.we,
                 dut.packed_ram[bank_part].even_ram.d,
                 dut.packed_ram[bank_part].odd_ram.d} !==
                {baseline.packed_ram[bank_part].even_ram.ra,
                 baseline.packed_ram[bank_part].odd_ram.ra,
                 baseline.packed_ram[bank_part].even_ram.wa,
                 baseline.packed_ram[bank_part].odd_ram.wa,
                 baseline.packed_ram[bank_part].even_ram.we,
                 baseline.packed_ram[bank_part].odd_ram.we,
                 baseline.packed_ram[bank_part].even_ram.d,
                 baseline.packed_ram[bank_part].odd_ram.d})
                $fatal(1,"RAM port mismatch part=%0d",bank_part);
        end
    end endgenerate

    integer cycles=0, pixels=0, writes=0, line_starts=0, stalls=0;
    integer advances[0:2]='{0,0,0};
    integer wraps=0, last_slot=0, seed=32'h193fe207, scenario_id=0;
    integer qual_last=0, qual_saturated=0, qual_saturated_stall=0, qual_restart=0;
    reg was_saturated=0;
    reg fault=0;
    task automatic compare_addresses;
        begin
            if ({dut.wa,dut.ra_even,dut.ra_odd,dut.write_even,dut.write_odd,
                 dut.write_pixel,dut.flush_group,dut.write_lane,dut.pack_next} !==
                {baseline.wa,baseline.ra_even,baseline.ra_odd,baseline.write_even,baseline.write_odd,
                 baseline.write_pixel,baseline.flush_group,baseline.write_lane,baseline.pack_next})
                $fatal(1,"address/write mismatch cycle=%0d line_begin=%0b slot=%0d ra=%0d/%0d ref=%0d/%0d",
                    cycles,dut.line_begin,dut.slot_now,dut.ra_even,dut.ra_odd,baseline.ra_even,baseline.ra_odd);
        end
    endtask
    task automatic tick;
        begin
            @(negedge clk); #1;
            compare_addresses();
            // Require real threshold crossings, held false qualification under
            // CE gaps, and the next line's same-cycle address bypass. All six
            // captured RAM ports/data and registered video are compared below.
            if (dut.wcol == LINE_PX-1 && ce && !hb) qual_last++;
            if (dut.wcol == LINE_PX) begin
                qual_saturated++;
                if (!ce) qual_saturated_stall++;
            end
            if (was_saturated && dut.line_begin) qual_restart++;
            was_saturated = dut.wcol == LINE_PX;
            if (dut.line_begin && dut.output_now && !dut.first_output) begin
                if (dut.advance_rows <= 2) advances[dut.advance_rows]++;
                if (dut.slot_now < last_slot) wraps++;
                last_slot=dut.slot_now;
            end
            if(dut.line_begin) line_starts++;
            if(!ce) stalls++;
            if(dut.write_even || dut.write_odd) writes++;
            @(posedge clk); #1;
            // Include synchronous RAM outputs on every clock, even with CE=0,
            // in blanking and after wrap/reset; not just address expressions.
            if ({dut.qe,dut.qo,dut.pack_q,dut.read_lane,dut.slot_now,dut.bslot,
                 dut.pair_ready,dut.source_row,dut.position,dut.complete} !==
                {baseline.qe,baseline.qo,baseline.pack_q,baseline.read_lane,baseline.slot_now,baseline.bslot,
                 baseline.pair_ready,baseline.source_row,baseline.position,baseline.complete})
                $fatal(1,"registered RAM/control mismatch cycle=%0d",cycles);
            if ({rgb_new,sync_new,height_new,top_new,running_new,underrun_new} !==
                {rgb_ref,sync_ref,height_ref,top_ref,running_ref,underrun_ref})
                $fatal(1,"video/latency mismatch cycle=%0d",cycles);
            if(sync_new[6] && !sync_new[2] && !sync_new[1]) pixels++;
            cycles++;
        end
    endtask

    task automatic scenario(input integer d,w,h,ratio,interlace,front,add_stalls,do_reset,mid_reset);
        integer f,y,x,t,g,ht,at,vstart,vend,start_pixels,start_writes;
        begin
            scenario_id++;
            ce=0; ce2=0; hb=1; vb=1; vs=0; hs=0;
            reset=do_reset;
            repeat(6) tick();
            reset=0; size=6'(d); width=16'(w); height=16'(h);
            // Establish geometry on an actual field boundary before source data.
            ce=1; vs=1; tick(); ce=0; repeat(36) tick();
            vs=0; ce=1; tick(); ce=0; tick();
            start_pixels=pixels; start_writes=writes; ht=w+32;
            for(f=0;f<2;f++) begin
                for(y=0;y<h+24;y++) begin
                    for(x=0;x<ht;x++) begin
                        at=y*ht+x;
                        vstart=(h+front)*ht+((interlace && f%2) ? ht/2 : 0);
                        vend=vstart+3*ht;
                        hb=(x<8 || x>=w+8); vb=y>=h;
                        hs=x>=w+16 && x<w+24;
                        vs=at>=vstart && at<vend; field=interlace && f%2;
                        if(add_stalls && (x+3*y+f)%17==0) begin
                            ce=0; ce2=0;
                            for(g=0;g<3;g++) begin rgb=24'($random(seed)); tick(); end
                        end
                        for(t=0;t<ratio;t++) begin
                            ce=t==0; ce2=t==ratio/2;
                            rgb=24'($random(seed));
                            reset=mid_reset && f==0 && y==21 && x==9 && t==0;
                            tick();
                        end
                    end
                end
            end
            if(pixels==start_pixels) $fatal(1,"vacuous video test scenario=%0d",scenario_id);
            if(d!=0 && w<=LINE_PX && writes==start_writes) $fatal(1,"vacuous RAM test");
            $display("PASS: read/RAM/video equivalence d=%0d w=%0d h=%0d CE=%0d interlace=%0d stalls=%0d restart=%0d",
                     d,w,h,ratio,interlace,add_stalls,mid_reset);
        end
    endtask
    integer d,r,w;
    initial begin
        if(LINE_PX==32) begin
            for(d=-7;d<=7;d++) scenario(d,31,48,2,1,12,1,1,0);
            for(w=1;w<=6;w++) scenario(-7,w,49,1,0,12,1,1,0);
            for(r=1;r<=16;r*=2) scenario(7,32,240,r,1,2,1,1,0);
            scenario(-7,32,288,6,1,12,1,0,1);
            scenario(3,16,241,12,1,12,1,0,0);
            scenario(0,33,240,4,0,12,1,0,0);
        end else begin
            scenario(7,2560,240,1,0,12,1,1,0);
            scenario(-7,2559,240,2,1,12,1,0,0);
        end
        if(advances[0]==0 || advances[1]==0 || advances[2]==0 || wraps==0)
            $fatal(1,"missing source-step or ring-wrap coverage");
        if (qual_last==0 || qual_saturated==0 || qual_saturated_stall==0 || qual_restart==0)
            $fatal(1,"missing qualification boundary coverage: %0d/%0d/%0d/%0d",
                qual_last,qual_saturated,qual_saturated_stall,qual_restart);
        $display("PASS: qualifier boundary last=%0d saturated=%0d CE-stall=%0d next-line=%0d",
            qual_last,qual_saturated,qual_saturated_stall,qual_restart);
        $display("PASS: %0d clocks, %0d active pixels, %0d writes, advances=%0d/%0d/%0d wraps=%0d stalls=%0d lines=%0d",
                 cycles,pixels,writes,advances[0],advances[1],advances[2],wraps,stalls,line_starts);
        $finish;
    end
    initial begin #10000000000; $fatal(1,"timeout"); end
endmodule
