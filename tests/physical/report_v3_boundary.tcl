# USER RUN ONLY against a copied R0 native database. Never compiles or fits.
# The atom/project interfaces are the same adapters used in the reviewed R0
# exports. Source location is not represented as original-register ancestry.
source [file join [file dirname [info script]] common.tcl]
set mode [lindex $quartus(args) 0]
if {![info exists ::env(R0_PHYS_EXPORT_DIR)]} {error "Fresh V3 export destination required"}
set dir $::env(R0_PHYS_EXPORT_DIR)
file mkdir $dir
if {$mode eq "support"} {
    # Isolate one explicitly opted-in name query in its own quartus_sh process.
    # Never call get_all_assignment_names: it previously caused native PJC failure.
    if {![info exists ::env(V3_SINGLE_ASSIGNMENT_QUERY)] || $::env(V3_SINGLE_ASSIGNMENT_QUERY) ne "1"} {
        error "V3_SINGLE_ASSIGNMENT_QUERY=1 required for optional single-name metadata query"
    }
    set name [lindex $quartus(args) 1]
    if {$name ni {ADV_NETLIST_OPT_ALLOWED PHYSICAL_SYNTHESIS_REGISTER_RETIMING}} {error "Unknown V3 assignment"}
    load_package project
    set out [physical::table $dir/v3_single_assignment_metadata.tsv {name native_status raw_metadata applicability}]
    if {[catch {get_assignment_name_info $name} value]} {
        physical::row $out [list $name UNVERIFIED_NATIVE_QUERY $value PENDING_INSTANCE_REGISTER_SCOPE_REVIEW]
    } else {physical::row $out [list $name OBSERVED_METADATA_ONLY $value PENDING_INSTANCE_REGISTER_SCOPE_AND_VALUE_REVIEW]}
    close $out
    return
}
if {$mode ni {map cmp}} {error "Expected map, cmp, or support NAME"}
load_package atoms
project_open Groovy -revision Groovy
read_atom_netlist -type $mode
set out [physical::table $dir/v3_boundary_ports_${mode}.tsv {stage direction node port bit peer peer_port peer_bit node_id peer_id observation}]
foreach_in_collection node [get_atom_nodes] {
    set name [get_atom_node_info -node $node -key name]
    if {![regexp {vga:vga.*(v_cnt|Add0|Add1|Add54|LessThan19)|^emu:emu\|(Add17|Add18|Mult0|PoC_px_frameskip|state\[|Decoder|WideOr|PoC_V|PoC_pll_F_K)} $name]} {continue}
    foreach ip [get_atom_iports -node $node] {
        set type [get_atom_port_info -node $node -type iport -port_id $ip -key type]
        set bit [get_atom_port_info -node $node -type iport -port_id $ip -key literal_index]
        set fi [get_atom_port_info -node $node -type iport -port_id $ip -key fanin]
        if {[llength $fi] < 2} {
            physical::row $out [list $mode INPUT_UNCONNECTED $name $type $bit "" "" "" $node "" NOT_REGISTER_ANCESTRY]
        } else {
            lassign $fi src op
            physical::row $out [list $mode INPUT $name $type $bit [get_atom_node_info -node $src -key name] \
                [get_atom_port_info -node $src -type oport -port_id $op -key type] \
                [get_atom_port_info -node $src -type oport -port_id $op -key literal_index] $node $src NOT_REGISTER_ANCESTRY]
        }
    }
    foreach op [get_atom_oports -node $node] {
        set type [get_atom_port_info -node $node -type oport -port_id $op -key type]
        set bit [get_atom_port_info -node $node -type oport -port_id $op -key literal_index]
        foreach pair [get_atom_port_info -node $node -type oport -port_id $op -key fanout] {
            if {[llength $pair] != 2} {error "Unexpected native pin connection"}
            lassign $pair dst ip
            physical::row $out [list $mode OUTPUT $name $type $bit [get_atom_node_info -node $dst -key name] \
                [get_atom_port_info -node $dst -type iport -port_id $ip -key type] \
                [get_atom_port_info -node $dst -type iport -port_id $ip -key literal_index] $node $dst NOT_REGISTER_ANCESTRY]
        }
    }
}
close $out
project_close
