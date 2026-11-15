#!/usr/bin/env python3
"""USER RUN ONLY: isolated read-only V3 queries; default metadata query disabled."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tests/restart')]
from physical.q25_experiments import validate_baseline, write
from physical.control import verify_version, expected_build_id
from physical.run_r0_phys import clone_database
from physical.upper_selection import sha
from package_reports import pack


def commands(source,single=None):
    script=str(Path(source)/'tests/physical/report_v3_boundary.tcl')
    result=[['quartus_cdb','-t',script,'map'],['quartus_cdb','-t',script,'cmp']]
    if single:result.append(['quartus_sh','-t',script,'support',single])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir',type=Path,default=Path('/home/taichi/src/groovy-crt-build/Groovy-Q25-R0-postmapgate'))
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--quartus-bin',type=Path,default=Path('/home/taichi/altera_lite/25.1std/quartus/bin'))
    p.add_argument('--single-assignment-query',choices=['ADV_NETLIST_OPT_ALLOWED','PHYSICAL_SYNTHESIS_REGISTER_RETIMING'])
    p.add_argument('--prepare-only',action='store_true')
    a=p.parse_args();build=a.build_dir.resolve();out=a.output.resolve()
    if out==build or build in out.parents or out.exists() or Path(str(out)+'-reports.tar.gz').exists():raise ValueError('V3 query output must be new and outside the sealed build')
    identity=validate_baseline(build)
    out.mkdir(parents=True);plan=commands(ROOT,a.single_assignment_query)
    state={'control':identity,'commands':plan,'quartus_executed':False,'status':'prepared-only',
           'assignment_approval':False,'register_ancestry':'PENDING_REVIEW',
           'script_sha256':sha(ROOT/'tests/physical/report_v3_boundary.tcl')}
    code=0
    try:
        if not a.prepare_only:
            if (build/'build_id.v').read_bytes()!=expected_build_id():raise ValueError('Local generated input drift')
            provenance=json.loads((build/'output_files/provenance.json').read_text())
            for rel,wanted in provenance['hardware_hashes'].items():
                if rel not in ('Groovy.qsf','Groovy.qpf') and sha(build/rel)!=wanted:raise ValueError('Local hardware drift: '+rel)
            query=out.parent/(out.name+'-native-query')
            clone_database(build,query)
            state['query_snapshot']=str(query);state['quartus_executed']=True
            env={**os.environ,'R0_PHYS_EXPORT_DIR':str(out),'PHYSICAL_COMPILER_PROFILE':'q25'}
            if a.single_assignment_query:env['V3_SINGLE_ASSIGNMENT_QUERY']='1'
            for tool in sorted({c[0] for c in plan}):
                exe=(a.quartus_bin/tool).resolve()
                if a.quartus_bin.resolve().parent not in exe.parents:raise ValueError('Mixed installation')
                text=subprocess.check_output([str(exe),'--version'],text=True);verify_version(text,'q25')
                (out/(tool+'_version.txt')).write_text(text)
            for i,cmd in enumerate(plan):
                with (out/f'query_{i}.log').open('w') as f:
                    subprocess.run([str(a.quartus_bin/cmd[0]),*cmd[1:]],cwd=query,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
            state['status']='observations-exported-ancestry-and-scope-review-pending'
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        code=3;state.update(status='incomplete',error=str(error))
    finally:
        state['exit_code']=code;write(out/'v3_query_state.json',state)
        shutil.copy2(ROOT/'tests/physical/recipes/V3.blocked.json',out)
        shutil.copy2(ROOT/'tests/physical/fixtures/root_operand_r0.json',out)
        pack(out,str(out)+'-reports.tar.gz')
    return code


if __name__=='__main__':raise SystemExit(main())
