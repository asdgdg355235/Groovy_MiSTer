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
           ['quartus_cdb','-t',str(ROOT/'tests/physical/report_atoms.tcl'),'map'],
           ['quartus_cdb','-t',str(ROOT/'tests/physical/report_atoms.tcl'),'cmp'],
           ['quartus_sta','-t',str(ROOT/'tests/physical/report_fanout.tcl')],
           ['quartus_sta','-t',str(ROOT/'tests/physical/report_recovery_paths.tcl')]]
 sources={p:sha(ROOT/p) for p in ('tests/physical/report_correspondence.tcl','tests/physical/report_atoms.tcl','tests/physical/report_fanout.tcl','tests/physical/report_recovery_paths.tcl','tests/physical/common.tcl')}
 project={rel:sha(build/rel) for rel in ('Groovy.qsf','Groovy.qpf') if (build/rel).exists()}
 request={'format':'r0-phys-request-v1','r0_provenance_sha256':sha(p),'r0_provenance':provenance,'export_source_hashes':sources,
  'exporter_source_commit':exporter_commit,'project_before':project,'commands':commands,'prepare_only':prepare_only,'quartus_executed':False,
  'assignment_capabilities':'UNVERIFIED; hazardous enumeration remains disabled','legal_sites':'PENDING_NATIVE_DEVICE_AND_TARGET_REVIEW'}
 (destination/'request.json').write_text(json.dumps(request,indent=2)+'\n')
 return commands,request,reports

def clone_database(build, destination):
 import shutil
 build=Path(build).resolve();destination=Path(destination).resolve()
 if destination.exists() or build == destination or build in destination.parents:
  raise ValueError('Native query snapshot must be a new sibling outside the original build')
 # No hardlinks: native project/cache writes must not reach original inode data.
 shutil.copytree(build,destination,ignore=shutil.ignore_patterns('.git','output_files','__pycache__'),symlinks=True)
 if any(p.is_symlink() for p in destination.rglob('*')):
  raise ValueError('Native query snapshot contains symlinks; review before vendor access')
 (destination/'output_files').mkdir(exist_ok=True)

def validate_exports(destination):
 import csv
 destination=Path(destination)
 required={'atom_ports_map.tsv','atom_ports_cmp.tsv','fanout_locations.tsv',
           'fanout_processed_sources.tsv','fanout_export_status.tsv','source_correspondence.tsv',
           'correspondence_errors.tsv','recovery_paths/corners.tsv','recovery_paths/filters.tsv',
           'recovery_paths/endpoints.tsv','recovery_paths/query_errors.tsv'}
 for name in required:
  if not (destination/name).is_file():raise ValueError('Missing fresh export: '+name)
 def rows(name):
  with (destination/name).open() as stream:return list(csv.DictReader(stream,delimiter='\t'))
 corners=rows('recovery_paths/corners.tsv')
 if len(corners)!=8 or len({r['name'] for r in corners})!=8:raise ValueError('Fresh path export requires eight distinct corners')
 for name,fields in {'atom_ports_map.tsv':{'direction','node','port','peer','peer_port','node_id','peer_id'},
                     'atom_ports_cmp.tsv':{'direction','node','port','peer','peer_port','node_id','peer_id'},
                     'source_correspondence.tsv':{'stage','native_id','name','type','source_file','status'},
                     'fanout_locations.tsv':{'source','destination','edge_id','source_id','destination_id'},
                     'fanout_processed_sources.tsv':{'source','expected_fanout','source_id'}}.items():
  observed=rows(name)
  if not observed or not fields<=observed[0].keys():raise ValueError('Incomplete fresh schema/data: '+name)
 if rows('recovery_paths/query_errors.tsv'):raise ValueError('Native focused-path query failed; partial evidence retained')
 if rows('correspondence_errors.tsv'):raise ValueError('Source correspondence queries incomplete; partial evidence retained')
 filters=rows('recovery_paths/filters.tsv')
 families={'lz4_window_capture','lz4_window_counter','lz4_window_address','lz4_window_state',
           'vga_root','root_consumers','crt_hb','crt_wcol','crt_advance'}
 expected={(c['corner'],f) for c in corners for f in families}
 observed=[(r['corner'],r['family']) for r in filters]
 if set(observed)!=expected or len(observed)!=len(expected) or any(r['status']!='OBSERVED' for r in filters):
  raise ValueError('Unmatched or incomplete physical path filters')
 if not rows('recovery_paths/endpoints.tsv'):raise ValueError('Missing focused endpoint observations')

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
   snapshot=a.build_dir.resolve().parent/(a.build_dir.name+'-'+destination.name+'-native-query')
   clone_database(a.build_dir,snapshot)
   request['native_query_snapshot']=str(snapshot)
   env={**os.environ,'R0_PHYS_EXPORT_DIR':str(destination),'PHYSICAL_COMPILER_PROFILE':'q25'}
   for command in commands:
    stage=command[0];request['quartus_executed']=True
    with (destination/(str(commands.index(command))+'_'+stage+'.log')).open('w') as log:subprocess.run([str(a.quartus_bin/command[0]),*command[1:]],cwd=snapshot,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
   normalize(destination/'fanout_locations.tsv',destination,destination/'fanout_processed_sources.tsv',destination/'fanout_export_status.tsv')
   if request['project_before']!={rel:sha(a.build_dir/rel) for rel in request['project_before']}:raise ValueError('Project assignments changed during export')
   from physical.diagnostics import collect
   validate_exports(destination)
   status=collect(reports,destination/'corrected_diagnostics',raw_overrides=destination)
   if not status['export_queries_complete']:raise ValueError('Fresh physical exports failed diagnostics')
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
