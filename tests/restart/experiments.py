#!/usr/bin/env python3
"""Apply exactly one reviewed experiment to the c8d4b38 hardware sources."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE='c8d4b3897c4ed98165d3ee862cabbdd9ab9a4f17'
PROTECTED=('Groovy.qsf','Groovy.qpf','files.qip','Groovy.sdc','sys/sys_top.sdc',
 'sys/sys_top.v','rtl/CRT/crt_measured_hps.qsf','rtl/CRT/crt_address_duplication.qsf',
 'rtl/CRT/crt_packed_ram.sv','rtl/lz4.v','rtl/pll.v','rtl/pll/pll_0002.v')
CORE=('Groovy.sv','rtl/CRT/crt_vsize_fixed.sv','rtl/vga.v')
BUILD_EXCLUDE={'db','incremental_db','output_files','.git','__pycache__','old-builds','test-builds'}
def source_archive(source,revision):
 # Historical release bundles are not compilation inputs. Do not materialize
 # hundreds of MiB of unrelated binaries for every independent RTL check.
 paths=subprocess.check_output(['git','ls-tree','--name-only',revision],cwd=source,text=True).splitlines()
 paths=[p for p in paths if p not in BUILD_EXCLUDE]
 return subprocess.check_output(['git','archive',revision,'--',*paths],cwd=source)
def baseline(path):return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
def sha(data):return hashlib.sha256(data).hexdigest()
def registry():return json.loads((ROOT/'tests/timing_experiments/index.json').read_text())
def apply(root,name):
 root=Path(root).resolve()
 for path in PROTECTED+CORE:
  if (root/path).read_bytes()!=baseline(path):raise ValueError('Not the required hardware baseline: '+path)
 if name in ('baseline','candidate'):return {'name':'baseline','hardware_baseline':BASE,'changes':[]}
 assets=root/'tests/timing_experiments' if (root/'tests/timing_experiments/index.json').exists() else ROOT/'tests/timing_experiments'
 spec=json.loads((assets/'index.json').read_text())[name]; patch=assets/spec['patch']
 if sha(patch.read_bytes())!=spec['patch_sha256']:raise ValueError('Patch digest mismatch')
 subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
 subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 if sha((root/spec['path']).read_bytes())!=spec['result_sha256']:raise ValueError('Experiment result digest mismatch')
 return dict(spec,name=name,hardware_baseline=BASE)
