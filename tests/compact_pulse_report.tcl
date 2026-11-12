# Quartus 17 report_min_pulse_width sorts worst to best, but has no slack filter.
# Expand only while every returned check fails. A nonnegative last row proves
# that all negative checks are present; a short result proves exhaustion.
proc pulse_slacks {path} {
    set h [open $path]; set text [read $h]; close $h
    if {[string match -nocase *truncat* $text]} {error "Truncated pulse report: $path"}
    set values {}
    foreach line [split $text "\n"] {
        if {[regexp {^;\s*(-?[0-9]+\.[0-9]+)\s*;} $line -> slack]} {lappend values $slack}
    }
    if {![llength $values]} {error "No pulse-width checks parsed: $path"}
    if {$values ne [lsort -real $values]} {error "Pulse report is not worst-first: $path"}
    return $values
}
proc compact_pulse_report {dir} {
    set limit 32
    while {1} {
        report_min_pulse_width -nworst $limit -detail summary -file $dir/min_pulse_width.txt
        set values [pulse_slacks $dir/min_pulse_width.txt]
        set count [llength $values]
        if {$count < $limit || [lindex $values end] >= 0} {break}
        set limit [expr {$limit*2}]
    }
    set failed 0
    foreach slack $values {if {$slack < 0} {incr failed}}
    set h [open $dir/min_pulse_coverage.tsv w]
    puts $h "exported_checks\tnegative_checks\tworst_slack_ns\tcomplete_negative_inventory"
    puts $h "$count\t$failed\t[lindex $values 0]\t1"
    close $h
    if {$failed} {
        report_min_pulse_width -nworst $failed -detail full_path -file $dir/negative_min_pulse_paths.txt
    } else {
        set h [open $dir/negative_min_pulse_paths.txt w]; puts $h "No negative minimum-pulse/period checks."; close $h
    }
}
