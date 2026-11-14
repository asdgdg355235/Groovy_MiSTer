"""Observe address dependencies, including reviewed one-register selectors."""
from collections import defaultdict
import json
EXPECTED={(str(p),b,str(n)) for p in range(3) for b in ('even','odd') for n in range(12)}
def resolve_registered(bits,fitted,mapped):
 by_node=defaultdict(list)
 for row in fitted:by_node[row['node']].append(row)
 result=[];chains=[]
 for bit in bits:
  if bit[3]!='UNRESOLVED':result.append(bit);continue
  part,bank,n=bit[:3];token=f'packed_ram[{part}].{bank}_ram|'
  # The same actual driver must be tied to this bit on a physical RAM input
  # AND on this bank's mapped mux. Neither a bus-like name nor a prefix proves it.
  known={(r['peer'],r['peer_port'],r.get('peer_bit','')) for r in fitted if r['direction']=='INPUT' and
   r['port']=='PORTBADDR' and r['bit']==str(n) and f'.{bank}_ram|' in r['node']}
  proven={k for k in known if any(r['direction']=='INPUT' and token in r['node'] and
   (r['peer'],r['peer_port'],r.get('peer_bit',''))==k for r in mapped)}
  found=[]
  for register,inputs in by_node.items():
   data=[r for r in inputs if r['direction']=='INPUT' and r['port']=='SDATA' and
         (r['peer'],r['peer_port'],r.get('peer_bit','')) in proven]
   clocks=[r for r in inputs if r['direction']=='INPUT' and r['port']=='CLK' and r['peer']]
   if len(data)!=1 or len(clocks)!=1:continue
   consumers=[r for r in fitted if r['direction']=='INPUT' and token in r['node'] and
              'rd_mux' in r['node'] and r['peer']==register and r['peer_port']=='Q']
   for consumer in consumers:
    chain={'part':part,'bank':bank,'logical_bit':n,'stage':'post_fitter','mapped_driver':data[0]['peer'],
     'capture_register':register,'capture_port':'SDATA','clock_node':clocks[0]['peer'],'clock_port':clocks[0]['peer_port'],
     'q_port':'Q','destination':consumer['node'],'destination_port':consumer['port'],'register_crossings':1,
     'cycle_offset_when_captured':1,'cycle_equivalence_status':'PENDING_CAPTURE_ENABLE_AND_MAPPED_FUNCTION_REVIEW'}
    chains.append(chain)
    found.append([part,bank,n,'OBSERVED_REGISTERED_HIGH_BIT',consumer['node'],consumer['port'],register,'Q',consumer['fanout'],
      'Observed mapped control -> SDATA -> Q -> mux; one register crossing. Functional capture/enable equivalence is a separate gate.'])
  result.extend(found if found else [bit])
 return result,chains

def summarize(bits,chains):
 groups=defaultdict(list)
 for r in bits:groups[tuple(map(str,r[:3]))].append(r)
 extra=set(groups)-EXPECTED;summary=[]
 for key in sorted(EXPECTED):
  group=groups.get(key,[]);statuses=sorted({r[3] for r in group})
  unresolved=not group or 'UNRESOLVED' in statuses
  evidence=[c for c in chains if tuple(map(str,(c['part'],c['bank'],c['logical_bit'])))==key]
  summary.append([*key,'UNRESOLVED' if unresolved else 'OBSERVED_DEPENDENCY',len(group),json.dumps(statuses),
    json.dumps(sorted({r[6] for r in group if r[6]})),json.dumps(evidence,sort_keys=True),
    'Missing/ambiguous dependency' if unresolved else 'Functional cycle equivalence remains separate'])
 return summary,not extra and set(groups)==EXPECTED and all(r[3]!='UNRESOLVED' for r in summary)
