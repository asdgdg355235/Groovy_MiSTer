"""Reviewed one-file source variants applied only to fresh build snapshots."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def variant():
 path=Path(__file__).with_name('variants')/'V1.json'
 if not path.is_file():raise ValueError('V1 source recipe is not present on this independent branch')
 spec=json.loads(path.read_text())
 if spec['experiment']!='V1' or spec['path']!='rtl/vga.v' or spec['control_commit']!='3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a':raise ValueError('Unreviewed variant identity')
 patch=path.with_name('V1.patch')
 if hashlib.sha256(patch.read_bytes()).hexdigest()!=spec['patch_sha256']:raise ValueError('Variant patch changed')
 return spec

def apply_variant(root):
 root=Path(root);v=variant();path=root/v['path'];patch=Path(__file__).with_name('variants')/'V1.patch'
 if hashlib.sha256(path.read_bytes()).hexdigest()!=v['baseline_sha256']:raise ValueError('V1 requires untouched R0 input')
 subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
 subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
 if hashlib.sha256(path.read_bytes()).hexdigest()!=v['result_sha256']:raise ValueError('V1 source hash mismatch')
 return v
