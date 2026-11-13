# USER RUN ONLY: quartus_sh -t tests/physical/report_project.tcl support|map|cmp
# Quartus project 6.0/report 2.1 APIs. No assignments are set or exported.
source [file join [file dirname [info script]] common.tcl]
load_package project
set mode [lindex $quartus(args) 0]
if {$mode ni {support map cmp}} {error "Expected support, map or cmp"}
set dir output_files/closure_diagnostics
file mkdir $dir
if {$mode eq "support"} {
    set raw [open $dir/assignment_support.txt w]
    puts $raw "Installed executable: [info nameofexecutable]"
    puts $raw "Installed version: $quartus(version)"
    puts $raw "Metadata availability is not proof of individual-register applicability."
    set tab [physical::table $dir/assignment_capabilities.tsv {module scope name available metadata}]
    # Quartus Lite 25.1std.0 Build 1129 terminates inside sys_pjc when
    # get_all_assignment_names is called, even after project_open. Tcl catch
    # cannot intercept a native PJC Internal Error. R0 only needs truthful
    # discovery evidence: never guess availability or supported values.
    # A1 still requires independently verified compiler metadata before an
    # assignment can be admitted by overlays.py.
    set q25_broken_enumeration [string match {25.1std.0*} $quartus(version)]
    if {$q25_broken_enumeration} {
        puts $raw "UNVERIFIED: Quartus 25.1std.0 PJC crashes on get_all_assignment_names; enumeration deliberately not called."
        puts $raw "This does not establish that any assignment is unsupported. A1 approval requires separate native capability evidence."
    }
    foreach phase {map fit} {
        foreach scope {global instance} {
            if {$q25_broken_enumeration} {
                set names {}
                set ok 0
                set reason "UNVERIFIED: Quartus 25.1std.0 PJC assignment enumeration unavailable; scope and legal values not established"
            } else {
                set names {}
                set ok [expr {![catch {get_all_assignment_names -family {Cyclone V} -module $phase -type $scope} names]}]
                set reason "NOT_LISTED: applicability and value pending"
            }
            puts $raw "MODULE $phase SCOPE $scope LIST_OK $ok\n$names"
            foreach name {PHYSICAL_SYNTHESIS_REGISTER_RETIMING ADV_NETLIST_OPT_ALLOWED MUX_RESTRUCTURE AUTO_SHIFT_REGISTER_RECOGNITION} {
                set available [expr {$ok && [lsearch -exact $names $name] >= 0}]
                set metadata $reason
                if {$available} {
                    if {[catch {get_assignment_name_info $name} metadata]} {set available 0}
                    if {[string match -nocase {*not supported*} $metadata]} {set available 0}
                }
                puts $raw "MODULE $phase SCOPE $scope NAME $name AVAILABLE $available\n$metadata"
                physical::row $tab [list $phase $scope $name $available $metadata]
            }
        }
    }
    close $tab
    close $raw
    return
}
project_open Groovy -revision Groovy
set stages {post_fitter}
if {$mode eq "map"} {set stages {pre_synthesis post_synthesis}}
set path $dir/node_inventory.tsv
if {$mode eq "map"} {
    set inv [physical::table $path {stage name short_name type creator source_file query_status}]
} else {set inv [open $path a]}
set errors [physical::table $dir/project_query_errors_${mode}.tsv {stage node field error}]
foreach stage $stages {
    # Complete identity inventory. Numeric IDs are build-local and never overlay targets.
    foreach_in_collection id [get_names -filter * -observable_type $stage] {
        set fields [list $stage]
        set status OBSERVED
        foreach field {full_path short_full_path node_type creator file_location} {
            if {[catch {get_name_info -info $field -observable_type $stage $id} value]} {
                physical::row $errors [list $stage $id $field $value]
                set value ""
                set status PARTIAL_INFO
            }
            lappend fields $value
        }
        lappend fields $status
        physical::row $inv $fields
    }
}
close $inv
close $errors
if {[file exists output_files/physical_targets.tcl]} {
    source output_files/physical_targets.tcl
    set matches [physical::table $dir/target_matches_${mode}.tsv {target stage matches names}]
    set missing 0
    foreach target $physical_targets {
        set count 0
        foreach stage $stages {
            set found {}
            foreach_in_collection id [get_names -filter [physical::exact_filter $target] -observable_type $stage] {
                set name [get_name_info -info full_path -observable_type $stage $id]
                set short [get_name_info -info short_full_path -observable_type $stage $id]
                if {$name eq $target || $short eq $target} {lappend found $name}
            }
            incr count [llength $found]
            physical::row $matches [list $target $stage [llength $found] $found]
        }
        if {$count == 0} {incr missing}
    }
    close $matches
    if {$missing} {error "INVALID EXPERIMENT: $missing physical targets did not match exact observed nodes"}
}
# Export actual report cells without guessing field meanings or stripping names.
set panels [physical::table $dir/report_panels_${mode}.tsv {panel row column value}]
load_package report
if {[catch {load_report} why]} {
    physical::row $panels [list QUERY_ERROR 0 0 $why]
} else {
    foreach panel [get_report_panel_names] {
        if {![regexp -nocase {retim|packed|netlist|physical synthesis|multiplexer|routing|congestion|fitter settings} $panel]} {continue}
        set id [get_report_panel_id $panel]
        if {[catch {get_number_of_rows -id $id} n]} {continue}
        for {set i 0} {$i < $n} {incr i} {
            set col 0
            foreach value [get_report_panel_row -id $id -row $i] {
                physical::row $panels [list $panel $i $col $value]
                incr col
            }
        }
    }
    unload_report
}
close $panels
project_close
