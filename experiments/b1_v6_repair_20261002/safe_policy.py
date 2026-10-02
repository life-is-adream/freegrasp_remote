"""Routing fixes using deployable evidence; no scores or difficulty labels."""
from copy import deepcopy
import legacy_policy as old

VERSION = 'b1-route-repair-20261002'

def numeric_id(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None

def normalize_relations(relations, visible):
    result, rejected = [], []
    for relation in relations:
        if not isinstance(relation, dict):
            rejected.append({'reason': 'non_object_relation'})
            continue
        r = deepcopy(relation)
        # subject_id -> object_id is a directed subject/object relation.
        # Do not interpret object_id as a blocker in that schema.
        if 'subject_id' in r:
            blocker = numeric_id(r['subject_id'])
            target = numeric_id(r.get('target_id', r.get('blocked_id', r.get('object_id'))))
        else:
            blocker = numeric_id(r.get('blocker_id', r.get('object_id')))
            target = numeric_id(r.get('target_id', r.get('blocked_id')))
        if blocker not in visible or target not in visible or blocker == target:
            rejected.append({'reason': 'invalid_or_ambiguous_endpoints', 'relation': r})
            continue
        r.update(blocker_id=blocker, target_id=target)
        result.append(r)
    return result, rejected

def normalize_assessment(packet, assessment):
    old.assert_deployable_packet(packet)
    visible = {c['id'] for c in packet['candidates']}
    a = deepcopy(assessment)
    candidates, invalid = [], []
    for c in a.get('target_candidates', []):
        c = deepcopy(c)
        ident = numeric_id(c.get('object_id', c.get('id')))
        if ident not in visible or not c.get('valid', True):
            invalid.append(c)
        else:
            c.update(object_id=ident, valid=True)
            candidates.append(c)
    a['target_candidates'] = candidates
    relations = a.get('blocking_relations') or []
    a['blocking_relations'], errors = normalize_relations(relations, visible)
    a['normalization'] = {'invalid_candidates': invalid, 'rejected_relations': errors,
                          'raw_relation_count': len(relations)}
    return a

def safe_direct(packet, a):
    return (len(a['target_candidates']) == 1
            and a.get('target_visibility') == 'free_visible'
            and a['normalization']['raw_relation_count'] == 0
            and not a['normalization']['invalid_candidates']
            and not a.get('ambiguity_evidence')
            and not packet.get('duplicate_mask_conflict')
            and not a.get('duplicate_mask_conflict')
            and old._coerce_float(a.get('route_confidence')) >= old.DIRECT_CONFIDENCE)

def select_route(arm, packet, assessment, *, difficulty_artifact=None, **kwargs):
    old.assert_deployable_packet(packet)
    base = old.select_route('A', packet, assessment)
    if arm == 'A':
        return base
    a = normalize_assessment(packet, assessment)
    if arm == 'D':
        if difficulty_artifact is None:
            raise ValueError('missing frozen development artifact')
        proposed = old.select_route('D', packet, assessment, difficulty_artifact=difficulty_artifact)
        if proposed['selected_route'] == 'direct' and not safe_direct(packet, a):
            result = deepcopy(base)
            result['guard_reasons'] = ['D_direct_requires_unique_free_target_without_obstruction']
        else:
            result = deepcopy(proposed)
        result['difficulty_prediction'] = proposed.get('difficulty_prediction')
        result['proposed_route'] = proposed['selected_route']
        result['mapping_quality'] = 'historical_frequency_mapping_not_optimal_route_labels'
    elif arm == 'E':
        # Preserve blockers even when target identity is ambiguous. Missing
        # endpoints are unknown evidence, never evidence of a free target.
        uncertain = (len(a['target_candidates']) != 1 or bool(a.get('ambiguity_evidence'))
                     or bool(a['normalization']['rejected_relations'])
                     or bool(a['normalization']['invalid_candidates']))
        if base['selected_route'] == 'blocker_first':
            result = deepcopy(base)
            result['guard_reasons'] = ['E_preserve_existing_blocker_route']
        elif uncertain and base['selected_route'] != 'direct':
            result = deepcopy(base)
            result['guard_reasons'] = ['E_uncertain_evidence_preserve_A']
        else:
            result = old.select_route('E', packet, a)
            if result['selected_route'] == 'direct' and not safe_direct(packet, a):
                result = deepcopy(base)
                result['guard_reasons'] = ['E_direct_gate_preserve_A']
    else:
        raise ValueError('only A/D/E supported in deployment repair')
    result.update(policy_version=VERSION, selection_source=arm+'_repaired_rule',
                  evidence_mode='cached_router_rules', router_prompt_hit=False,
                  normalization=a['normalization'])
    return result

def collect_evidence(packet, *, cached=None, live_call=None, base_prompt=None):
    """Explicit distinction between cached rules and actually sending a prompt."""
    old.assert_deployable_packet(packet)
    if cached is not None and live_call is not None:
        raise ValueError('choose cached or live evidence, not both')
    if cached is not None:
        return {'output': cached, 'router_prompt_hit': False, 'external_calls': 0}
    if live_call is None or base_prompt is None:
        raise ValueError('live E evidence requires an explicit adapter and prompt')
    prompt = old.build_e_router_prompt(base_prompt)
    output = live_call(prompt, old.sanitize_deployable_packet(packet))
    return {'output': output, 'router_prompt_hit': True, 'external_calls': 1,
            'prompt_sha256': old.canonical_hash(prompt)}
