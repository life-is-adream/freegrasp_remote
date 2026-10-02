"""Prediction-only prompt intervention. No labels, difficulty or outcome inputs."""
import copy
import json

COMMON = ('Previous visual observations below are fallible hypotheses, not ground truth. '
          'Reconcile them with the image and requested description before choosing the first grasp. '
          'Keep requested target identity distinct from first-grasp identity. Preserve the original JSON schema. '
          'Use only visible candidate IDs. Record the concise supporting visual evidence in existing evidence fields. ')
TASKS = {
 'identity': 'Resolve identity first: compare plausible candidates against every category, appearance and spatial constraint in the request. Reject a candidate that violates a required constraint. Only then assess obstruction of that resolved target.',
 'occlusion': 'Check the proposed blocker-to-target relations individually. Distinguish covering or physically obstructing access from mere proximity or image-plane overlap. Identify the direct blocker if supported; explain why its removal helps the requested target. Visibility alone does not establish accessibility.',
 'conflict': 'Resolve the contradictory observations explicitly: the earlier visibility, proposed obstruction and chosen route may disagree. Recheck target identity and each proposed relation against the image. A route downgrade is not evidence that obstruction disappeared. Do not copy a prior conclusion without checking it.',
 'simple': 'Verify the target ID against the request and visible candidates. Use a concise direct visual justification and do not invent an obstruction.'
}

def evidence(route):
    sc = route.get('scene_complexity', {})
    return {'target_object_id': route.get('target_object_id'),
            'target_label': route.get('target_label'),
            'selected_route': route.get('route_mode'),
            'proposed_route': route.get('pre_guard_route_mode'),
            'visibility': sc.get('target_visibility'),
            'target_candidates': [{k: c.get(k) for k in ('object_id', 'label')} for c in sc.get('target_candidates', [])],
            'relations': [{'blocker_id': r.get('blocker_id', r.get('object_id')),
                           'target_id': r.get('target_id', r.get('blocked_id')),
                           'relation': r.get('relation', r.get('type'))} for r in sc.get('blocking_relations', [])],
            'ambiguity': list(route.get('ambiguity_evidence', []))}

def classify(ev):
    relations = ev['relations']
    conflict = (bool(relations) and ev['visibility'] == 'free_visible') or (
        ev['proposed_route'] == 'blocker_first' and ev['selected_route'] != 'blocker_first')
    if conflict:
        return 'conflict'
    if len(ev['target_candidates']) > 1 or ev['ambiguity']:
        return 'identity'
    if relations or ev['visibility'] in ('visible_but_blocked', 'mostly_hidden'):
        return 'occlusion'
    return 'simple'

def augment(messages, route, arm):
    assert arm in ('baseline', 'uniform', 'adaptive')
    if arm == 'baseline':
        return messages
    ev = evidence(route)
    instruction = ('Check target identity, obstruction and any conflicting observations in that order.'
                   if arm == 'uniform' else TASKS[classify(ev)])
    addition = '\nB1 evidence consistency check: ' + COMMON + instruction + '\nPrior observations: ' + json.dumps(ev, ensure_ascii=False)
    result = copy.deepcopy(messages)
    # Existing last user message holds the original image and task. No extra API call.
    for message in reversed(result):
        if message['role'] == 'user':
            if isinstance(message['content'], list):
                message['content'].append({'type': 'text', 'text': addition})
            else:
                message['content'] += addition
            return result
    raise ValueError('missing user message')

def tests():
    r={'route_mode':'target_first','pre_guard_route_mode':'blocker_first','target_object_id':2,
       'scene_complexity':{'target_visibility':'visible_but_blocked','blocking_relations':[{'blocker_id':1,'target_id':2,'relation':'overlap'}]}}
    assert classify(evidence(r))=='conflict'
    r['route_mode']='blocker_first';assert classify(evidence(r))=='occlusion'
    r['scene_complexity']['target_candidates']=[{'object_id':2},{'object_id':3}];assert classify(evidence(r))=='identity'
    s={'scene_complexity':{'target_visibility':'free_visible'}};assert classify(evidence(s))=='simple'
    m=[{'role':'user','content':[{'type':'text','text':'task'}]}]
    assert augment(m,r,'baseline') is m
    assert len(augment(m,r,'adaptive')[0]['content'])==2 and len(m[0]['content'])==1
    poisoned=copy.deepcopy(r);poisoned.update(difficulty='hard',gt_ids=[99],ssr_correct=1,object_id=99)
    assert evidence(poisoned)==evidence(r)
    assert 'confidence' not in json.dumps(evidence(r))
    alias=copy.deepcopy(r);alias['scene_complexity']['blocking_relations']=[{'object_id':1,'blocked_id':2,'type':'overlap'}]
    assert evidence(alias)['relations']==evidence(r)['relations']
    return 9
