#!/usr/bin/env python3
"""USER RUN ONLY. This script invokes Quartus 25.1; never execute in ChatGPT Work."""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PIN = "d071948d765c426921873093b9900ed9210532e0"

def result(args, cwd=None, capture=False, env=None):
    print("+", " ".join(map(str,args)), flush=True)
    return subprocess.run(args,cwd=cwd,env=env,check=True,
        text=True,stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None)

def run_log(args, cwd, logpath, env):
    with open(logpath,"w") as log:
        proc=subprocess.Popen(args,cwd=cwd,env=env,stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,text=True,bufsize=1)
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        code=proc.wait()
    if code:raise RuntimeError(f"{args[0]} failed with exit code {code}")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full",action="store_true",help="continue through fitter and eight-corner timing after map audit")
    parser.add_argument("--quartus",default="/home/taichi/altera_lite/25.1std")
    a=parser.parse_args()
    # In a linked git worktree, .git is a pointer *file*, not a directory.
    # Query Git rather than assuming how the checkout stores its metadata.
    git_root = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if git_root.returncode or Path(git_root.stdout.strip()).resolve() != ROOT.resolve():
        raise SystemExit("Use a Git checkout or linked worktree (not a source archive)")
    if result(["git","status","--porcelain","--untracked-files=all"],ROOT,True).stdout.strip():
        raise SystemExit("Commit or clean the checkout before testing")
    result(["git","merge-base","--is-ancestor",PIN,"HEAD"],ROOT)
    if "window_prefetch_data <= window[window_prefetch_addr];" not in (ROOT/"rtl/lz4.v").read_text():
        raise SystemExit("Missing LZ4 window candidate")

    env=os.environ.copy()
    env["PATH"]=str(Path(a.quartus)/"quartus"/"bin")+os.pathsep+env.get("PATH","")
    version=result(["quartus_sh","--version"],ROOT,True,env).stdout
    if "25.1std" not in version:raise SystemExit("Wrong Quartus version: "+version)

    sha=result(["git","rev-parse","HEAD"],ROOT,True).stdout.strip()
    dest=ROOT.parent/("Groovy-q25-lz4-"+datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")+"-"+str(os.getpid()))
    if dest.exists():raise SystemExit("Build directory already exists: "+str(dest))
    dest.mkdir()
    sys.path.insert(0,str(ROOT/"tests"/"restart"))
    from experiments import source_archive,BUILD_EXCLUDE
    with tarfile.open(fileobj=io.BytesIO(source_archive(ROOT,sha))) as archive:
        members=[m for m in archive.getmembers()
                 if not any(part in BUILD_EXCLUDE for part in Path(m.name).parts)]
        archive.extractall(dest,members=members,filter="data")
    shutil.copy2(dest/"sys/pll_q17.qip",dest/"sys/pll_q25.qip")
    reports=dest/"output_files"
    reports.mkdir(exist_ok=True)
    (reports/"q25_tool_version.txt").write_text(version)
    (reports/"q25_source_commit.txt").write_text(sha+"\n")
    (reports/"q25_variant.txt").write_text("quartus25_lz4_inference\n")
    stage="pre_flow"
    code=1
    try:
        run_log(["quartus_sh","-t","sys/build_id.tcl","pre_flow","Groovy","Groovy"],
                dest,reports/"q25_pre_flow.log",env)
        if not (dest/"build_id.v").is_file():
            raise RuntimeError("Missing generated build_id.v")
        stage="analysis_synthesis"
        run_log(["quartus_map","Groovy","-c","Groovy"],dest,reports/"q25_map.log",env)
        maplog=(reports/"q25_map.log").read_text(errors="replace")
        if "Quartus Prime Analysis & Synthesis was successful" not in maplog:
            raise RuntimeError("Quartus map did not report success")
        stage="window_ram_audit"
        mapreport=(reports/"Groovy.map.rpt").read_text(errors="replace")
        lines=[row.strip() for row in mapreport.splitlines()
               if "lz4" in row.lower() and "window" in row.lower()]
        ram=[line for line in lines if "altsyncram" in line.lower()
             and ("8192" in line or "524288" in line)]
        (reports/"q25_window_ram_rows.txt").write_text("\n".join(lines)+"\n")
        (reports/"q25_window_ram_audit.json").write_text(json.dumps({
            "inferred_window_ram_rows":ram,"inferred_window_ram_evidenced":bool(ram)
        },indent=2)+"\n")
        if not ram:
            raise RuntimeError("Inferred window RAM was not established; inspect map report")
        if a.full:
            steps=[
                ("map_drivers",["quartus_cdb","-t","tests/report_crt_local_drivers.tcl","map"]),
                ("driver_json",["python3","tests/summarize_crt_local_drivers.py","output_files/crt_local_drivers_map.tsv"]),
                ("driver_resolve",["python3","tests/resolve_crt_duplicate_sources.py","output_files/crt_local_drivers_map.tsv","output_files/crt_address_duplication_resolved.qsf"]),
                ("fitter",["python3","tests/run_crt_duplicate_fit.py"]),
                ("assembler",["quartus_asm","Groovy","-c","Groovy"]),
                ("timing",["quartus_sta","Groovy","-c","Groovy"]),
                ("eight_corners",["quartus_sta","-t","tests/report_timing_closure.tcl"]),
                ("final_drivers",["quartus_cdb","-t","tests/report_crt_local_drivers.tcl","cmp"]),
                ("driver_cmp_json",["python3","tests/summarize_crt_local_drivers.py","output_files/crt_local_drivers_cmp.tsv","--require-local"]),
                ("timing_audit",["python3","tests/validate_timing_exports.py","output_files/timing_closure"]),
                ("resource_audit",["python3","tests/validate_fitted_resources.py","output_files"]),
            ]
            for stage,command in steps:
                run_log(command,dest,reports/("q25_"+stage+".log"),env)
        stage="complete"
        code=0
    except BaseException as error:
        print("FAILED:",stage,str(error),file=sys.stderr)
        code=1
    finally:
        (reports/"q25_build_state.json").write_text(json.dumps({
            "stage":stage,"exit_code":code,"source_commit":sha,
            "quartus_executed_by":"user","full_requested":a.full
        },indent=2)+"\n")
        try:
            from package_reports import pack
            pack(reports,str(dest)+"-reports.tar.gz")
            print("Diagnostic archive:",str(dest)+"-reports.tar.gz")
        except BaseException as error:
            print("Archive failed:",error,file=sys.stderr)
        print("Build directory:",dest)
    return code

if __name__=="__main__":
    raise SystemExit(main())
