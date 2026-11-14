#!/usr/bin/env python3
"""User-run export-only R0 investigation. --prepare-only never probes Quartus."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tests/restart')]
from physical.control import expected_build_id,verify_version
from physical.graph import sha,normalize
from package_reports import pack
BASE='3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a'

def prepare(build,destination,prepare_only=False):
 build=Path(build).resolve();destination=Path(destination).resolve()
 if destination.exists() or (destination.parent/'Groovy-Q25-R0-PHYS-reports.tar.gz').exists():raise ValueError('R0_PHYS destination and archive must be new')
 exporter_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=ROOT,text=True)
 dirty=[line for line in status.splitlines() if '__pycache__/' not in line and not line.endswith('.pyc')]
 if dirty:raise ValueError('Exporter checkout must be clean and committed')
 reports=build/'output_files' if (build/'output_files').is_dir() else build
 p=reports/'provenance.json';provenance=json.loads(p.read_text())
 if provenance.get('source_commit')!=BASE or provenance.get('compiler_profile')!='q25' or provenance['experiment']['name']!='R0':raise ValueError('Requires exact Q25 R0 3b8d1ed evidence')
 if provenance.get('generated_input',{}).get('sha256')!=hashlib.sha256(expected_build_id()).hexdigest():raise ValueError('Generated input differs from R0')
 verify_version((reports/'crt_read_address_tool_version.txt').read_text(),'q25')
 if not prepare_only:
  if not (build/'Groovy.qpf').is_file() or not (build/'db').is_dir():raise ValueError('Local fitted project/database required; archive alone is insufficient')
  if (build/'build_id.v').read_bytes()!=expected_build_id():raise ValueError('Local generated input drift')
  for rel,wanted in provenance['hardware_hashes'].items():
   if rel in ('Groovy.qsf','Groovy.qpf'):continue
   if sha(build/rel)!=wanted:raise ValueError('Local R0 hardware drift: '+rel)
 destination.mkdir(parents=True)
 commands=[['quartus_sh','-t',str(ROOT/'tests/physical/report_correspondence.tcl')],
           ['quartus_cdb','-t',str(ROOT/'tests/physical/report_atoms.tcl'),'cmp'],
           ['quartus_sta','-t',str(ROOT/'tests/physical/report_fanout.tcl')]]
 sources={p:sha(ROOT/p) for p in ('tests/physical/report_correspondence.tcl','tests/physical/report_atoms.tcl','tests/physical/report_fanout.tcl','tests/physical/common.tcl')}
 project={rel:sha(build/rel) for rel in ('Groovy.qsf','Groovy.qpf') if (build/rel).exists()}
 request={'format':'r0-phys-request-v1','r0_provenance_sha256':sha(p),'r0_provenance':provenance,'export_source_hashes':sources,
  'exporter_source_commit':exporter_commit,'project_before':project,'commands':commands,'prepare_only':prepare_only,'quartus_executed':False,
  'assignment_capabilities':'UNVERIFIED; hazardous enumeration remains disabled','legal_sites':'PENDING_NATIVE_DEVICE_AND_TARGET_REVIEW'}
 (destination/'request.json').write_text(json.dumps(request,indent=2)+'\n')
 return commands,request,reports

def main():
 p=argparse.ArgumentParser();p.add_argument('--build-dir',type=Path,default=Path('/home/taichi/src/groovy-crt-build/Groovy-Q25-R0-postmapgate'))
 p.add_argument('--output',required=True,type=Path);p.add_argument('--quartus-bin',type=Path,default=Path('/home/taichi/altera_lite/25.1std/quartus/bin'));p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
 commands,request,reports=prepare(a.build_dir,a.output,a.prepare_only);code=0;stage='prepared';destination=a.output.resolve()
 try:
  if not a.prepare_only:
   request['quartus_executed']=True
   stage='version-check'
   for tool in ('quartus_sh','quartus_cdb','quartus_sta'):
    executable=(a.quartus_bin/tool).resolve()
    if a.quartus_bin.resolve().parent not in executable.parents:raise ValueError('Mixed installation executable')
    text=subprocess.check_output([str(executable),'--version'],text=True);verify_version(text,'q25');(destination/(tool+'_version.txt')).write_text(text)
   env={**os.environ,'R0_PHYS_EXPORT_DIR':str(destination),'PHYSICAL_COMPILER_PROFILE':'q25'}
   for command in commands:
    stage=command[0];request['quartus_executed']=True
    with (destination/(stage+'.log')).open('w') as log:subprocess.run([str(a.quartus_bin/command[0]),*command[1:]],cwd=a.build_dir,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
   normalize(destination/'fanout_locations.tsv',destination,destination/'fanout_processed_sources.tsv',destination/'fanout_export_status.tsv')
   if request['project_before']!={rel:sha(a.build_dir/rel) for rel in request['project_before']}:raise ValueError('Project assignments changed during export')
   from physical.diagnostics import collect
   collect(reports,destination/'corrected_diagnostics')
   stage='exports-complete-mapping-review-pending'
 except BaseException as error:
  code=3;(destination/'export_failure.txt').write_text(str(error)+'\n')
 finally:
  # Reports/provenance only, never copy db or incremental_db into this diagnostic package.
  import shutil
  for name in ('provenance.json','source_manifest_prepared.json','source_manifest_before_map.json','source_manifest_before_fit.json','resource_clock_gate.json','q25_window_ram_gate.json'):
   if (reports/name).is_file():shutil.copy2(reports/name,destination/name)
  if (reports/'timing_closure').is_dir():shutil.copytree(reports/'timing_closure',destination/'timing_closure')
  state={**request,'stage':stage,'exit_code':code,'physical_mapping_review':'PENDING','legal_placement_approved':False}
  (destination/'export_state.json').write_text(json.dumps(state,indent=2)+'\n')
  pack(destination,destination.parent/'Groovy-Q25-R0-PHYS-reports.tar.gz')
 return code
if __name__=='__main__':raise SystemExit(main())
