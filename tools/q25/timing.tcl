# USER RUN ONLY. Adapted from the verified Q25 report_timing_closure APIs at
# Groovy_MiSTer 3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a.
source [file join [file dirname [info script]] pulse.tcl]
set revision [lindex $quartus(args) 0]
project_open Groovy -revision $revision
create_timing_netlist
read_sdc
update_timing_netlist
set root output_files/q25/timing
file mkdir $root
report_clocks -file $root/clocks.txt
report_sdc -file $root/constraints.txt
report_sdc -ignored -file $root/ignored_constraints.txt
check_timing -include {no_clock multiple_clock generated_clock loops latches no_input_delay no_output_delay partial_input_delay partial_output_delay io_min_max_delay_consistency uncertainty partial_multicycle multicycle_consistency pll_cross_check} -file $root/check_timing.txt
report_ucp -file $root/unconstrained.txt
set manifest [open $root/corners.tsv w]
puts $manifest "corner\tname\tmodel\tspeed\tvoltage\ttemperature"
set summary [open $root/summary.tsv w]
puts $summary "corner\tcheck\tfailing_endpoints\ttns_ns\twns_ns"
set corners [get_available_operating_conditions -all]
set index 0
foreach_in_collection op $corners {
    incr index
    set corner [format corner_%02d $index]
    set dir $root/$corner
    file mkdir $dir
    puts $manifest "$corner\t[get_operating_conditions_info -name $op]\t[get_operating_conditions_info -model $op]\t[get_operating_conditions_info -speed $op]\t[get_operating_conditions_info -voltage $op]\t[get_operating_conditions_info -temperature $op]"
    flush $manifest
    set_operating_conditions $op
    update_timing_netlist
    foreach kind {setup hold recovery removal} {
        set out [open $dir/all_${kind}_endpoints.tsv w]
        puts $out "to\tfrom\tslack_ns\tdata_delay_ns\tlogic_levels"
        array unset endpoints
        array set endpoints {}
        # Unlimited, one worst path per endpoint; positive endpoints included.
        foreach_in_collection path [get_timing_paths -$kind -npaths 0 -nworst 1] {
            set sink [get_node_info -name [get_path_info -to $path]]
            set slack [get_path_info -slack $path]
            if {![info exists endpoints($sink)] || $slack < [lindex $endpoints($sink) 2]} {
                set endpoints($sink) [list $sink [get_node_info -name [get_path_info -from $path]] $slack [get_path_info -data_delay $path] [get_path_info -num_logic_levels $path]]
            }
        }
        set failed 0
        set tns 0.0
        set wns NA
        foreach sink [lsort [array names endpoints]] {
            set row $endpoints($sink)
            puts $out [join $row "\t"]
            set slack [lindex $row 2]
            if {$wns eq "NA" || $slack < $wns} {set wns $slack}
            if {$slack < 0} {incr failed; set tns [expr {$tns + $slack}]}
        }
        close $out
        puts $summary "$corner\t$kind\t$failed\t$tns\t$wns"
        flush $summary
        report_timing -$kind -less_than_slack 0 -npaths 0 -nworst 1 -detail full_path -show_routing -file $dir/negative_${kind}_paths.txt
        report_timing -$kind -npaths 32 -nworst 1 -detail full_path -show_routing -file $dir/worst_${kind}_paths.txt
    }
    export_pulse_checks $dir
    report_clock_transfers -file $dir/clock_transfers.txt
}
close $manifest
close $summary
delete_timing_netlist
project_close
if {$index != 8} {error "Expected eight corners, received $index; reports retained, qualification rejected"}
puts "Eight corners exported. Timing, RAM, resources, warnings & hardware still require review."
