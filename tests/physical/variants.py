"""Exact reviewed V2 patch on fresh R0 hardware snapshots only."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def variant():
    directory=Path(__file__).with_name('variants');path=directory/'V2.json'
    if not path.is_file():raise ValueError('V2 source recipe missing')
    spec=json.loads(path.read_text());patch=directory/'V2.patch'
    if spec.get('experiment')!='V2' or spec.get('path')!='Groovy.sv' or spec.get('control_commit')!='3b8d1edb63f2d2fed05d23323c3ba1ae93eeed1a':
        raise ValueError('Unreviewed V2 source identity')
    if hashlib.sha256(patch.read_bytes()).hexdigest()!=spec['patch_sha256']:raise ValueError('V2 patch changed')
    evidence=Path(__file__).with_name('evidence')/'R0-PHYS-reviewed.json'
    if hashlib.sha256(evidence.read_bytes()).hexdigest()!=spec['r0_phys_review_sha256']:raise ValueError('R0 physical review changed')
    review=json.loads(evidence.read_text())
    if review['r0_source_commit']!=spec['control_commit'] or review['V2_source_scope']!='Root next-line operand only; no counter or register-control change':
        raise ValueError('Physical review does not support this source experiment')
    return spec

def apply_variant(root):
    root=Path(root);spec=variant();target=root/spec['path'];patch=Path(__file__).with_name('variants')/'V2.patch'
    if hashlib.sha256(target.read_bytes()).hexdigest()!=spec['baseline_sha256']:raise ValueError('V2 requires untouched R0 source')
    subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
    subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=spec['result_sha256']:raise ValueError('V2 result hash mismatch')
    return spec
