# USER RUN ONLY. Targeted project queries; no assignment-name enumeration.
load_package project
load_package report
set revision [lindex $quartus(args) 0]
project_open Groovy -revision $revision
file mkdir output_files/q25
set out [open output_files/q25/effective_assignments.tsv w]
puts $out "name\tvalue"
foreach name {DEVICE FAMILY SEED LAST_QUARTUS_VERSION TIMEQUEST_MULTICORNER_ANALYSIS OPTIMIZE_MULTI_CORNER_TIMING VERILOG_MACRO QIP_FILE SDC_FILE} {
    foreach row [get_all_global_assignments -name $name] {puts $out "$name\t$row"}
}
foreach row [get_all_instance_assignments -name HPS_LOCATION] {puts $out "HPS_LOCATION\t$row"}
close $out
if {[get_global_assignment -name DEVICE] ne "5CSEBA6U23I7"} {error "Wrong device"}
if {[get_global_assignment -name SEED] ne "1"} {error "Wrong Fitter seed"}
load_report
# Export all cells, including complete warnings & RAM/resource tables.
set out [open output_files/q25/report_panels.tsv w]
puts $out "panel\trow\tcells"
foreach panel [get_report_panel_names] {
    set id [get_report_panel_id $panel]
    set count [get_number_of_rows -id $id]
    for {set row 0} {$row < $count} {incr row} {
        puts $out "$panel\t$row\t[get_report_panel_row -id $id -row $row]"
    }
}
close $out
unload_report
project_close
