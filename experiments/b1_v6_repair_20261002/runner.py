"""Executable offline regression and reusable repaired batch execution.

Run: python runner.py --source <resume8_repaired> --repo <repo> --output <new-dir>
This CLI never instantiates an API client or GPU model.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
import execution as X
import safe_policy as P

def key(c): return hashlib.sha256(c['case'].encode()).hexdigest()[:24]
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    with Path(p).open('x',encoding='utf-8') as f:
        json.dump(v,f,ensure_ascii=False,indent=2)

def build_plan(cases, artifact, parse):
    plan=[]
    for c in cases:
        packet=c['packet']
        evidence=P.collect_evidence(packet,cached=c['router_output'])
        a=parse(evidence['output'],[v['id'] for v in packet['candidates']],target_label=packet['instruction'])
        baseline=P.select_route('A',packet,a)
        for arm in 'ADE':
            choice=P.select_route(arm,packet,a,difficulty_artifact=artifact if arm=='D' else None)
            plan.append({'case_id':key(c),'arm':arm,'selection':choice,
                         'baseline_route':baseline['selected_route'],
                         'new_prediction_required':choice['selected_route']!=baseline['selected_route'],
                         'router_prompt_hit':False,'evidence_mode':'cached_router_rules'})
    return plan

def execute_plan(plan, cases, controls, images, backend=None):
    """Streaming batch executor; changed cases cannot silently use old outputs.

    backend(case, original_rgb, selection) must be an explicitly configured
    B1 adapter. Its return value uses the normal mask/reasoning schema.
    """
    bykey={key(c):c for c in cases}
    for item in plan:
        c=bykey[item['case_id']]
        predict=(lambda rgb,s: backend(c,rgb,s)) if backend else None
        yield item,X.execute_case(item['case_id'],item['arm'],item['selection'],controls,
                                 image_bytes=images.get((int(c['scene']),int(c['object'])-1,c['annotation'])),
                                 changed_predict=predict)

def regression(source, repo, output):
    import numpy as np
    source,repo,output=map(lambda p:Path(p).resolve(),(source,repo,output))
    if source in output.parents or repo in output.parents or output in (source,repo):
        raise ValueError('output must be outside source and frozen repository')
    output.mkdir(exist_ok=False)
    sys.path.insert(0,str(repo))
    from utils.eghc_router import parse_eghc_assessment
    cases=load(source/'cases.json'); ids=[key(c) for c in cases]
    if len(set(ids))!=300 or len(ids)!=300:raise ValueError('case coverage')
    paid=source.parent/'b1_v6_routing_split0_20260930_resume8'
    artifact=load(paid/'d_artifact.json')
    if load(source/'repair_seal.json')['status']!='complete':raise ValueError('repair incomplete')
    if load(paid/'seal.json')['status']!='complete':raise ValueError('predictions incomplete')
    # Newly hash all derived outputs. Prior manifests refer to old-resolution
    # masks and cannot serve as the seal for these derived artifacts.
    hashes={}
    for arm in 'ADE':
        for k in ids:
            for kind,ext in [('rows','json'),('predictions','npz')]:
                rel=f'{kind}/{arm}/{k}.{ext}';hashes[rel]=X.sha(source/rel)
    derived={'status':'complete','case_ids':ids,'source':str(source),'files':hashes,
             'repair_seal_sha256':X.sha(source/'repair_seal.json'),
             'seal_scope':'integrity snapshot after repair; not proof of historical parity'}
    X.verify_derived(source,derived)
    write(output/'derived_integrity.json',derived)
    control_manifest={'source':str(source),'baseline_kind':'explicit_frozen_repaired_A',
                      'historical_clean_equivalent':False,'files':{r:h for r,h in hashes.items() if '/A/' in r}}
    controls=X.ControlStore(source,control_manifest)
    write(output/'control_manifest.json',control_manifest)
    images=X.load_original_images(repo,cases)
    shape_counts=Counter()
    for c in cases:
        image=X.original_image(images[(int(c['scene']),int(c['object'])-1,c['annotation'])])
        shape_counts[str(image.size)]+=1
        for arm in 'ADE':
            with np.load(source/'predictions'/arm/(key(c)+'.npz'),allow_pickle=False) as f:
                X.assert_mask_shape(f['mask'],image)
    plan=build_plan(cases,artifact,parse_eghc_assessment)
    shared=[i for i in plan if not i['new_prediction_required']]
    calls=[]
    def forbidden(*args):
        calls.append(1);raise AssertionError('control must not invoke downstream')
    for item,result in execute_plan(shared,cases,controls,images,backend=forbidden):
        a,mask=controls.load(item['case_id'])
        if result['reasoning']!=a['reasoning'] or result['mask_sha256']!=X.sha(mask) or result['external_calls']!=0:
            raise AssertionError('shared control identity mismatch')
    # Real data structural gates without observing score labels.
    for c in cases:
        parsed=parse_eghc_assessment(c['router_output'],[v['id'] for v in c['packet']['candidates']],target_label=c['annotation'])
        norm=P.normalize_assessment(c['packet'],parsed)
        for arm in 'DE':
            choice=P.select_route(arm,c['packet'],parsed,difficulty_artifact=artifact if arm=='D' else None)
            base=P.select_route('A',c['packet'],parsed)['selected_route']
            if choice['selected_route']=='direct' and base!='direct' and not P.safe_direct(c['packet'],norm):
                raise AssertionError('unsafe direct demotion')
            if arm=='E' and base=='blocker_first' and choice['selected_route']!='blocker_first':
                raise AssertionError('blocker protection failed')
    write(output/'plan.json',plan)
    counts={a:Counter('requires_new_prediction' if i['new_prediction_required'] else 'shared_A' for i in plan if i['arm']==a) for a in 'ADE'}
    report={'status':'PASS','cases':300,'derived_masks_verified':900,'derived_files_hashed':len(hashes),
            'shared_predictions_checked':len(shared),'api_attempts':0,'gpu_calls':0,
            'original_rgb_shapes':dict(shape_counts),'plan_counts':counts,
            'historical_baseline_parity':'NOT_PASS_KNOWN_6_ID_DIFFERENCES',
            'baseline_policy':'explicit current repaired A; historical clean equivalence is not claimed',
            'method_status':'post_hoc_repair_not_prospectively_evaluated',
            'new_success_rate':None,'paid_started':False,'router_prompt_hit':False,
            'code_sha256':{p.name:X.sha(p) for p in Path(__file__).parent.glob('*.py')}}
    write(output/'validation.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True);parser.add_argument('--repo',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();regression(args.source,args.repo,args.output)
