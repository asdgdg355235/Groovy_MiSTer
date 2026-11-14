#!/usr/bin/env python3
"""Reassemble derived R0 diagnostics offline; never changes the input archive."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tests/restart')]
from package_reports import verify_or_restore,pack
from physical.graph import sha
from physical.diagnostics import collect

def repair(archive,destination):
 archive,destination=Path(archive).resolve(),Path(destination).resolve()
 if destination.exists():raise ValueError('Derived evidence destination must be new')
 original_hash=sha(archive)
 verify_or_restore(archive,destination)
 out=destination/'output_files';old=json.loads((out/'closure_diagnostics/diagnostic_status.json').read_text())
 # Original records remain byte-identical; the corrected seal lives separately.
 status=collect(out,out/'corrected_diagnostics')
 audit={'original_archive_sha256':original_hash,'original_source_commit':json.loads((out/'provenance.json').read_text())['source_commit'],
        'original_status':old,'corrected_status':status,'quartus_executed':False,
        'scope':'Derived physical dependency accounting; functional, assignment and coverage gates remain separate.'}
 (out/'diagnostic_repair.json').write_text(json.dumps(audit,indent=2)+'\n')
 if sha(archive)!=original_hash:raise ValueError('Original archive unexpectedly changed')
 target=Path(str(destination)+'-reports.tar.gz');pack(out,target)
 print(target)
 if not status['export_queries_complete']:raise ValueError('Derived diagnostics still incomplete; archive retained')
 return audit
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('destination',type=Path);a=p.parse_args();repair(a.archive,a.destination)
