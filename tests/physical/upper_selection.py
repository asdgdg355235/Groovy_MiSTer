"""Fresh atom-graph resolution for one upper read selector. No vendor calls.

The M10K bank's logical PORTBADDR is the semantic anchor. MLAB bits 5..11
are mux controls, not invented RAM pins. Generated suffixes are never anchors.
"""
import csv
import hashlib
import json
from pathlib import Path
import re

PREFIX = 'emu:emu|crt_vsize_fixed:u_vsize|'
SPECS = {
    'U10': {'bit': 10, 'parity': 'even', 'part': 1, 'copy': 'crt_upper_1_even_bit10'},
    'U9': {'bit': 9, 'parity': 'odd', 'part': 0, 'copy': 'crt_upper_0_odd_bit9'},
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def rows(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f, delimiter='\t'))


def bank_prefix(part, parity):
    return PREFIX + f'crt_packed_ram:packed_ram[{part}].{parity}_ram|'


def bank(node):
    m = re.match(re.escape(PREFIX) + r'crt_packed_ram:packed_ram\[([012])\]\.(even|odd)_ram\|', node)
    return f'{m[1]}.{m[2]}' if m else 'outside'


def read_mux(node):
    return any(segment.split(':')[-1] == 'rd_mux' for segment in node.split('|'))


def literal(value):
    if not value or any(c in value for c in '{}\\\r\n\t*?'):
        raise ValueError('Unsafe or wildcard source identity: ' + repr(value))
    return '{' + value + '}'


def unique_ports(records):
    """Exact record repetition is safe; conflicting single-input identities are not."""
    seen = {}
    for r in records:
        key = (r['direction'], r['node'], r['port'], r['bit'], r['peer'], r['peer_port'], r['peer_bit'])
        if key in seen and seen[key] != r:
            raise ValueError('Conflicting repeated atom-port identity')
        seen[key] = r
    return list(seen.values())


def validate_connections(records, source, port, bit):
    outgoing = [r for r in records if r['direction'] == 'OUTPUT'
                and (r['node'], r['port'], r['bit']) == (source, port, bit)]
    if not outgoing: raise ValueError('Missing source output port/fanout export')
    counts = {int(r['fanout']) for r in outgoing}
    pins = {(r['peer'], r['peer_port'], r['peer_bit']) for r in outgoing}
    if len(counts) != 1 or counts != {len(pins)} or len(outgoing) != len(pins):
        raise ValueError('Incomplete or inconsistent expected fanout')
    by_input = {}
    for r in records:
        if r['direction'] != 'INPUT': continue
        key = (r['node'], r['port'], r['bit'])
        by_input.setdefault(key, set()).add((r['peer'], r['peer_port'], r['peer_bit']))
    for pin in pins:
        if by_input.get(pin) != {(source, port, bit)}:
            raise ValueError('Missing reciprocal input or conflicting source: ' + repr(pin))
    return outgoing


def resolve(records, experiment):
    if experiment not in SPECS: raise ValueError('Unknown upper-selection experiment')
    spec = SPECS[experiment]
    records = unique_ports(records)
    # Every M10K address bit must agree on one exact source and output port.
    anchors = [r for r in records if r['direction'] == 'INPUT'
               and r['node'].startswith(bank_prefix(2, spec['parity']))
               and r['port'] == 'PORTBADDR' and r['bit'] == str(spec['bit'])]
    sources = {(r['peer'], r['peer_port'], r['peer_bit']) for r in anchors}
    if len(sources) != 1: raise ValueError('Missing or ambiguous logical address anchor')
    source, output_port, output_bit = next(iter(sources))
    literal(source)
    if not source.startswith(PREFIX) or output_port not in ('COMBOUT', 'SUMOUT') or output_bit:
        raise ValueError('Unsupported source type/output port; no registers, constants or RAM outputs')
    outgoing = validate_connections(records, source, output_port, output_bit)
    groups = {}
    for r in outgoing:
        group = bank(r['peer'])
        if group not in {f'{i}.{spec["parity"]}' for i in range(3)}:
            raise ValueError('Address source has unexpected consumers outside its parity banks')
        groups.setdefault(group, []).append(r)
    if set(groups) != {f'{i}.{spec["parity"]}' for i in range(3)}:
        raise ValueError('Incomplete bank consumer partition')
    target_group = f'{spec["part"]}.{spec["parity"]}'
    target = groups[target_group]
    if any(not read_mux(r['peer']) or not re.fullmatch(r'DATA[A-Z]+', r['peer_port']) for r in target):
        raise ValueError('Unsupported target: expected upper read-mux input pins only')
    sink = bank_prefix(spec['part'], spec['parity'])
    # This is the same one-terminal-wildcard hierarchy form as the 30 measured
    # low-bit assignments. Actual pins, not that wildcard alone, prove scope.
    assignment = (f'set_instance_assignment -name DUPLICATE_ATOM {spec["copy"]}'
                  f' -from {literal(source)} -to {{{sink}*}}')
    return {'format': 'q25-upper-resolution-v1', 'experiment': experiment, **spec,
            'source': source, 'source_port': output_port, 'source_bit': output_bit,
            'source_node_ids': sorted({r.get('peer_id', '') for r in anchors}),
            'anchor_pins': [{'node': r['node'], 'port': r['port'], 'bit': r['bit']} for r in anchors],
            'map_fanout': len(outgoing), 'bank_counts': {k: len(v) for k, v in sorted(groups.items())},
            'destinations': [{'node': r['peer'], 'port': r['peer_port'], 'bit': r['peer_bit']} for r in target],
            'retained_other_bank_consumers': len(outgoing) - len(target), 'assignment': assignment}


def compose(resolutions):
    copies, pins = set(), set()
    for r in resolutions:
        if r['copy'] in copies: raise ValueError('Duplicate assignment/copy label')
        copies.add(r['copy'])
        current = {(d['node'], d['port'], d['bit']) for d in r['destinations']}
        if pins & current: raise ValueError('Conflicting destination selections')
        pins |= current
    return '# Fresh-map upper read-selection factors; no RTL or latency change.\n' + '\n'.join(r['assignment'] for r in resolutions) + '\n'


def audit_fit(records, resolution):
    """Prove the split, not an anticipated timing gain. All pins are retained."""
    records = unique_ports(records)
    label = resolution['copy']
    ports = {(r['node'], r['port'], r['bit']) for r in records
             if r['direction'] == 'OUTPUT' and r['node'].split('|')[-1] == label
             and r['port'] in ('COMBOUT', 'SUMOUT')}
    if len(ports) != 1: raise ValueError('Missing/ambiguous fitted copy; assignment not proved honored')
    source, port, bit = next(iter(ports))
    outgoing = validate_connections(records, source, port, bit)
    prefix = bank_prefix(resolution['part'], resolution['parity'])
    if any(not r['peer'].startswith(prefix) for r in outgoing):
        raise ValueError('Fitted copy drives another bank or unrelated logic')
    mux = [r for r in outgoing if read_mux(r['peer']) and re.fullmatch(r'DATA[A-Z]+', r['peer_port'])]
    if not mux: raise ValueError('Fitted copy has no observed upper mux loads')
    # Follow the still-original M10K anchor after fitting. Retiming can alter
    # fanout counts, so never demand the historical map or fit count unchanged.
    anchors = [r for r in records if r['direction'] == 'INPUT'
               and r['node'].startswith(bank_prefix(2, resolution['parity']))
               and r['port'] == 'PORTBADDR' and r['bit'] == str(resolution['bit'])]
    remaining = {(r['peer'], r['peer_port'], r['peer_bit']) for r in anchors}
    if len(remaining) != 1 or next(iter(remaining))[0] == source:
        raise ValueError('Original consumers not independently retained')
    old, old_port, old_bit = next(iter(remaining))
    original = validate_connections(records, old, old_port, old_bit)
    copy_ids = {r.get('node_id','') for r in outgoing}
    original_ids = {r.get('node_id','') for r in original}
    if len(copy_ids)!=1 or len(original_ids)!=1 or '' in copy_ids|original_ids or copy_ids & original_ids:
        raise ValueError('Copies lack distinct native physical source identities')
    if any(r['peer'].startswith(prefix) for r in original):
        raise ValueError('Selected bank still receives the shared original upper driver')
    wanted = {f'{i}.{resolution["parity"]}' for i in range(3) if i != resolution['part']}
    if {bank(r['peer']) for r in original} != wanted:
        raise ValueError('Unselected bank connectivity changed or is incomplete')
    return {'experiment': resolution['experiment'], 'copy_node': source, 'copy_port': port, 'copy_bit': bit,
            'bit': resolution['bit'], 'parity': resolution['parity'], 'part': resolution['part'],
            'fanout': len(outgoing), 'mux_pins': len(mux), 'original_source': old,
            'remaining_fanout': len(original), 'split_verified': True,
            'copy_fanin': [r for r in records if r['direction']=='INPUT' and r['node']==source],
            'original_fanin': [r for r in records if r['direction']=='INPUT' and r['node']==old],
            'timing_improvement': 'PENDING_EIGHT_CORNER_PATH_REVIEW'}


def reject_ignored(output, resolutions):
    needles = {r['copy'] for r in resolutions} | {r['source'] for r in resolutions}
    bad = re.compile(r'ignored|unsupported|not supported|does not exist|cannot apply|can.t duplicate|not found', re.I)
    for rel in ['Groovy.map.rpt', 'Groovy.fit.rpt', 'duplicate_fit.log', 'crt_read_address_compile.log']:
        path = Path(output) / rel
        if not path.exists(): continue
        previous = ''
        with path.open(errors='replace') as f:
            for n, line in enumerate(f, 1):
                context = previous + line
                if '(171070)' in line or (bad.search(context) and any(x in context for x in needles)):
                    raise ValueError(f'Ignored/unsupported required assignment: {rel}:{n}: {context.strip()}')
                previous = line
