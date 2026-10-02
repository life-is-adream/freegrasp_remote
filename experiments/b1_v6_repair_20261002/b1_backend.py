"""Adapter to the repository's get_prediction_result without owning API clients.

The caller configures the existing B1 model/ledger once, then passes
utils.utils.get_prediction_result and utils.eghc_router.parse_eghc_assessment.
The runner supplies the original parquet RGB and shares A for unchanged rows.
"""
import safe_policy as P

class B1Backend:
    def __init__(self, predict, parse):
        self.predict, self.parse = predict, parse

    def __call__(self, case, original_rgb, selection):
        packet = case['packet']
        P.old.assert_deployable_packet(packet)
        assessment = self.parse(case['router_output'], [v['id'] for v in packet['candidates']],
                                target_label=packet['instruction'])
        assessment = P.normalize_assessment(packet, assessment)
        route = selection['selected_route']
        frozen = {
            'route_mode': route,
            'pre_guard_route_mode': assessment.get('recommended_route'),
            'route_confidence': assessment.get('route_confidence',0),
            'target_object_id': assessment.get('target_object_id'),
            'target_label': assessment.get('target_label'),
            'target_candidates': assessment.get('target_candidates',[]),
            'target_visibility': assessment.get('target_visibility'),
            'blocking_relations': assessment.get('blocking_relations',[]),
            'ambiguity_evidence': assessment.get('ambiguity_evidence',[]),
            'route_guard_applied': route!=assessment.get('recommended_route'),
            'route_guard_reasons': selection.get('guard_reasons',[]),
            'route_guard_variant':'pathb_blk_arb_v1',
            'scene_router_version':'pathb_blk_arb_v1',
            'scene_complexity': {
                'model':'pathb_blk_arb_v1','route_mode':route,
                'recommended_route':assessment.get('recommended_route'),
                'target_visibility':assessment.get('target_visibility'),
                'target_candidates':assessment.get('target_candidates',[]),
                'blocking_relations':assessment.get('blocking_relations',[]),
                'requires_adjudication':selection.get('requires_adjudication',False),
            },
        }
        # scene and point_dir are peripheral image/point lookups in the
        # existing repository API; neither GT nor difficulty enters policy.
        outcome=self.predict(original_rgb,case['point_dir'],int(case['scene']),packet['instruction'],
                             return_metadata=True,prompt_variant='legacy',model_name='mimo-v2.5',
                             max_output_tokens=1024,mimo_retry_mode='none',
                             segmentation_variant='eghc_mask_repair_v1',routing_variant='evidence_gated_cascade',
                             feature_source='deployable_predicted',protocol_ablation='full',
                             route_guard_variant='pathb_blk_arb_v1',frozen_route_assessment=frozen,sam_backend='sam1')
        if not isinstance(outcome,dict) or 'error' in outcome or outcome.get('mask') is None:
            raise RuntimeError('B1 downstream failure; no implicit rerun')
        mask=outcome['mask']
        if hasattr(mask,'detach'):mask=mask.detach().cpu().numpy()
        return {**outcome,'mask':mask}
