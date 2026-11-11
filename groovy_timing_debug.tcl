project_open Groovy -revision Groovy

create_timing_netlist
read_sdc
update_timing_netlist

report_timing \
    -setup \
    -detail full_path \
    -npaths 30 \
    -nworst 1 \
    -show_routing \
    -file groovy_worst_setup.txt

delete_timing_netlist
project_close
