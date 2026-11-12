# Use the same timing model/constraints as the fitted counter baseline.
project_open Groovy -revision Groovy
create_timing_netlist
read_sdc
update_timing_netlist
report_timing -setup -detail full_path -npaths 30 -nworst 1 -show_routing -file output_files/crt_read_address_worst_setup.txt
report_timing -hold -detail full_path -npaths 10 -nworst 1 -show_routing -file output_files/crt_read_address_worst_hold.txt
report_ucp -file output_files/crt_read_address_unconstrained.txt
delete_timing_netlist
project_close
