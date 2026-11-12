# USER RUN ONLY: quartus_sta -t tests/report_timing_closure.tcl
# Quartus 17 APIs. -npaths 0 means unlimited, -nworst 1 means one worst path
# per endpoint. Never silently substitute a top-N list for failing endpoints.
source [file join [file dirname [info script]] restart/pulse_summary.tcl]
project_open Groovy -revision Groovy
create_timing_netlist
read_sdc
update_timing_netlist
set root output_files/timing_closure
file mkdir $root
set version [open $root/report_format.txt w]; puts $version "restart-v1"; close $version
report_clocks -file $root/clocks.txt
report_sdc -file $root/constraints.txt
report_sdc -ignored -file $root/ignored_constraints.txt
check_timing -include {no_clock multiple_clock generated_clock loops latches no_input_delay no_output_delay partial_input_delay partial_output_delay io_min_max_delay_consistency uncertainty partial_multicycle multicycle_consistency pll_cross_check} -file $root/check_timing.txt
report_ucp -file $root/unconstrained.txt
set manifest [open $root/corners.tsv w]
puts $manifest "directory\tname\tmodel\tspeed\tvoltage\ttemperature"
set summary [open $root/endpoint_summary.tsv w]
puts $summary "corner\tcheck\tfailing_endpoints\tendpoint_TNS_ns\tworst_slack_ns"
set filters [open $root/filters.tsv w]
puts $filters "corner\tfamily\tlaunch_registers\tcapture_registers"

proc node_name {id} {
    if {$id eq ""} {return ""}
    return [get_node_info -name $id]
}
proc all_negative {dir corner kind summary} {
    # A separate complete endpoint table is small even when full path routing
    # detail is large. Deduplicate by endpoint before summing negative slack.
    set paths [get_timing_paths -$kind -less_than_slack 0 -npaths 0 -nworst 1]
    array set worst {}
    array set details {}
    foreach_in_collection path $paths {
        set sink [node_name [get_path_info -to $path]]
        set slack [get_path_info -slack $path]
        if {![info exists worst($sink)] || $slack < $worst($sink)} {
            set worst($sink) $slack
            set details($sink) [list [node_name [get_path_info -from $path]] $slack [get_path_info -data_delay $path] [get_path_info -num_logic_levels $path]]
        }
    }
    set table [open $dir/negative_${kind}_endpoints.tsv w]
    puts $table "to\tfrom\tslack_ns\tdata_delay_ns\tlogic_levels"
    set tns 0.0
    foreach sink [lsort [array names worst]] {
        puts $table [join [linsert $details($sink) 0 $sink] "\t"]
        set tns [expr {$tns + $worst($sink)}]
    }
    close $table
    set worst_slack NA
    foreach_in_collection path [get_timing_paths -$kind -npaths 1] {
        set worst_slack [get_path_info -slack $path]
    }
    puts $summary "$corner\t$kind\t[array size worst]\t[format %.6f $tns]\t$worst_slack"
    flush $summary
    report_timing -$kind -less_than_slack 0 -npaths 0 -nworst 1 -detail full_path -show_routing -file $dir/negative_${kind}_paths.txt
    report_timing -$kind -npaths 8 -nworst 1 -detail full_path -show_routing -file $dir/worst_${kind}.txt
}
proc family {dir corner label from_pattern to_pattern filters {all_endpoints 0}} {
    set command [list report_timing -setup -npaths 8 -nworst 1 -detail full_path -show_routing -file $dir/${label}_setup.txt]
    set from_count ALL
    set to_count ALL
    if {$from_pattern ne ""} {
        set sources [get_registers $from_pattern]
        set from_count [get_collection_size $sources]
        lappend command -from $sources
    }
    if {$to_pattern ne ""} {
        set sinks [get_keepers $to_pattern]
        set to_count [get_collection_size $sinks]
        lappend command -to $sinks
    }
    puts $filters "$corner\t$label\t$from_count\t$to_count"
    flush $filters
    if {$from_count eq "0" || $to_count eq "0"} {
        # Renaming/retiming is not evidence of a passing family. Keep global
        # complete failure reports; explicitly mark this filter for review.
        set out [open $dir/${label}_setup.txt w]
        puts $out "UNMATCHED FILTER: from=$from_pattern to=$to_pattern; inspect complete endpoint reports."
        close $out
        post_message -type warning "Unmatched timing family $label in $corner"
    } else {
        eval $command
    }
}
set corners [get_available_operating_conditions -all]
if {[get_collection_size $corners] == 0} {error "No supported timing corners returned"}
set index 0
foreach_in_collection op $corners {
    incr index
    set name [get_operating_conditions_info -name $op]
    set corner [format corner_%02d $index]
    set dir $root/$corner
    file mkdir $dir
    puts $manifest "$corner\t$name\t[get_operating_conditions_info -model $op]\t[get_operating_conditions_info -speed $op]\t[get_operating_conditions_info -voltage $op]\t[get_operating_conditions_info -temperature $op]"
    flush $manifest
    set_operating_conditions $op
    update_timing_netlist
    foreach kind {setup hold recovery removal} {all_negative $dir $corner $kind $summary}
    export_pulse_checks $dir
    report_clock_transfers -file $dir/clock_transfers.txt
    family $dir $corner wcol {*u_vsize*wcol*} {*u_vsize*packed_ram*} $filters
    # Historical measured RTL intentionally has no column predicate register.
    if {[get_collection_size [get_registers {*u_vsize*column_in_range*}]] > 0} {
        family $dir $corner column_flag {*u_vsize*column_in_range*} {*u_vsize*packed_ram*} $filters
    } else {
        puts $filters "$corner\tcolumn_flag_absent_in_measured_rtl\t0\tALL"
    }
    family $dir $corner hb {*vga*hb* *u_vsize*hb_d*} {} $filters
    family $dir $corner poc_v {*|PoC_V*} {} $filters
    family $dir $corner vga {*vga*v_cnt* *|PoC_V*} {} $filters
    family $dir $corner delta_framebuffer {*PoC_lz4_delta_FB*} {} $filters
    family $dir $corner delta_index {*PoC_lz4_delta_index*} {} $filters
    family $dir $corner lz4_compressed {} {*lz4_compressed_bytes*} $filters 1
    family $dir $corner lz4_counters {} {*lz4*block_read_total* *lz4*block_write_total* *lz4*uncompressed_bytes* *lz4*LL* *lz4*ML* *lz4*window_addr* *lz4*MP*} $filters 1
    # Counter-to-state paths are independent of paths captured by counters.
    family $dir $corner lz4_counter_launch {*lz4*block_read_total* *lz4*block_write_total* *lz4*uncompressed_bytes* *lz4*LL* *lz4*ML* *lz4*window_addr* *lz4*MP*} {} $filters 1
    foreach part {0 1 2} {
        foreach bank {even odd} {
            family $dir $corner bank_${part}_${bank} {} "*u_vsize*packed_ram?${part}?.${bank}_ram*" $filters
        }
    }
}
close $manifest
close $summary
close $filters
puts "Exported $index operating conditions to $root; this script does not declare timing sign-off."
delete_timing_netlist
project_close
