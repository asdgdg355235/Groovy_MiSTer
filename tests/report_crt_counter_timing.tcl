# Run after full Quartus fitting; export detailed timing for the counter revision.
project_open Groovy -revision Groovy
create_timing_netlist
read_sdc
update_timing_netlist
report_timing -setup -detail full_path -npaths 30 -nworst 1 -show_routing -file output_files/crt_counter_worst_setup.txt
report_timing -hold -detail full_path -npaths 10 -nworst 1 -show_routing -file output_files/crt_counter_worst_hold.txt
delete_timing_netlist
project_close
