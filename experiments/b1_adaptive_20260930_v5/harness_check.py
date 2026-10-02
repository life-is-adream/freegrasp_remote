"""Offline CPU check of the executor gate that stopped the sealed paid batch.

Drives the frozen B1 get_prediction_result with a scripted reasoning model, a
scripted adjudicator and stubbed segmentation. No network, no GPU, no writes.
It reads the sealed batch read-only (inference inputs and the recorded model
response); it never opens score_only.json, GT npz files or the GT mapping.

Scenarios
  repair_ok      : round-1 planner returns first-grasp ID 0 (visible 1-4),
                   then the frozen protocol repairs to a visible ID  -> PASS
  repair_invalid : the adjudicator keeps the plan and every round returns ID 0
                   -> the directed repair is attempted once, the final validity
                   gate is not passed and the arm stays in the denominator.

Acceptance: round-1 invalid ID is not stopped by the executor; at most one
directed repair; at most 2 paid-model calls and 1 adjudicator call per row.
"""
import argparse
import json
import os
import pathlib
import socket
import sys

REPO = pathlib.Path('/home/public/zb/FreeGrasp_code-freegrasp_codex')
DEFAULT_BATCH = pathlib.Path('/home/public/zb/freegrasp_unograsp_fusion_20260922_v1/b1_adaptive_20260929_v2')
CASE = 'c012'

PREDICTION_KWARGS = dict(
    return_metadata=True, prompt_variant='legacy', model_name='mimo-v2.5',
    max_output_tokens=1024, mimo_retry_mode='none',
    segmentation_variant='eghc_mask_repair_v1',
    routing_variant='evidence_gated_cascade', feature_source='predicted',
    protocol_ablation='full', route_guard_variant='pathb_blk_arb_v1',
    sam_backend='sam1')


class Checks:
    def __init__(self):
        self.rows = []

    def ok(self, name, condition, detail=''):
        self.rows.append({'check': name, 'pass': bool(condition), 'detail': str(detail)[:200]})
        print('%-46s %s %s' % (name, 'PASS' if condition else 'FAIL', str(detail)[:120]), flush=True)
        return bool(condition)

    @property
    def failed(self):
        return [r for r in self.rows if not r['pass']]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario', choices=('repair_ok', 'repair_invalid'))
    ap.add_argument('--batch', default=str(DEFAULT_BATCH))
    args = ap.parse_args()

    batch = pathlib.Path(args.batch)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_TELEMETRY='1', CUDA_VISIBLE_DEVICES='',
                      TOKENIZERS_PARALLELISM='false')
    sys.path.insert(0, str(REPO))

    network = []
    def deny(*_a, **_kw):
        network.append(1)
        raise AssertionError('NETWORK_ATTEMPT')
    socket.socket.connect = deny
    socket.socket.connect_ex = deny

    import numpy as np
    import torch
    from PIL import Image
    import utils.utils as U
    from utils import eghc_adjudicator as A

    c = Checks()

    rows = json.loads((batch / 'inputs.json').read_text())
    row = [r for r in rows if r['case'] == CASE][0]
    raw = json.loads((batch / 'paid' / 'r0031_response.json').read_text())
    round1 = raw['choices'][0]['message']['content']
    router_output = row['router_output']
    adjudicated = row['replay_qwen']

    plan = json.loads(round1)
    repaired = json.loads(round1)
    repaired['first_grasp_planning'] = {
        'should_grasp_target_directly': True,
        'blocking_candidates': [],
        'first_grasp_object_id': 1,
        'first_grasp_label': 'purple box',
        'mask_query': 'bottom purple box',
        'decision_rule': 'grasp_target',
    }
    repaired = json.dumps(repaired)
    repair_answer = repaired if args.scenario == 'repair_ok' else round1

    im = Image.open(row['image']).convert('RGB')
    visible = [x[0] for x in U.parse_visible_points(
        pathlib.Path(row['point_dir']) / (str(row['scene']) + '_id.txt'))[0]]
    c.ok('visible candidates are 1-4', visible == [1, 2, 3, 4], visible)

    # The assert the sealed worker used as its pre-validator.
    round1_parsed = U.process_grasping_result(round1, row['instruction'], 'full')
    c.ok('round-1 output fails the old pre-validator',
         round1_parsed.get('selected_object_id') not in visible,
         'selected_object_id=%r' % (round1_parsed.get('selected_object_id'),))
    c.ok('round-1 output needs the frozen ID repair',
         U._needs_id_repair(round1_parsed, visible))

    calls = {'model': 0, 'qwen': 0}
    def fake_model(messages, model_name, max_output_tokens):
        index = calls['model']
        calls['model'] += 1
        if index == 0:
            return router_output
        if index == 1:
            return round1
        return repair_answer
    def fake_qwen(messages, **kw):
        calls['qwen'] += 1
        if args.scenario == 'repair_invalid':
            # Non-replacing adjudication: keep the invalid plan under test.
            return json.dumps({'decision': 'keep',
                               'reason': 'offline harness: verifier keeps current plan'})
        return adjudicated

    U._call_reasoning_model = fake_model
    A.call_qwen_adjudicator = fake_qwen

    class FakeActor:
        def __init__(self, *_a, **_kw):
            pass
        def predict(self, image, query, *_a, **_kw):
            size = image.size[::-1]
            mask = torch.zeros((1, size[0], size[1]), dtype=torch.bool)
            mask[0, 4:size[0] - 4, 4:size[1] - 4] = True
            boxes = torch.tensor([[4.0, 4.0, float(size[1] - 4), float(size[0] - 4)]])
            return mask, boxes, [query], torch.tensor([[1.0]])
    U.get_langsam_actor = FakeActor

    pred = U.get_prediction_result(im, row['point_dir'], row['scene'], row['instruction'],
                                   **PREDICTION_KWARGS)
    rr = pred.get('reasoning', {})
    paid_calls = calls['model'] - 1  # first model call replays the saved router output
    c.ok('paid-model calls within 2', paid_calls <= 2, 'paid_model_calls=%d' % paid_calls)
    c.ok('adjudicator calls within 1', calls['qwen'] <= 1, 'qwen_calls=%d' % calls['qwen'])
    c.ok('no network attempt', not network)

    if args.scenario == 'repair_ok':
        c.ok('final parse_status is valid_id', rr.get('parse_status') == 'valid_id',
             'parse_status=%r' % (rr.get('parse_status'),))
        c.ok('exactly one directed repair ran', rr.get('retry_count') == 1,
             'retry_count=%r retry_reason=%r' % (rr.get('retry_count'), rr.get('retry_reason')))
        c.ok('pipeline did not raise', not pred.get('error'),
             'error=%r' % (pred.get('error'),))
        c.ok('selected ID is visible', rr.get('selected_object_id') in visible,
             'selected_object_id=%r' % (rr.get('selected_object_id'),))
    else:
        c.ok('pipeline completed without error', not pred.get('error'),
             'error=%r' % (pred.get('error'),))
        c.ok('directed ID repair was attempted once',
             rr.get('retry_count') == 1 and rr.get('retry_reason') == 'invalid_id',
             'retry_count=%r retry_reason=%r' % (rr.get('retry_count'), rr.get('retry_reason')))
        c.ok('final validity gate is not passed', rr.get('parse_status') != 'valid_id',
             'parse_status=%r' % (rr.get('parse_status'),))
        c.ok('paid-model calls within 2', paid_calls == 2, 'paid_model_calls=%d' % paid_calls)

    print(json.dumps({'scenario': args.scenario, 'case': CASE,
                      'checks': len(c.rows), 'failed': len(c.failed)}, ensure_ascii=False))
    return 1 if c.failed else 0


if __name__ == '__main__':
    sys.exit(main())