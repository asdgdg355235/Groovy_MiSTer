#!/usr/bin/env python3
"""USER RUN ONLY: sequential independent Q25 experiments. Never reuses a build.

Unit tests inject mocked build/snapshot functions. --prepare-only never probes
any vendor executable. V3/combined fail closed until a reviewed recipe exists.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tests/restart')]
from physical.control import hardware_hashes, freeze_generated, stage_inputs, write_json, create
from physical.q25_experiments import CONTROL, NAMES, Blocked, request, output_root, validate_baseline
from physical.q25_batch_compare import compare
from package_reports import pack

ORDER=('U10','U9','V3')


def source_identity(source):
    source=Path(source)
    status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=source,text=True)
    if any('__pycache__/' not in r and not r.endswith('.pyc') for r in status.splitlines()):
        raise ValueError('Batch source must be clean and committed')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    subprocess.run(['git','merge-base','--is-ancestor',CONTROL,head],cwd=source,check=True)
    hardware_hashes(source,'q25')
    return head


def snapshot(source,destination,head):
    if Path(destination).exists():raise ValueError('Existing source snapshot')
    subprocess.run(['git','worktree','add','--detach',str(destination),head],cwd=source,check=True)


def invoke(command,source,env,log):
    with Path(log).open('w') as f:
        return subprocess.run(command,cwd=source,env=env,stdout=f,stderr=subprocess.STDOUT).returncode


def summary(root,results,source):
    payload={'format':'q25-timing-batch-v1','source_commit':source,'control_commit':CONTROL,
             'compiler':'Quartus Prime Lite 25.1std.0 Build 1129','results':results,
             'updated_utc':datetime.now(timezone.utc).isoformat(),
             'qualification':'No timing-closure or hardware claim follows from source delivery or compilation alone.'}
    write_json(root/'q25-timing-batch-summary.json',payload)
    fields=['experiment','status','source_commit','stage','mechanism','corner','check',
            'R0_WNS_ns','candidate_WNS_ns','R0_TNS_ns','candidate_TNS_ns','R0_failing','candidate_failing']
    with (root/'q25-timing-batch-comparison.tsv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter='\t',lineterminator='\n');w.writeheader()
        for r in results:
            common={k:r.get(k,'') for k in ('experiment','status','source_commit','stage','mechanism')}
            vectors=r.get('comparison',{}).get('vectors',[])
            for row in vectors or [{'corner':'NOT_RUN_OR_INCOMPLETE','check':'NOT_ANALYZED'}]:w.writerow({**common,**row})
    lines=['# Q25 timing experiment batch','',f'Control: `{CONTROL}`. Infrastructure: `{source}`.','',
           '| Experiment | Status | Last stage | Mechanism | Reports |','| --- | --- | --- | --- | --- |']
    for r in results:
        lines.append('| '+' | '.join(str(r.get(k,'')).replace('|','/') for k in ('experiment','status','stage','mechanism','archive'))+' |')
        if r.get('reason'):lines += ['',r['experiment']+': '+r['reason']]
    lines += ['','Each experiment has its own source snapshot & build. No fitting database is reused.',
              'V3 and the combined build remain blocked until source/register/scope evidence is approved.',
              'Read each comparison.json and complete endpoint TSV; renamed endpoints require correspondence review.']
    (root/'q25-timing-batch-results.md').write_text('\n'.join(lines)+'\n')


def run_batch(args,build_call=invoke,snapshot_call=snapshot,compare_call=compare,identity_call=source_identity):
    wanted=args.experiments.split(',')
    if not wanted or len(wanted)!=len(set(wanted)) or any(e not in ORDER for e in wanted):
        raise ValueError('Select unique U10,U9,V3 experiments')
    if args.combined_when_qualified or args.combined_exploratory:
        if set(wanted)!=set(ORDER):raise ValueError('Combined requires all three independent constituents')
    root=Path(args.output_root).resolve()
    if root.exists():raise ValueError('Output root must be new; old builds are never reused')
    source=Path(args.source).resolve();head=identity_call(source)
    if root==source or source in root.parents:raise ValueError('Batch output must be outside the checkout')
    baseline=output_root(args.baseline_reports);control=validate_baseline(baseline)
    root.mkdir(parents=True);(root/'sources').mkdir();(root/'logs').mkdir()
    write_json(root/'control_evidence_manifest.json',control)
    results=[]

    def execute(experiment,exploratory=False):
        label='COMBINED' if experiment=='U10_U9_V3' else experiment
        build=root/('Groovy-Q25-'+label);src=root/'sources'/label
        r={'experiment':experiment,'source_commit':head,'control_commit':CONTROL,
           'compiler':'25.1std.0 Build 1129 Lite','stage':'evidence-gate',
           'mechanism':'NOT_APPLIED','build':str(build),'source_snapshot':str(src),
           'status':'BLOCKED','exploratory':exploratory}
        results.append(r)
        try:
            spec=request(experiment,baseline,args.v3_recipe)
            snapshot_call(source,src,head)
            command=['bash',str(src/'tests/run_physical_timing_quartus.sh'),experiment,
                     '--profile','q25','--quartus-bin',str(args.quartus_bin),'--evidence',str(baseline)]
            if args.v3_recipe and 'V3' in spec['factors']:command += ['--overlay',str(Path(args.v3_recipe).resolve())]
            r['command']=command
            if args.prepare_only:
                create(src,build,experiment,args.v3_recipe,baseline,'q25')
                freeze_generated(build);stage_inputs(build,'before_map')
                out=build/'output_files'
                write_json(out/'build_state.json',{'runner_exit_code':0,'last_stage':'prepared-only','compilation_completed':False,
                                                'timing_results_available':False,'physical_exports_complete':False})
                pack(out,str(build)+'-reports.tar.gz')
                r.update(status='PREPARED',stage='prepared-only',runner_exit_code=0,mechanism='NOT_RUN')
            else:
                env={**os.environ,'CRT_READ_BUILD_DIR':str(build)}
                r['stage']='user-compilation'
                r['runner_exit_code']=build_call(command,src,env,root/'logs'/(label+'.log'))
                out=build/'output_files'
                state=json.loads((out/'build_state.json').read_text())
                r['stage']=state['last_stage']
                if not state.get('compilation_completed'):
                    r['status']='INVALID' if r['stage'] in ('preparation','preflight','postmap-targets','pre-fit-inputs','capabilities') else 'COMPILE_FAILED'
                    r['reason']='Compilation did not complete; logs and partial reports retained.'
                elif not state.get('physical_exports_complete'):
                    r.update(status='INVALID',reason='Physical diagnostic exports incomplete')
                else:
                    review=(Path(args.reviews_dir)/(label+'.json')) if args.reviews_dir else None
                    review=review if review and review.is_file() else None
                    r['comparison']=compare_call(baseline,out,out/'batch_comparison',review)
                    r['status']=r['comparison']['status']
                    r['mechanism']=r['comparison'].get('application',{}).get('mechanism_status','PENDING_REVIEW')
                # Keep comparison and all failure evidence in the same lossless archive.
                if out.exists():pack(out,str(build)+'-reports.tar.gz')
        except Blocked as error:
            r.update(status='BLOCKED',reason=str(error))
        except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:
            r.update(status='INVALID',reason=str(error))
        finally:
            # Evidence-gate failures also get a diagnostic package. The combined
            # archive, however, is created only after an actual build/preparation.
            if build.exists() or experiment!='U10_U9_V3':
                out=build/'output_files';out.mkdir(parents=True,exist_ok=True)
                write_json(out/'batch_result.json',r)
                write_json(out/'control_evidence_manifest.json',control)
                if (root/'logs'/(label+'.log')).is_file():shutil.copy2(root/'logs'/(label+'.log'),out/'batch_runner.log')
                pack(out,str(build)+'-reports.tar.gz')
            archive=Path(str(build)+'-reports.tar.gz')
            if archive.exists():r['archive']=str(archive)
            summary(root,results,head)
        return r

    for experiment in ORDER:
        if experiment in wanted:execute(experiment)
    if args.combined_when_qualified or args.combined_exploratory:
        accepted=all(r['status']=='ACCEPTED' for r in results)
        valid_exploration=(args.combined_exploratory and all(
            r.get('comparison',{}).get('application',{}).get('target_gate_pass')
            and not r.get('comparison',{}).get('invalid') for r in results))
        if accepted or valid_exploration:execute('U10_U9_V3',not accepted)
        else:
            results.append({'experiment':'U10_U9_V3','source_commit':head,'stage':'constituent-gate','mechanism':'NOT_APPLIED',
                            'status':'BLOCKED','reason':'Each factor needs valid mechanism/source evidence; default combination also requires independent acceptance.'})
            summary(root,results,head)
    # CI/callers can distinguish an incomplete fit, invalid/blocked evidence,
    # completed but rejected timing, and a successfully prepared/accepted batch.
    if any(r['status']=='COMPILE_FAILED' for r in results):return 1
    if any(r['status'] in ('INVALID','BLOCKED','BLOCKED_REVIEW') for r in results):return 3
    if any(r['status'].startswith('REJECTED') for r in results):return 4
    return 0


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT)
    p.add_argument('--quartus-bin',type=Path,default=Path(os.environ.get('QUARTUS_25_BIN','/home/taichi/altera_lite/25.1std/quartus/bin')))
    p.add_argument('--baseline-reports',required=True,type=Path,help='Restored original R0 output_files or its build directory; never modified')
    p.add_argument('--experiments',default='U10,U9,V3')
    p.add_argument('--v3-recipe',type=Path,help='Reviewed q25-v3-boundary-v1 recipe, absent means V3 blocked')
    p.add_argument('--reviews-dir',type=Path,help='Optional source/provenance-bound physical reviews named U10.json/U9.json/V3.json')
    p.add_argument('--combined-when-qualified',action='store_true')
    p.add_argument('--combined-exploratory',action='store_true',help='Explicit combined measurement despite timing rejection; never bypasses invalid mechanism/evidence')
    p.add_argument('--prepare-only',action='store_true',help='No Quartus probes or execution; V3 gates still apply')
    p.add_argument('--output-root',required=True,type=Path)
    return p


if __name__=='__main__':
    try:raise SystemExit(run_batch(parser().parse_args()))
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print('Invalid batch: '+str(error),file=sys.stderr)
        raise SystemExit(2)
