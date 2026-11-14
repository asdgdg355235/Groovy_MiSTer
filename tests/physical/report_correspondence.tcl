# USER RUN ONLY. Read-only source/physical observations, not inferred ancestry.
source [file join [file dirname [info script]] common.tcl]
load_package project
project_open Groovy -revision Groovy
if {![info exists ::env(R0_PHYS_EXPORT_DIR)]} {error "Fresh export destination required"}
set dir $::env(R0_PHYS_EXPORT_DIR)
set out [physical::table $dir/source_correspondence.tsv {stage native_id name short_name type creator source_file status}]
set errors [physical::table $dir/correspondence_errors.tsv {stage native_id field error}]
foreach stage {pre_synthesis post_synthesis post_fitter} {
    array unset seen
    array set seen {}
    foreach pattern {*vga*v_cnt* *vga*hb* *vga*Add0* *vga*Add1* *vga*Add54* *vga*LessThan19* *Add17* *PoC_px_frameskip* *u_vsize*local_ra* *u_vsize*advance_rows* *u_vsize*dataout_reg*} {
        foreach_in_collection id [get_names -filter $pattern -observable_type $stage] {
            if {[info exists seen($id)]} {continue}
            set seen($id) 1
            set row [list $stage $id]
            set status OBSERVED_SOURCE_LOCATION_NOT_REGISTER_ANCESTRY
            foreach field {full_path short_full_path node_type creator file_location} {
                if {[catch {get_name_info -info $field -observable_type $stage $id} value]} {
                    physical::row $errors [list $stage $id $field $value]
                    set value ""
                    set status UNRESOLVED_NATIVE_QUERY
                }
                lappend row $value
            }
            physical::row $out [concat $row [list $status]]
        }
    }
}
close $out
close $errors
project_close
