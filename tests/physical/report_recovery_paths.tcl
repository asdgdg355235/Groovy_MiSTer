# USER RUN ONLY. Read timing paths from a COPY of the existing fitted database.
# APIs/options follow the measured Q25 tests/report_timing_closure.tcl interface.
# Bounded positive detail is paired with complete filtered endpoint inventories.
source [file join [file dirname [info script]] common.tcl]
if {![info exists ::env(R0_PHYS_EXPORT_DIR)]} {error "Fresh export destination required"}
project_open Groovy -revision Groovy
create_timing_netlist
read_sdc
update_timing_netlist
set root [file join $::env(R0_PHYS_EXPORT_DIR) recovery_paths]
set manifest [physical::table $root/corners.tsv {corner name}]
set filters [physical::table $root/filters.tsv {corner family launch_objects capture_objects status}]
set endpoints [physical::table $root/endpoints.tsv {corner family launch capture slack_ns data_delay_ns logic_levels clock_skew_ns}]
set errors [physical::table $root/query_errors.tsv {corner family error}]
set families {
    lz4_window_capture {} {*lz4*window_rtl_0*}
    lz4_window_counter {*lz4*block_read_total* *lz4*block_write_total*} {*lz4*window_rtl_0*}
    lz4_window_address {*lz4*window_addr* *lz4*MP*} {*lz4*window_rtl_0*}
    lz4_window_state {*lz4*state* *lz4*LL* *lz4*ML*} {*lz4*window_rtl_0*}
    vga_root {*vga* *|PoC_V* *|PoC_VS*} {*Add17* *PoC_px_frameskip*}
    root_consumers {*Add17*} {}
    crt_hb {*vga*hb*} {*u_vsize*packed_ram*}
    crt_wcol {*u_vsize*wcol*} {*u_vsize*packed_ram*}
    crt_advance {*u_vsize*advance_rows*} {*u_vsize*packed_ram*}
}
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
foreach handle [list $manifest $filters $endpoints $errors] {close $handle}
delete_timing_netlist
project_close
