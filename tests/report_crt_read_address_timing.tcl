# Use the same timing model/constraints as the fitted counter baseline.
project_open Groovy -revision Groovy
create_timing_netlist
read_sdc
update_timing_netlist
report_timing -setup -detail full_path -npaths 30 -nworst 1 -show_routing -file output_files/crt_read_address_worst_setup.txt
report_timing -hold -detail full_path -npaths 10 -nworst 1 -show_routing -file output_files/crt_read_address_worst_hold.txt
# Report the original source-to-memory cone even if another path is now worst.
set ce_source [get_registers {*|ce_pix}]
set ram_endpoints [get_keepers {*u_vsize*packed_ram*}]
if {[get_collection_size $ce_source] == 0 || [get_collection_size $ram_endpoints] == 0} {
    error "CRT CE/RAM timing filters did not match the compiled design"
}
report_timing -setup -from $ce_source -to $ram_endpoints -detail full_path -npaths 30 -nworst 1 -show_routing -file output_files/crt_read_address_ce_to_ram.txt
# Query each physical RAM hierarchy separately, including both M10K instances.
for {set part 0} {$part < 3} {incr part} {
    foreach bank {even odd} {
        set endpoints [get_keepers "*packed_ram?${part}?.${bank}_ram*"]
        if {[get_collection_size $endpoints] == 0} {error "Missing RAM $part/$bank"}
        report_timing -setup -to $endpoints -detail full_path -npaths 3 -nworst 1 -show_routing -file "output_files/crt_local_bank_${part}_${bank}_setup.txt"
    }
}
report_ucp -file output_files/crt_read_address_unconstrained.txt
delete_timing_netlist
project_close
