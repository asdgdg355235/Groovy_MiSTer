#!/usr/bin/env python3
"""Summarize direct RAM-address driver identities from a Quartus atom audit."""
import csv
import json
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
banks = {}
local_nodes = None
controls = {}
qualification_drivers = []
with path.open() as source:
    for row in csv.reader(source, delimiter='\t'):
        if row[0] == 'LOCAL_NODE_COUNT':
            local_nodes = int(row[1])
        if row[0] == 'READ_CONTROL_EDGE':
            controls.setdefault(row[2], []).append({'port': row[3], 'source_id': row[5],
                                                    'source_name': row[6], 'fanout': int(row[7])})
        if row[0] == 'DRIVER' and ('LessThan13' in row[2] or 'crt_read_qual_' in row[2]):
            qualification_drivers.append({'id': row[1], 'name': row[2], 'fanout': int(row[4])})
        if row[0] != 'RAM_ADDRESS' or row[3] != 'PORTBADDR':
            continue
        match = re.search(r'packed_ram\[(\d+)\]\.(even|odd)_ram', row[2])
        if not match:
            continue
        bank = f'{match[1]}.{match[2]}'
        bit = row[4]
        entry = {'source_id': row[5], 'source_name': row[6], 'fanout': int(row[7])}
        key = entry['source_id']
        banks.setdefault(bank, {}).setdefault(bit, {})[key] = entry
if local_nodes is None:
    raise SystemExit('Audit is incomplete: missing final node count')
if len(banks) != 6:
    raise SystemExit(f'Expected six RAM address hierarchies, found {len(banks)}')
shared = {}
for bit in range(5):
    sources = {}
    for bank, bits in banks.items():
        for sid, entry in bits.get(str(bit), {}).items():
            sources.setdefault(sid, {'name': entry['source_name'], 'fanout': entry['fanout'], 'banks': []})['banks'].append(bank)
    shared[str(bit)] = list(sources.values())
print(json.dumps({'audit': str(path), 'local_named_atom_count': local_nodes,
                  'low_read_address_bits': shared, 'banks': banks,
                  'read_control_inputs': controls, 'qualification_drivers': qualification_drivers}, indent=2))
