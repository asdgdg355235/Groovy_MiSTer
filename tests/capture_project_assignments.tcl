# Plain Tcl, not Quartus. Capture explicit/source-expanded assignment calls.
# Quartus QSF permits unquoted bus indices. Model only that spelling here.
proc unknown {cmd args} {
    if {![llength $args] && [regexp {^(\d+|\*)$} $cmd]} {return "\[$cmd\]"}
    error "Unsupported project command: $cmd $args"
}
proc emit {row} {
    set fields {}
    foreach value $row {
        binary scan [encoding convertto utf-8 $value] H* hex
        lappend fields $hex
    }
    puts [join $fields "\t"]
}
foreach kind {global instance location} {
    proc set_${kind}_assignment {args} [format {emit [linsert $args 0 %s]} $kind]
}
proc set_hps_location_assignment {args} {emit [linsert $args 0 hps_location]}
set quartus(version) 17.0.2
set quartus(qip_path) "[file dirname [file normalize [lindex $argv 0]]]/"
source [lindex $argv 0]
