# Plain tclsh test, never loads or executes Quartus.
set root [file dirname [file dirname [file normalize [info script]]]]
set assignments {}
proc set_instance_assignment {args} {
    global assignments
    if {[llength $args] != 7 || [lrange $args 0 1] ne {-name DUPLICATE_ATOM} ||
        [lindex $args 3] ne "-from" || [lindex $args 5] ne "-to"} {error "Unexpected assignment: $args"}
    lappend assignments $args
}
if {[info exists ::env(CRT_DUPLICATE_QSF)]} {
    source $::env(CRT_DUPLICATE_QSF)
} else {
    source $root/rtl/CRT/crt_address_duplication.qsf
}
if {[llength $assignments] != 30} {error "Expected 30 targeted assignments"}
set names {}
foreach a $assignments {
    lassign $a flag type name from source to sink
    if {$name in $names} {error "Duplicate name $name"}
    lappend names $name
    if {![regexp {^crt_read_([012])_(even|odd)_bit([0-4])$} $name -> part bank bit]} {error $name}
    set observed_source [format {emu:emu|crt_vsize_fixed:u_vsize|packed_ram[1].local_ra_odd[%d]~%d} $bit $bit]
    set observed_sink [format {emu:emu|crt_vsize_fixed:u_vsize|crt_packed_ram:packed_ram[%d].%s_ram|} $part $bank]
    # Hierarchies/leaf forms recorded in Candidate A's map audit.
    if {$part < 2} {append observed_sink {altdpram:distributed.mem_rtl_0|dpram_rro1:auto_generated|lutrama16}} else {append observed_sink {altsyncram:block_ram.mem_rtl_0|altsyncram_jpk1:auto_generated|ram_block1a8}}
    foreach p {0 1 2} {
        foreach b {even odd} {
            set other [format {emu:emu|crt_vsize_fixed:u_vsize|crt_packed_ram:packed_ram[%d].%s_ram|mem~0} $p $b]
            if {[expr {[string first [string range $sink 0 end-1] $other] == 0}] != ($p == $part && $b eq $bank)} {error "Cross-bank target $sink"}
        }
    }
    if {(![info exists ::env(CRT_DUPLICATE_QSF)] && $source ne $observed_source) || ![expr {$sink eq $observed_sink || ([string index $sink end] eq "*" && [string first [string range $sink 0 end-1] $observed_sink] == 0)}]} {error "Nonmatching target: $a"}
}
puts "PASS: 30 unique assignments; observed source names match; six bank targets remain disjoint"
puts "Exact source names and literal destination prefixes only; Quartus assignment acceptance and physical duplication are unverified"

if {[llength $argv] && [lindex $argv 0] eq "--dump"} {
    foreach a $assignments {puts [join [list ASSIGN [lindex $a 2] [lindex $a 4] [lindex $a 6]] "\t"]}
}
