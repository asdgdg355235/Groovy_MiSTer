#!/usr/bin/env python3
"""Package completed or failed builds without treating compilation as timing."""
import json,sys
from pathlib import Path
from package_reports import pack
root=Path(sys.argv[1]).resolve();code=int(sys.argv[2]);stage=sys.argv[3]
out=root/'output_files';out.mkdir(exist_ok=True)
state={'runner_exit_code':code,'last_stage':stage,'compilation_completed':stage in ('sta-export','diagnostics','audits','complete'),
       'timing_results_available':(out/'timing_closure/timing_gate.json').is_file(),
       'qualification':'Inspect timing/resource/I/O gates; tool success alone is not timing closure.'}
physical=out/'closure_diagnostics/diagnostic_status.json'
state['physical_exports_complete']=json.loads(physical.read_text()).get('export_queries_complete',False) if physical.exists() else None
state['diagnostic_assembly_failed']=(out/'diagnostic_assembly_failed.txt').exists()
(out/'build_state.json').write_text(json.dumps(state,indent=2)+'\n')
(out/'build_runner_exit_status.txt').write_text(str(code)+'\n')
pack(out,str(root)+'-reports.tar.gz')
print('Diagnostic archive:',str(root)+'-reports.tar.gz')
