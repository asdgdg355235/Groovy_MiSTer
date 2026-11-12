# Plain tclsh test, never loads or executes Quartus.
set root [file dirname [file dirname [file normalize [info script]]]]
set assignments {}
proc set_instance_assignment {args} {
    global assignments
    if {[llength $args] != 7 || [lrange $args 0 1] ne {-name DUPLICATE_ATOM} ||
        [lindex $args 3] ne "-from" || [lindex $args 5] ne "-to"} {error "Unexpected assignment: $args"}
    lappend assignments $args
}
source $root/rtl/CRT/crt_address_duplication.qsf
if {[llength $assignments] != 31} {error "Expected 31 targeted assignments"}
set names {}
foreach a $assignments {
    lassign $a flag type name from source to sink
    if {$name in $names} {error "Duplicate name $name"}
    lappend names $name
    if {$name eq "crt_read_word_bit3"} {
        set observed_source {emu:emu|crt_vsize_fixed:u_vsize|wa[3]~3}
        set observed_sink {emu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[3]~3}
    } else {
        if {![regexp {^crt_read_([012])_(even|odd)_bit([0-4])$} $name -> part bank bit]} {error $name}
        set observed_source [format {emu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[%d]~%d} $bit $bit]
        set observed_sink [format {emu:emu|crt_vsize_fixed:u_vsize|crt_packed_ram:packed_ram[%d].%s_ram|} $part $bank]
        # Hierarchies/leaf forms recorded in Candidate A's map audit.
        if {$part < 2} {append observed_sink {altdpram:distributed.mem_rtl_0|dpram_rro1:auto_generated|lutrama16}} else {append observed_sink {altsyncram:block_ram.mem_rtl_0|altsyncram_jpk1:auto_generated|ram_block1a8}}
        foreach p {0 1 2} {
            foreach b {even odd} {
                set other [format {emu:emu|crt_vsize_fixed:u_vsize|crt_packed_ram:packed_ram[%d].%s_ram|mem~0} $p $b]
                if {[string match $sink $other] != ($p == $part && $b eq $bank)} {error "Cross-bank target $sink"}
            }
        }
    }
    if {![string match $source $observed_source] || ![string match $sink $observed_sink]} {error "Nonmatching target: $a"}
}
puts "PASS: 31 unique assignments; observed source names match; six bank targets remain disjoint"
puts "Tcl syntax/matching only; Quartus assignment acceptance and physical duplication are unverified"
