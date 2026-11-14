# USER RUN ONLY: quartus_sta -t tests/physical/report_fanout.tcl
# Quartus 17 STA get_node_info/get_edge_info. Complete selected fanout graph:
# continue through combinational nodes, stop at state; never a top-N sample.
source [file join [file dirname [info script]] common.tcl]
project_open Groovy -revision Groovy
create_timing_netlist
read_sdc
update_timing_netlist
set dir output_files/closure_diagnostics
if {[info exists ::env(R0_PHYS_EXPORT_DIR)]} {set dir $::env(R0_PHYS_EXPORT_DIR)}
set out [physical::table $dir/fanout_locations.tsv {source source_type source_location destination destination_type destination_location edge_type expected_fanout edge_id source_id destination_id}]
set seeds [physical::table $dir/fanout_seeds.tsv {family node type location native_id}]
set binding [physical::table $dir/placement_binding.tsv {fitted_node footprint_source_node location status native_token query_error}]
set queue {}
array set enqueued {}
set seed_count 0
foreach {family patterns} {
    position {*u_vsize*position* *u_vsize*delay_lines* *u_vsize*advance_rows*}
    crt_address {*crt_read_* *u_vsize*local_ra_* *u_vsize*wcol* *u_vsize*group_col*}
    delta {*PoC_lz4_delta_index* *PoC_lz4_delta_FB*}
    metadata {*u_vsize*control* *u_vsize*hb_d* *dv_hs1*}
    vga {*vga*v_cnt* *vga*hb* *vga*Add0* *vga*Add1* *vga*Add54* *vga*LessThan19* *|PoC_V* *Add17* *PoC_px_frameskip*}
} {
    foreach_in_collection id [get_nodes $patterns] {
        physical::row $seeds [list $family [get_node_info -name $id] [get_node_info -type $id] [get_node_info -location $id] $id]
        incr seed_count
        if {![info exists enqueued($id)]} {set enqueued($id) 1; lappend queue $id}
    }
}
close $seeds
set count 0
set processed_count 0
array set processed {}
array set identities {}
set zero [physical::table $dir/fanout_processed_sources.tsv {source source_type source_location expected_fanout source_id}]
set aliases [physical::table $dir/fanout_native_aliases.tsv {source source_type source_location native_id first_native_id}]

for {set index 0} {$index < [llength $queue]} {incr index} {
    set src [lindex $queue $index]
    set source [get_node_info -name $src]
    set st [get_node_info -type $src]
    set sl [get_node_info -location $src]
    set identity [list $st $sl]
    if {[info exists identities($source)] && $identities($source) ne $identity} {error "Conflicting canonical identity for $source"}
    set identities($source) $identity
    if {[info exists processed($source)]} {
        physical::row $aliases [list $source $st $sl $src $processed($source)]
        continue
    }
    set processed($source) $src
    incr processed_count
    if {$st eq "pin" && [string match *crt_read_1_even_bit3* $source]} {
        if {[catch {get_cell_info -name [get_node_info -cell $src]} host]} {
            physical::row $binding [list "" $source $sl UNRESOLVED_NATIVE_BINDING $src $host]
        } else {physical::row $binding [list $host $source $sl OBSERVED $src ""]}
    }
    set edges [get_node_info -fanout_edges $src]
    physical::row $zero [list $source $st $sl [llength $edges] $src]
    foreach edge $edges {
        set dst [get_edge_info -dst $edge]
        set dt [get_node_info -type $dst]
        physical::row $out [list $source $st $sl [get_node_info -name $dst] $dt [get_node_info -location $dst] \
            [get_edge_info -delay_type $edge] [llength $edges] $edge $src $dst]
        incr count
        if {$dt ni {reg port} && ![info exists enqueued($dst)]} {
            set enqueued($dst) 1
            lappend queue $dst
        }
    }
}
close $out
close $zero
close $aliases
close $binding
set status [physical::table $dir/fanout_export_status.tsv {seeds processed_nodes edges complete scope native_visits}]
physical::row $status [list $seed_count $processed_count $count [expr {$seed_count > 0}] {All selected roots and combinational fanout until state; canonical sources processed once, zero fanout explicit.} [llength $queue]]
close $status
delete_timing_netlist
project_close
