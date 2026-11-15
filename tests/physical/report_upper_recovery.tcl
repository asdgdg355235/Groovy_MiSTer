# USER RUN ONLY. Read timing paths from a COPY of the existing fitted database.
# APIs/options follow the measured Q25 tests/report_timing_closure.tcl interface.
# Bounded positive detail is paired with complete filtered endpoint inventories.
source [file join [file dirname [info script]] common.tcl]
if {![info exists ::env(R0_PHYS_EXPORT_DIR)]} {error "Fresh export destination required"}
project_open Groovy -revision Groovy
create_timing_netlist
read_sdc
update_timing_netlist
set root [file join $::env(R0_PHYS_EXPORT_DIR) upper_recovery_paths]
set manifest [physical::table $root/corners.tsv {corner name}]
set filters [physical::table $root/filters.tsv {corner family launch_objects capture_objects status}]
set endpoints [physical::table $root/endpoints.tsv {corner family launch capture slack_ns data_delay_ns logic_levels clock_skew_ns}]
set errors [physical::table $root/query_errors.tsv {corner family error}]
set families {
    vga_to_root {*vga*} {*Add17* *PoC_px_frameskip*}
    root_to_vga {*|state* *|PoC_V*} {*vga*}
    crt_hb {*vga*hb* *u_vsize*hb_d*} {*u_vsize*packed_ram*}
    crt_advance {*u_vsize*advance_rows*} {*u_vsize*packed_ram*}
}
set through_families {
    upper_even {*local_ra_even*10* *crt_upper_1_even_bit10*}
    upper_odd {*local_ra_odd*9* *crt_upper_0_odd_bit9*}
}
# Through queries use actual pin collections; no invented physical MLAB pins.
foreach {family patterns} $through_families {lappend families $family {} {}}

set selected [physical::table $root/through_nodes.tsv {corner family name type location}]
set i 0
foreach_in_collection op [get_available_operating_conditions -all] {
    incr i
    set corner [format corner_%02d $i]
    physical::row $manifest [list $corner [get_operating_conditions_info -name $op]]
    set_operating_conditions $op
    update_timing_netlist
    foreach {family from to} $families {
        set dir $root/$corner
        file mkdir $dir
        set options {}
        set launches ALL
        set captures ALL
        if {$from ne ""} {
            set nodes [get_keepers $from]
            set launches [get_collection_size $nodes]
            lappend options -from $nodes
        }
        if {$to ne ""} {
            set nodes [get_keepers $to]
            set captures [get_collection_size $nodes]
            lappend options -to $nodes
        }
        if {$launches eq "0" || $captures eq "0"} {
            physical::row $filters [list $corner $family $launches $captures UNMATCHED]
            continue
        }
        if {[string match upper_* $family]} {
            set at [lsearch -exact $through_families $family]
            set pins [get_pins [lindex $through_families [expr {$at+1}]]]
            if {[get_collection_size $pins] == 0} {
                physical::row $filters [list $corner $family 0 0 UNMATCHED_THROUGH_PINS]
                continue
            }
            foreach_in_collection pin $pins {
                physical::row $selected [list $corner $family [get_node_info -name $pin] [get_node_info -type $pin] [get_node_info -location $pin]]
            }
            lappend options -through $pins
        }
        set count 0
        if {[catch {
            set paths [eval [concat [list get_timing_paths -setup -npaths 0 -nworst 1] $options]]
            foreach_in_collection path $paths {
                incr count
                physical::row $endpoints [list $corner $family \
                    [get_node_info -name [get_path_info -from $path]] \
                    [get_node_info -name [get_path_info -to $path]] \
                    [get_path_info -slack $path] [get_path_info -data_delay $path] \
                    [get_path_info -num_logic_levels $path] [get_path_info -clock_skew $path]]
            }
            eval [concat [list report_timing -setup -npaths 8 -nworst 1 -detail full_path -show_routing -file $dir/${family}_setup.txt] $options]
        } message]} {
            physical::row $errors [list $corner $family $message]
            physical::row $filters [list $corner $family $launches $captures QUERY_ERROR]
        } elseif {$count == 0} {
            physical::row $filters [list $corner $family $launches $captures NO_PATHS]
        } else {physical::row $filters [list $corner $family $launches $captures OBSERVED]}
    }
}
foreach handle [list $manifest $filters $endpoints $errors $selected] {close $handle}
delete_timing_netlist
project_close
