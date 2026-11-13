# USER RUN ONLY: quartus_cdb -t tests/physical/report_atoms.tcl map|cmp
# Uses the same atoms interface already accepted by the existing 17.0.2 audit.
# Locations come from the documented STA API, not an invented atoms key.
source [file join [file dirname [info script]] common.tcl]
load_package atoms
set mode [lindex $quartus(args) 0]
if {$mode ni {map cmp}} {error "Expected map or cmp"}
project_open Groovy -revision Groovy
read_atom_netlist -type $mode
set dir output_files/closure_diagnostics
file mkdir $dir
set help [open $dir/atoms_api_help_${mode}.txt w]
foreach command {get_atom_node_info get_atom_port_info get_atom_iports get_atom_oports} {
    puts $help "COMMAND $command"
    if {[catch {$command -long_help} text]} {puts $help "PENDING/UNAVAILABLE: $text"} else {puts $help $text}
}
close $help
set out [physical::table $dir/atom_ports_${mode}.tsv {direction node port bit peer peer_port peer_bit fanout}]
foreach_in_collection node [get_atom_nodes] {
    set name [get_atom_node_info -node $node -key name]
    if {![regexp {u_vsize|PoC_lz4_delta|r_vram_in2|dv_hs|dv_vs|hdmi_dv_hs|yc_out} $name]} {continue}
    foreach port [get_atom_iports -node $node] {
        set type [get_atom_port_info -node $node -type iport -port_id $port -key type]
        set bit [get_atom_port_info -node $node -type iport -port_id $port -key literal_index]
        set fi [get_atom_port_info -node $node -type iport -port_id $port -key fanin]
        if {[llength $fi] < 2} {
            physical::row $out [list INPUT_UNCONNECTED $name $type $bit "" "" "" 0]
            continue
        }
        lassign $fi src op
        set peer [get_atom_node_info -node $src -key name]
        set pt [get_atom_port_info -node $src -type oport -port_id $op -key type]
        set ix [get_atom_port_info -node $src -type oport -port_id $op -key literal_index]
        set fanout [llength [get_atom_port_info -node $src -type oport -port_id $op -key fanout]]
        physical::row $out [list INPUT $name $type $bit $peer $pt $ix $fanout]
    }
    # Preserve every packed-memory output connection and its actual port bit.
    if {![string match *dv_hs1_rtl_0* $name]} {continue}
    foreach port [get_atom_oports -node $node] {
        set type [get_atom_port_info -node $node -type oport -port_id $port -key type]
        set bit [get_atom_port_info -node $node -type oport -port_id $port -key literal_index]
        set fanout [get_atom_port_info -node $node -type oport -port_id $port -key fanout]
        foreach pair $fanout {
            if {[llength $pair] != 2} {error "Unexpected atom fanout representation; no connections omitted"}
            lassign $pair dst ip
            physical::row $out [list OUTPUT $name $type $bit [get_atom_node_info -node $dst -key name] \
                [get_atom_port_info -node $dst -type iport -port_id $ip -key type] \
                [get_atom_port_info -node $dst -type iport -port_id $ip -key literal_index] [llength $fanout]]
        }
    }
}
close $out
project_close
