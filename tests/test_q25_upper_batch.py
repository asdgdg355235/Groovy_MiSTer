"""No vendor calls. Native excerpts and explicitly synthetic split/build tests."""
import argparse
import copy
import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
from physical.upper_selection import SPECS, PREFIX, resolve, compose, audit_fit, bank_prefix, sha, reject_ignored
from physical.q25_experiments import CONTROL, request, validate_baseline, validate_v3, validate_selection, materialize, derived_assignments, Blocked
from physical.control import digest, expected_build_id, hardware_hashes, stage_inputs, write_json
from physical.diagnostics import table, logical_bits
from physical.q25_batch_compare import compare, physical_summary
from physical.run_v3_diagnostics import commands
from test_physical_experiments import timing_fixture
spec=importlib.util.spec_from_file_location('batch',ROOT/'tests/run_q25_timing_experiment_batch.py')
batch=importlib.util.module_from_spec(spec);spec.loader.exec_module(batch)

FIXTURE=ROOT/'tests/physical/fixtures/upper_selection_r0_map.tsv.gz'
with gzip.open(FIXTURE,'rt') as f:NATIVE=list(csv.DictReader(f,delimiter='\t'))


def put_rows(path,rr):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rr)


def synthetic_split(rr,resolution):
    """Test transformation only. Never a claim about a measured candidate."""
    source=resolution['source'];target=bank_prefix(resolution['part'],resolution['parity'])
    copy_node=PREFIX+resolution['copy'];selected=len(resolution['destinations']);total=resolution['map_fanout']
    out=copy.deepcopy(rr)
    for r in out:
        if r['direction']=='INPUT' and r['peer']==source:
            if r['node'].startswith(target):r.update(peer=copy_node,peer_id='SYNTHETIC_NEW_ATOM',fanout=str(selected))
            else:r['fanout']=str(total-selected)
        elif r['direction']=='OUTPUT' and r['node']==source:
            if r['peer'].startswith(target):r.update(node=copy_node,node_id='SYNTHETIC_NEW_ATOM',fanout=str(selected))
            else:r['fanout']=str(total-selected)
    return out


def baseline(root):
    """Synthetic acceptance fixture using the real immutable hardware profile."""
    root.mkdir(parents=True)
    h=hardware_hashes(ROOT,'q25');mh=sha(ROOT/'tests/physical/hardware_q25.json')
    p={'source_commit':CONTROL,'compiler_profile':'q25','experiment':{'name':'R0'},
       'hardware_hashes':h,'hardware_manifest_sha256':mh,
       'generated_input':{'path':'build_id.v','sha256':digest(expected_build_id()),'policy':'synthetic same bytes'},
       'fixture':'SYNTHETIC ONLY'}
    write_json(root/'provenance.json',p)
    (root/'crt_read_address_tool_version.txt').write_text('Version 25.1std.0 Build 1129 SC Lite Edition\n')
    write_json(root/'resource_clock_gate.json',{'resource_clock_pass':True,'m10k_used':489,'mlab_bits':491520})
    write_json(root/'q25_window_ram_gate.json',{'embedded_ram_inferred':True,'compiler_profile':'q25'})
    for phase in ['prepared','before_map','before_fit']:
        write_json(root/f'source_manifest_{phase}.json',{'source_commit':CONTROL,'experiment':{'name':'R0'},
            'files':[{'path':k,'sha256':v} for k,v in h.items()]})
    for phase in ['before_map','before_fit']:
        write_json(root/f'input_gate_{phase}.json',{'pass':True})
        write_json(root/f'project_calls_{phase}.json',{'events':[]})
    put_rows(root/'closure_diagnostics/atom_ports_map.tsv',NATIVE)
    write_json(root/'host_environment.json',{'host':'SYNTHETIC','cpu_count':1,'affinity':[0],'parallel_setting':'ALL'})
    timing_fixture(root,(-.2,-.1))
    return root


def reviewed_v3(root,b):
    """SYNTHETIC native approval to exercise the gate, never a published recipe."""
    seal=validate_baseline(b);proof=root/'V3-evidence';proof.mkdir()
    native_raw=proof/'native_metadata.txt';native_raw.write_text('SYNTHETIC ONLY, not an installed compiler observation\n')
    files={}
    for k in ['register_ancestry','clock_enable_reset_initialization','native_assignment_scope_values']:
        p=proof/(k+'.txt');p.write_text('SYNTHETIC ONLY register scope/ancestry fixture\n')
        if k=='native_assignment_scope_values':write_json(p,{'status':'supported','version':'25.1std.0','build':1129,'edition':'Lite',
            'scope':'instance','object_type':'register','name':'ADV_NETLIST_OPT_ALLOWED','accepted_values':['NEVER ALLOW'],
            'reviewed_by':'SYNTHETIC UNIT TEST','native_evidence':{'native_metadata.txt':sha(native_raw)}})
        files[k]={'file':p.name,'sha256':sha(p),'explanation':'Synthetic unit test'}
    original='emu:emu|vga:vga|v_cnt[12]';fitted=original+'_SYNTHETIC'
    table(b/'closure_diagnostics/node_inventory.tsv',['stage','name','short_name','type'],
          [['pre_synthesis',original,original,'reg'],['post_fitter',fitted,fitted,'reg']])
    recipe={'format':'q25-v3-boundary-v1','status':'reviewed','control_commit':CONTROL,'compiler_profile':'q25',
       'hardware_manifest_sha256':seal['hardware_manifest_sha256'],'generated_input_sha256':seal['generated_input_sha256'],
       'control_provenance_sha256':seal['files']['provenance.json'],'reviewed_by':'SYNTHETIC UNIT TEST',
       'mechanism':'Synthetic boundary test only','evidence':files,
       'support':{'native_25_1_lite_verified':True,'instance_register_scope_verified':True,'accepted_value_verified':True,
                  'name':'ADV_NETLIST_OPT_ALLOWED','value':'NEVER ALLOW'},
       'assignments':[{'kind':'instance','name':'ADV_NETLIST_OPT_ALLOWED','value':'NEVER ALLOW','target':original}],
       'correspondence':[{'rtl_node':original,'fitted_node':fitted,'reviewed':True,'ancestry_explanation':'SYNTHETIC'}]}
    path=root/'V3.json';write_json(path,recipe);return path


class UpperSelectors(unittest.TestCase):
    def test_actual_complete_selected_map_excerpt_both_experiments(self):
        metadata=json.loads(FIXTURE.with_name('upper_selection_r0_map.json').read_text())
        self.assertEqual(sha(FIXTURE),metadata['fixture_sha256'])
        for e,target in [('U10','1.even'),('U9','0.odd')]:
            r=resolve(NATIVE,e)
            self.assertEqual(r['map_fanout'],1400)
            self.assertEqual(r['bank_counts'][target],680)
            self.assertEqual(r['retained_other_bank_consumers'],720)
            self.assertEqual(len(r['destinations']),680)

    def test_suffixes_not_hardcoded(self):
        rr=copy.deepcopy(NATIVE)
        for r in rr:
            for k in ['node','peer']:
                r[k]=r[k].replace('local_ra_even[10]~2','renamed_upper_truth~981')
        self.assertIn('renamed_upper_truth~981',resolve(rr,'U10')['source'])

    def test_ambiguous_or_missing_logical_anchor(self):
        for missing in [False,True]:
            rr=copy.deepcopy(NATIVE)
            anchors=[r for r in rr if r['direction']=='INPUT' and r['node'].startswith(bank_prefix(2,'even')) and r['bit']=='10']
            if missing:rr=[r for r in rr if r not in anchors]
            else:anchors[0]['peer']='another_source'
            with self.assertRaisesRegex(ValueError,'anchor'):resolve(rr,'U10')

    def test_missing_outputs_reciprocal_pins_and_wrong_fanout(self):
        r=resolve(NATIVE,'U10')
        for kind in ['output','input','fanout']:
            rr=copy.deepcopy(NATIVE)
            victim=next(x for x in rr if x['direction']=='OUTPUT' and x['node']==r['source'])
            if kind=='output':rr.remove(victim)
            elif kind=='input':
                rr.remove(next(x for x in rr if x['direction']=='INPUT' and x['node']==victim['peer'] and x['port']==victim['peer_port'] and x['bit']==victim['peer_bit']))
            else:victim['fanout']='999999'
            with self.assertRaises(ValueError):resolve(rr,'U10')

    def test_noncombinational_source_and_nonmux_target_rejected(self):
        rr=copy.deepcopy(NATIVE)
        for r in rr:
            if r['direction']=='INPUT' and r['node'].startswith(bank_prefix(2,'even')) and r['bit']=='10':r['peer_port']='Q'
        with self.assertRaisesRegex(ValueError,'Unsupported source'):resolve(rr,'U10')
        rr=copy.deepcopy(NATIVE);src=resolve(rr,'U10')['source']
        for r in rr:
            if r['direction']=='OUTPUT' and r['node']==src and r['peer'].startswith(bank_prefix(1,'even')):r['peer_port']='CLK';break
        with self.assertRaises(ValueError):resolve(rr,'U10')

    def test_exact_duplicate_rows_safe_but_conflicting_records_rejected(self):
        self.assertEqual(resolve(NATIVE+[NATIVE[0]],'U10')['map_fanout'],1400)
        changed=dict(NATIVE[0]);changed['fanout']='7'
        with self.assertRaisesRegex(ValueError,'Conflicting'):resolve(NATIVE+[changed],'U10')

    def test_composition_distinct_and_conflicting_factors(self):
        a,b=resolve(NATIVE,'U10'),resolve(NATIVE,'U9')
        self.assertEqual(compose([a,b]).count('set_instance_assignment'),2)
        with self.assertRaisesRegex(ValueError,'Duplicate'):compose([a,a])
        b['destinations']=a['destinations']
        with self.assertRaisesRegex(ValueError,'Conflicting'):compose([a,b])

    def test_synthetic_fit_partition_and_invalid_shared_or_missing_copy(self):
        for e in SPECS:
            r=resolve(NATIVE,e);rr=synthetic_split(NATIVE,r)
            result=audit_fit(rr,r);self.assertTrue(result['split_verified']);self.assertEqual(result['fanout'],680)
            with self.assertRaises(ValueError):audit_fit(NATIVE,r)
            bad=copy.deepcopy(rr)
            next(x for x in bad if x['direction']=='OUTPUT' and x['node'].endswith(r['copy']))['fanout']='681'
            with self.assertRaises(ValueError):audit_fit(bad,r)

    def test_fake_physical_identity_cannot_be_a_copy(self):
        r=resolve(NATIVE,'U10');rr=synthetic_split(NATIVE,r)
        source_id=next(x['node_id'] for x in rr if x['direction']=='OUTPUT' and x['node']==r['source'])
        for x in rr:
            if x['direction']=='OUTPUT' and x['node'].endswith(r['copy']):x['node_id']=source_id
        with self.assertRaisesRegex(ValueError,'distinct native'):audit_fit(rr,r)

    def test_ignored_required_assignment_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'duplicate_fit.log').write_text('Warning (171070): missing required duplicate source\n')
            with self.assertRaises(ValueError):reject_ignored(d,[resolve(NATIVE,'U9')])

    def test_low_bit_policy_files_are_unchanged_from_control(self):
        for rel in ['tests/resolve_crt_duplicate_sources.py','tests/check_crt_duplicate_targets.py',
                    'tests/report_crt_local_drivers.tcl','rtl/CRT/crt_address_duplication.qsf']:
            original=subprocess.check_output(['git','show',CONTROL+':'+rel],cwd=ROOT)
            self.assertEqual((ROOT/rel).read_bytes(),original)

    def test_upper_copy_is_logical_bit_evidence_without_fake_mlab_pin(self):
        from physical.upper_selection import audit_fit
        r=resolve(NATIVE,'U10');rr=synthetic_split(NATIVE,r);copy=audit_fit(rr,r)
        bits=logical_bits(rr,upper_copies=[copy])
        hit=[b for b in bits if b[:3]==[1,'even',10] and b[3]=='OBSERVED_HIGH_BIT_FANOUT']
        self.assertTrue(hit);self.assertTrue(all(b[5]!='PORTBADDR' for b in hit))


class CandidateGates(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.b=baseline(self.root/'R0')

    def test_baseline_manifest_generated_inputs_and_wrong_revision_fail(self):
        validate_baseline(self.b)
        p=json.loads((self.b/'provenance.json').read_text());p['source_commit']='edfa9ed5bd98c113d028a1a659a738fae15584e9';write_json(self.b/'provenance.json',p)
        with self.assertRaisesRegex(ValueError,'original'):validate_baseline(self.b)

    def test_u10_and_u9_independent_v3_and_combined_blocked(self):
        a=request('U10',self.b);b=request('U9',self.b)
        self.assertEqual(a['factors'],['U10']);self.assertEqual(b['factors'],['U9'])
        for e in ['V3','U10_U9_V3']:
            with self.assertRaises(Blocked):request(e,self.b)

    def test_original_legacy_memory_only_outputs_use_only_sealed_reviewed_excerpt(self):
        from physical.q25_experiments import LEGACY_ATOMS_EXPORTER_SHA256
        legacy=[{k:v for k,v in r.items() if k not in ('node_id','peer_id')} for r in NATIVE if r['direction']=='INPUT']
        memory=dict(legacy[0]);memory['direction']='OUTPUT';memory['node']='legacy|memory';legacy.append(memory)
        put_rows(self.b/'closure_diagnostics/atom_ports_map.tsv',legacy)
        m=json.loads((self.b/'source_manifest_prepared.json').read_text())
        m['files'].append({'path':'tests/physical/report_atoms.tcl','sha256':LEGACY_ATOMS_EXPORTER_SHA256})
        write_json(self.b/'source_manifest_prepared.json',m)
        r=request('U10',self.b);self.assertEqual(r['baseline_upper_graph']['kind'],'actual_Q25_R0_complete_selected_port_excerpt')
        # The same partial graph with a current/unknown exporter must fail.
        m['files'][-1]['sha256']='unreviewed';write_json(self.b/'source_manifest_prepared.json',m)
        with self.assertRaises(ValueError):request('U10',self.b)

    def test_v3_complete_review_and_missing_scope_or_ancestry(self):
        p=reviewed_v3(self.root,self.b);r=validate_v3(p,self.b);self.assertEqual(len(r['assignments']),1)
        for k in ['native_25_1_lite_verified','instance_register_scope_verified','accepted_value_verified']:
            bad=copy.deepcopy(r);bad['support'][k]=False;write_json(p,bad)
            with self.assertRaises(Blocked):validate_v3(p,self.b)
        bad=copy.deepcopy(r);bad['correspondence'][0]['rtl_node']='emu:emu|Add17~5_NEW_REG5722';write_json(p,bad)
        with self.assertRaisesRegex(ValueError,'original VGA'):validate_v3(p,self.b)

    def test_v3_no_wildcard_global_factor_or_multiple_settings(self):
        p=reviewed_v3(self.root,self.b);r=json.loads(p.read_text())
        for key,value in [('target','*v_cnt*'),('kind','global'),('name','UNVERIFIED_NAME')]:
            bad=copy.deepcopy(r);bad['assignments'][0][key]=value;write_json(p,bad)
            with self.assertRaises(ValueError):validate_v3(p,self.b)

    def test_combined_direct_composition_without_rtl_or_conflicting_scope(self):
        p=reviewed_v3(self.root,self.b);r=request('U10_U9_V3',self.b,p)
        self.assertEqual(r['factors'],['U10','U9','V3']);self.assertEqual(r['source_rtl_changes'],[])
        self.assertEqual(len(r['baseline_upper_observations']),2)
        build=self.root/'combined';(build/'output_files').mkdir(parents=True);(build/'Groovy.qsf').write_text('control\n')
        materialize(build,r,self.b)
        self.assertEqual((build/'Groovy.qsf').read_text().count('source output_files/upper_address_duplication.qsf'),1)
        self.assertFalse((build/'rtl').exists())

    def test_unapproved_duplicate_not_hidden_by_stage_policy(self):
        out=self.root/'derived';out.mkdir();write_json(out/'q25_experiment.json',{})
        with self.assertRaisesRegex(ValueError,'Unapproved'):derived_assignments(out,{'events':[['instance','-name','DUPLICATE_ATOM','arbitrary']]},'before_map')

    def test_individual_branch_selection_does_not_enable_another_experiment(self):
        source=self.root/'source';(source/'tests/physical').mkdir(parents=True)
        write_json(source/'tests/physical/selected_experiment.json',{'control_commit':CONTROL,'compiler_profile':'q25','experiment':'U10','factors':['U10']})
        validate_selection(source,'U10')
        with self.assertRaises(ValueError):validate_selection(source,'U9')

    def test_native_scope_certificate_cannot_claim_unsupported_value(self):
        p=reviewed_v3(self.root,self.b);r=json.loads(p.read_text())
        native=self.root/'V3-evidence'/r['evidence']['native_assignment_scope_values']['file']
        d=json.loads(native.read_text());d['status']='unsupported';write_json(native,d)
        r['evidence']['native_assignment_scope_values']['sha256']=sha(native);write_json(p,r)
        with self.assertRaises(Blocked):validate_v3(p,self.b)

    def test_v3_supplemental_inventory_does_not_modify_sealed_control(self):
        p=reviewed_v3(self.root,self.b);r=json.loads(p.read_text())
        original=self.b/'closure_diagnostics/node_inventory.tsv'
        extra=self.root/'V3-evidence/register_inventory.tsv'
        extra.write_bytes(original.read_bytes());original.unlink()
        r['evidence']['register_inventory']={'file':extra.name,'sha256':sha(extra),'explanation':'SYNTHETIC supplemental source correspondence test'}
        write_json(p,r);self.assertEqual(validate_v3(p,self.b)['status'],'reviewed')
        extra.write_text('tampered')
        with self.assertRaises(ValueError):validate_v3(p,self.b)

    def test_v3_rejects_underscored_vendor_enum(self):
        p=reviewed_v3(self.root,self.b);r=json.loads(p.read_text())
        r['assignments'][0]['value']='NEVER_ALLOW';write_json(p,r)
        with self.assertRaises(ValueError):validate_v3(p,self.b)

    def test_v3_exporter_has_no_compile_or_unsafe_enumeration_calls(self):
        for args in [commands(ROOT),commands(ROOT,'ADV_NETLIST_OPT_ALLOWED')]:
            self.assertTrue(all(c[0] in ('quartus_cdb','quartus_sh','quartus_sta') and '-t' in c for c in args))
        tcl=(ROOT/'tests/physical/report_v3_boundary.tcl').read_text()
        self.assertNotRegex(tcl,r'(?m)^\s*get_all_assignment_names')
        script='set h [open {'+str(ROOT/'tests/physical/report_v3_boundary.tcl')+'}];set s [read $h];if {![info complete $s]} {exit 1}\n'
        subprocess.run(['tclsh'],input=script,text=True,check=True)


class BatchRunner(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.b=baseline(self.root/'R0')
        self.args=argparse.Namespace(source=ROOT,quartus_bin=Path('/NEVER_EXECUTE_VENDOR'),baseline_reports=self.b,
            experiments='V3,U9,U10',v3_recipe=None,reviews_dir=None,combined_when_qualified=True,
            combined_exploratory=False,prepare_only=False,output_root=self.root/'batch')
        self.calls=[];self.snapshots=[]

    def snapshot(self,source,dest,head):
        self.snapshots.append(dest);dest.mkdir();self.assertFalse((dest/'db').exists())

    def build(self,command,source,env,log):
        name=command[2];self.calls.append(name)
        out=Path(env['CRT_READ_BUILD_DIR'])/'output_files';out.mkdir(parents=True)
        write_json(out/'build_state.json',{'last_stage':'complete','compilation_completed':True,'physical_exports_complete':True})
        Path(log).write_text('SYNTHETIC ONLY mock compilation\n');return 4

    def comparison(self,control,candidate,dest,review):
        return {'status':'REJECTED','vectors':[],'application':{'target_gate_pass':True,'mechanism_status':'SYNTHETIC_SPLIT'}}

    def execute_batch(self):
        return batch.run_batch(self.args,self.build,self.snapshot,self.comparison,lambda _: 'SYNTHETIC_INFRASTRUCTURE')

    def test_independent_rejection_continues_in_fixed_order_and_blocks_v3(self):
        self.assertEqual(self.execute_batch(),3);self.assertEqual(self.calls,['U10','U9'])
        s=json.loads((self.args.output_root/'q25-timing-batch-summary.json').read_text())
        self.assertEqual([r['experiment'] for r in s['results']],['U10','U9','V3','U10_U9_V3'])
        self.assertEqual(len(set(self.snapshots)),2)
        for e in ['U10','U9','V3']:self.assertTrue((self.args.output_root/f'Groovy-Q25-{e}-reports.tar.gz').is_file())
        self.assertFalse((self.args.output_root/'Groovy-Q25-COMBINED-reports.tar.gz').exists())
        for suffix in ['summary.json','comparison.tsv','results.md']:self.assertTrue((self.args.output_root/('q25-timing-batch-'+suffix)).exists())

    def test_fit_failure_keeps_evidence_and_does_not_stop_u9(self):
        old=self.build
        def fail(command,source,env,log):
            code=old(command,source,env,log)
            if command[2]=='U10':
                write_json(Path(env['CRT_READ_BUILD_DIR'])/'output_files/build_state.json',{'last_stage':'fitting','compilation_completed':False});return 7
            return code
        self.build=fail
        self.assertEqual(self.execute_batch(),1);self.assertEqual(self.calls,['U10','U9'])

    def test_invalid_source_stops_only_that_candidate(self):
        from physical.q25_experiments import request as original
        def invalid(e,*args):
            if e=='U10':raise ValueError('ambiguous source')
            return original(e,*args)
        with patch.object(batch,'request',side_effect=invalid):self.assertEqual(self.execute_batch(),3)
        self.assertEqual(self.calls,['U9'])

    def test_combined_requires_independent_acceptance(self):
        self.args.v3_recipe=reviewed_v3(self.root,self.b)
        self.comparison=lambda *args:{'status':'ACCEPTED','vectors':[],'application':{'target_gate_pass':True}}
        self.assertEqual(self.execute_batch(),0);self.assertEqual(self.calls,['U10','U9','V3','U10_U9_V3'])
        self.assertTrue((self.args.output_root/'Groovy-Q25-COMBINED-reports.tar.gz').is_file())

    def test_combined_exploration_does_not_bypass_missing_v3_evidence(self):
        self.args.combined_exploratory=True
        self.assertEqual(self.execute_batch(),3);self.assertNotIn('U10_U9_V3',self.calls)

    def test_existing_output_and_unknown_names_rejected_without_build(self):
        self.args.output_root.mkdir()
        with self.assertRaisesRegex(ValueError,'new'):self.execute_batch()
        self.args.output_root=self.root/'another';self.args.experiments='U10,unknown'
        with self.assertRaisesRegex(ValueError,'unique'):self.execute_batch()
        self.assertEqual(self.calls,[])

    def test_prepare_only_has_no_build_subprocess_or_vendor_probe(self):
        self.args.experiments='U10,U9';self.args.combined_when_qualified=False;self.args.prepare_only=True
        def prepare(src,build,*args):
            (build/'output_files').mkdir(parents=True)
            (build/'output_files/no_vendor.txt').write_text('SYNTHETIC ONLY')
        with patch.object(batch,'create',side_effect=prepare),patch.object(batch,'freeze_generated'),patch.object(batch,'stage_inputs'):
            self.assertEqual(self.execute_batch(),0)
        self.assertEqual(self.calls,[])


class EightCornerComparison(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.b=baseline(self.root/'R0');self.c=self.root/'candidate'
        shutil.copytree(self.b,self.c)
        shutil.rmtree(self.c/'timing_closure');timing_fixture(self.c,(-.1,.01))
        p=json.loads((self.c/'provenance.json').read_text());p['source_commit']='SYNTHETIC_CANDIDATE';p['experiment']={'name':'U9'};write_json(self.c/'provenance.json',p)
        write_json(self.c/'q25_experiment.json',request('U9',self.b))
        write_json(self.c/'build_state.json',{'compilation_completed':True,'physical_exports_complete':True})
        write_json(self.c/'application_cmp.json',{'target_gate_pass':True,'copies':[{'experiment':'U9','split_verified':True}],
                                               'mechanism_status':'SYNTHETIC ONLY'})
        local={str(bit):[{'banks':[f'{part}.{side}']} for part in range(3) for side in ['even','odd']] for bit in range(5)}
        write_json(self.c/'crt_local_drivers_cmp.json',{'low_read_address_bits':local})
        for tool in ['quartus_sh','quartus_map','quartus_fit','quartus_asm','quartus_sta','quartus_cdb']:
            (self.c/(tool+'_version.txt')).write_text('Version 25.1std.0 Build 1129 SC Lite Edition\n')

    def compare(self,review=None):return compare(self.b,self.c,self.root/'comparison',review)

    def test_complete_distribution_without_review_is_not_promoted(self):
        r=self.compare();self.assertEqual(r['status'],'BLOCKED_REVIEW');self.assertEqual(len(r['vectors']),32)
        self.assertTrue((self.root/'comparison/endpoint_comparison.tsv').is_file())

    def test_one_corner_regression_rejects_even_with_fewer_failures(self):
        shutil.rmtree(self.c/'timing_closure');timing_fixture(self.c,{'-40':(-.25,), '0':(-.1,), '85':(-.1,), '100':(-.1,)})
        r=self.compare();self.assertEqual(r['status'],'REJECTED');self.assertTrue(r['setup_regressions'])

    def test_hold_failure_rejects(self):
        shutil.rmtree(self.c/'timing_closure');timing_fixture(self.c,(-.1,.01),hold_slack=-.001)
        r=self.compare();self.assertEqual(r['status'],'REJECTED');self.assertTrue(r['ancillary_failures'])

    def test_incomplete_corner_exports_rejected(self):
        (self.c/'timing_closure/corner_08/all_setup_endpoints.tsv').unlink()
        with self.assertRaises(ValueError):self.compare()

    def test_hardware_drift_and_missing_split_cannot_pass(self):
        p=json.loads((self.c/'provenance.json').read_text());p['hardware_hashes']['rtl/vga.v']='bad';write_json(self.c/'provenance.json',p)
        r=self.compare();self.assertEqual(r['status'],'REJECTED');self.assertIn('Hardware/compiler profile changed',r['invalid'])
        write_json(self.c/'application_cmp.json',{'target_gate_pass':False,'copies':[]})
        self.assertEqual(self.compare()['status'],'REJECTED')

    def test_false_target_improvement_review_is_blocked(self):
        evidence=self.c/'synthetic_review.txt';evidence.write_text('SYNTHETIC ONLY review\n')
        review={'candidate_provenance_sha256':sha(self.c/'provenance.json'),'control_provenance_sha256':sha(self.b/'provenance.json'),
                'reviewed_by':'SYNTHETIC UNIT TEST','mechanism_verified':True,'functional_cycles_verified':True,
                'evidence':{'synthetic_review.txt':sha(evidence)},'targeted_improvements':[{'factor':'U9','corner':'not_a_corner','control_capture':'missing','candidate_capture':'missing'}]}
        p=self.root/'review.json';write_json(p,review)
        r=self.compare(p);self.assertEqual(r['status'],'BLOCKED_REVIEW')

    def test_baseline_files_are_not_modified_by_comparison(self):
        before={p.relative_to(self.b).as_posix():sha(p) for p in self.b.rglob('*') if p.is_file()}
        self.compare()
        after={p.relative_to(self.b).as_posix():sha(p) for p in self.b.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_native_resource_and_retiming_record_summary(self):
        (self.c/'Groovy.fit.summary').write_text('SYNTHETIC ONLY\nLogic utilization (in ALMs) : 32,000 / 41,910\nTotal registers : 31,000\n')
        (self.c/'Groovy.fit.rpt').write_text('; synthetic_counter ; Retimed Register ; Synthetic physical record ;\n')
        r=physical_summary(self.c)
        self.assertEqual(r['resource_summary']['Total registers'],'31,000');self.assertEqual(r['retiming_records'],1)


if __name__=='__main__':unittest.main()
