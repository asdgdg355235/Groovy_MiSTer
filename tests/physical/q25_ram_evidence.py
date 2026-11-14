#!/usr/bin/env python3
"""Static QIP check and source-backed Quartus 25 RAM inference gate. No Quartus execution."""
import argparse
import json
from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from physical.control import digest, hardware_hashes, profile_spec, write_json


def preflight(root, profile):
    root = Path(root)
    spec = profile_spec(profile)
    provenance_path = root/'output_files/provenance.json'
    experiment = json.loads(provenance_path.read_text()).get('experiment',{}).get('name','R0') if provenance_path.is_file() else 'R0'
    validated = hardware_hashes(root, profile, experiment)
    qip = root / spec['pll_qip']
    q17 = root / 'sys/pll_q17.qip'
    if not qip.is_file() or not q17.is_file():
        raise ValueError('Missing approved PLL file list')
    if profile == 'q25' and qip.read_bytes() != q17.read_bytes():
        raise ValueError('Quartus 25 PLL list differs from the validated 17 file list')
    sys_qip = (root / 'sys/sys.qip').read_text()
    if 'regexp -inline {[0-9]+} $quartus(version)' not in sys_qip or 'pll_q' not in sys_qip:
        raise ValueError('Major-version PLL selection changed')
    for line in qip.read_text().splitlines():
        if not line.strip(): continue
        if not line.startswith('set_global_assignment -name QIP_FILE'):
            raise ValueError('Unexpected PLL QIP assignment: ' + line)
    from project_assignments import capture
    expanded = capture(root, profile)
    selected_qip = ['global', '-name', 'QIP_FILE', spec['pll_qip']]
    if selected_qip not in expanded['events'] or expanded['missing_qip_files']:
        raise ValueError('Selected PLL QIP not expanded or another QIP file missing')
    result = {'compiler_profile': profile, 'manifest': spec['manifest'],
              'pll_qip': spec['pll_qip'], 'pll_sha256': validated[spec['pll_qip']],
              'hardware_files': len(validated), 'quartus_executed': False}
    out = root / 'output_files'
    if out.is_dir(): write_json(out / 'static_preflight.json', result)
    return result


def mapped(root, profile):
    root = Path(root)
    if profile != 'q25': return {'compiler_profile': profile, 'inference_gate': 'not_applicable'}
    report = root / 'Groovy.map.rpt'
    if not report.is_file(): raise ValueError('Missing actual Quartus 25 map report')
    lines = report.read_text(errors='replace').splitlines()
    candidates = [line.strip() for line in lines
                  if re.search(r'lz4.*window', line, re.I)]
    accepted = [line for line in candidates
                if re.search(r'altsyncram', line, re.I)
                and re.search(r'8192|524,?288', line)
                and re.search(r'(?:\b64\b|64-bit|524,?288)', line, re.I)]
    result = {'compiler_profile': profile, 'report': report.name,
              'report_sha256': digest(report.read_bytes()),
              'window_rows': candidates, 'accepted_rows': accepted,
              'embedded_ram_inferred': bool(accepted)}
    write_json(root / 'q25_window_ram_gate.json', result)
    if not accepted:
        raise ValueError('Q25 window RAM inference not proved by map report; inspect q25_window_ram_gate.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preflight','map'])
    parser.add_argument('root')
    parser.add_argument('--profile', choices=['q17','q25'], default='q25')
    args = parser.parse_args()
    if args.command == 'preflight': preflight(args.root, args.profile)
    else: mapped(args.root, args.profile)


if __name__ == '__main__': main()
