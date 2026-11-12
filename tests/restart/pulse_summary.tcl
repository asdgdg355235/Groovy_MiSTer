# report_min_pulse_width in Quartus 17 has no slack filter. Sorted summary
# prefixes establish a complete negative set without exporting every good check.
proc read_pulse_rows {filename} {
    set h [open $filename]; set data [read $h]; close $h
    set slacks {}
    foreach line [split $data "\n"] {
        if {[regexp {^;\s*(-?[0-9]+\.[0-9]+)\s*;} $line -> value]} {lappend slacks $value}
    }
    if {![llength $slacks]} {error "Pulse summary contains no checks"}
    if {$slacks ne [lsort -real $slacks]} {error "Pulse summary is not sorted worst first"}
    return $slacks
}
proc export_pulse_checks {directory} {
    set requested 16
    while {1} {
        report_min_pulse_width -nworst $requested -detail summary -file $directory/min_pulse_width.txt
        set slacks [read_pulse_rows $directory/min_pulse_width.txt]
        set returned [llength $slacks]
        if {$returned < $requested || [lindex $slacks end] >= 0} {break}
        set requested [expr {$requested*2}]
        if {$requested > 1073741824} {error "Unreasonable pulse result count"}
    }
    set failed 0
    foreach value $slacks {if {$value < 0} {incr failed}}
    set h [open $directory/pulse_summary.tsv w]
    puts $h "requested\treturned\tfailing\twns_ns\tlast_slack_ns\tcomplete"
    puts $h "$requested\t$returned\t$failed\t[lindex $slacks 0]\t[lindex $slacks end]\t1"
    close $h
    if {$failed > 0} {
        report_min_pulse_width -nworst $failed -detail full_path -file $directory/negative_pulse_paths.txt
    } else {
        set h [open $directory/negative_pulse_paths.txt w]; puts $h "No failing pulse or minimum-period checks."; close $h
    }
}
