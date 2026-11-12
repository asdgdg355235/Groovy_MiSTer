load_package atoms
project_open Groovy -revision Groovy
set stage [lindex $quartus(args) 0]
if {$stage ni {map cmp}} {error "Expected map or cmp"}
read_atom_netlist -type $stage
set out [open output_files/crt_local_drivers_${stage}.tsv w]
puts $out "kind\tnode_id\tname\tport\tfanout_or_index\tsource_id\tsource_name\tsource_fanout"
set local_nodes 0
array set fanout_count {}
array set source_name {}
foreach_in_collection node [get_atom_nodes] {
    set name [get_atom_node_info -node $node -key name]
    if {[string first "u_vsize" $name] < 0 && [string first "crt_read_" $name] < 0} {continue}
    set local [expr {[string first "local_ra_" $name] >= 0 || [string first "crt_read_" $name] >= 0}]
    if {$local} {incr local_nodes}
    foreach port [get_atom_oports -node $node] {
        set fo [get_atom_port_info -node $node -type oport -port_id $port -key fanout]
        if {$local || [string first "LessThan13" $name] >= 0 || [llength $fo] >= 1000} {
            set pn [get_atom_port_info -node $node -type oport -port_id $port -key type]
            puts $out "DRIVER\t$node\t$name\t$pn\t[llength $fo]"
        }
    }
    # Export the actual upstream sources of retained read-control copies.
    if {$local} {
        foreach input_port [get_atom_iports -node $node] {
            set fi [get_atom_port_info -node $node -type iport -port_id $input_port -key fanin]
            if {[llength $fi] < 2} {continue}
            lassign $fi src op
            set pn [get_atom_port_info -node $node -type iport -port_id $input_port -key type]
            set sn [get_atom_node_info -node $src -key name]
            set n [llength [get_atom_port_info -node $src -type oport -port_id $op -key fanout]]
            puts $out "READ_CONTROL_EDGE\t$node\t$name\t$pn\t-\t$src\t$sn\t$n"
        }
    }
    if {[string first "packed_ram" $name] < 0} {continue}
    foreach port [get_atom_iports -node $node] {
        set pn [get_atom_port_info -node $node -type iport -port_id $port -key type]
        if {![string match *ADDR* $pn]} {continue}
        set fi [get_atom_port_info -node $node -type iport -port_id $port -key fanin]
        if {[llength $fi] < 2} {continue}
        set src [lindex $fi 0]
        set op [lindex $fi 1]
        if {![info exists source_name($src)]} {set source_name($src) [get_atom_node_info -node $src -key name]}
        set key "$src,$op"
        if {![info exists fanout_count($key)]} {
            set fanout_count($key) [llength [get_atom_port_info -node $src -type oport -port_id $op -key fanout]]
        }
        set sn $source_name($src)
        set n $fanout_count($key)
        set ix [get_atom_port_info -node $node -type iport -port_id $port -key literal_index]
        puts $out "RAM_ADDRESS\t$node\t$name\t$pn\t$ix\t$src\t$sn\t$n"
    }
}
puts $out "LOCAL_NODE_COUNT\t$local_nodes"
close $out
project_close
