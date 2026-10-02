import io,json,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
import execution as X
import safe_policy as P
import runner
from b1_backend import B1Backend

class RepairTests(unittest.TestCase):
    def setUp(self):
        self.packet={'instruction':'the box','candidates':[{'id':1},{'id':2}]}
        self.assess={'target_candidates':[{'object_id':1,'valid':True}], 'target_object_id':1,
                     'target_visibility':'visible_but_blocked','recommended_route':'blocker_first',
                     'route_confidence':.9,'blocking_relations':[{'blocker_id':2,'target_id':1,'type':'on-top'}]}
        self.artifact={'frozen':True,'centroids':{'easy':1.5,'medium':100,'hard':200},
                       'route_map':{'easy':'direct','medium':'blocker_first','hard':'blocker_first'}}

    def test_relation_variants(self):
        for rel in [{'subject_id':2,'object_id':1,'type':'on-top'},
                    {'object_id':'2','blocked_id':'1','relation':'overlap'},
                    {'blocker_id':2,'target_id':1,'relation':'overlap'}]:
            valid,bad=P.normalize_relations([rel],{1,2})
            self.assertFalse(bad);self.assertEqual((valid[0]['blocker_id'],valid[0]['target_id']),(2,1))

    def test_invalid_ids_not_free_evidence(self):
        for rel in [{'blocker_id':2,'target_id':'red_bowl'},{'blocker_id':1,'target_id':1}, {'blocker_id':True,'target_id':2}]:
            valid,bad=P.normalize_relations([rel],{1,2})
            self.assertFalse(valid);self.assertTrue(bad)

    def test_d_cannot_override_occlusion_with_easy(self):
        result=P.select_route('D',self.packet,self.assess,difficulty_artifact=self.artifact)
        self.assertEqual(result['difficulty_prediction']['predicted_difficulty'],'easy')
        self.assertEqual(result['proposed_route'],'direct')
        self.assertEqual(result['selected_route'],'blocker_first')

    def test_e_ambiguity_does_not_remove_blocker(self):
        self.assess['target_candidates'].append({'object_id':2,'valid':True})
        self.assertEqual(P.select_route('E',self.packet,self.assess)['selected_route'],'blocker_first')

    def test_e_prompt_accounting_and_adapter(self):
        self.assertFalse(P.collect_evidence(self.packet,cached='saved')['router_prompt_hit'])
        seen=[]
        def call(prompt,packet):seen.append(prompt);return 'new'
        result=P.collect_evidence(self.packet,live_call=call,base_prompt='base')
        self.assertIn('E routing evidence contract',seen[0]);self.assertTrue(result['router_prompt_hit'])
        self.assertEqual(result['external_calls'],1)
        with self.assertRaises(ValueError):P.collect_evidence(self.packet,cached='x',live_call=call)

    def test_strict_replay_no_live_fallback(self):
        replay=X.StrictReplay([{'provider':'mimo','payload_sha256':X.canonical({'x':1}),'content':'yes'}])
        with self.assertRaises(X.ReplayMissing):replay.call('qwen',{'x':1})
        self.assertEqual(replay.call('mimo',{'x':1}),'yes')
        replay.finish()
        with self.assertRaises(X.ReplayMissing):replay.call('mimo',{'x':1})

    def test_control_preserves_timeout_id_query_and_mask(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'rows/A').mkdir(parents=True);(root/'predictions/A').mkdir(parents=True)
            row={'case':'x','selected_route':'blocker_first','mask_path':'predictions/A/k.npz',
                 'reasoning':{'selected_object_id':1,'mask_query':'white block','qwen_adjudication':{'decision':'verifier_error_keep'}}}
            (root/'rows/A/k.json').write_text(json.dumps(row))
            np.savez_compressed(root/row['mask_path'],mask=np.ones((4,4),dtype=bool))
            files={p.relative_to(root).as_posix():X.sha(p) for p in root.rglob('*') if p.is_file()}
            controls=X.ControlStore(root,{'files':files})
            for arm in 'ADE':
                r=X.execute_case('k',arm,{'selected_route':'blocker_first'},controls,changed_predict=lambda *_:self.fail('live call'))
                self.assertEqual(r['reasoning'],row['reasoning']);self.assertEqual(r['external_calls'],0)
            with self.assertRaises(X.ReplayMissing):X.execute_case('k','E',{'selected_route':'target_first'},controls)
            b=io.BytesIO();Image.new('RGB',(4,4)).save(b,format='PNG')
            calls=[]
            def adapter(image,selection):
                calls.append(image.size)
                return {'mask':np.zeros((4,4),bool),'reasoning':{'selected_object_id':2}}
            X.execute_case('k','E',{'selected_route':'target_first'},controls,image_bytes=b.getvalue(),changed_predict=adapter)
            self.assertEqual(calls,[(4,4)])
            (root/row['mask_path']).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):controls.load('k')

    def test_original_image_mask_and_full_cache_schema(self):
        image=Image.new('RGB',(12,12))
        with self.assertRaises(ValueError):X.assert_mask_shape(np.zeros((18,18)),image)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cache.npz'
            h=X.save_segmentation_cache(p,np.zeros((2,12,12),bool),np.zeros((2,4)),['a','b'],np.zeros(2))
            masks,boxes,phrases,logits=X.load_segmentation_cache(p,h)
            self.assertEqual(masks.shape,(2,12,12));self.assertEqual(phrases,['a','b']);self.assertEqual(boxes.shape,(2,4))

    def test_no_score_fields_in_policy(self):
        packet=dict(self.packet,difficulty='easy')
        with self.assertRaises(ValueError):P.select_route('E',packet,self.assess)

    def test_repository_adapter_uses_original_rgb_and_normalized_route(self):
        self.assess['blocking_relations']=[{'subject_id':2,'object_id':1,'type':'on-top'}]
        captured=[]
        def predict(image,path,scene,instruction,**kwargs):
            captured.append((image.size,kwargs))
            return {'mask':np.zeros((12,12),bool),'reasoning':{'selected_object_id':2}}
        backend=B1Backend(predict,lambda *a,**kw:self.assess)
        case={'packet':self.packet,'router_output':'cached','point_dir':'points','scene':3}
        backend(case,Image.new('RGB',(12,12)),{'selected_route':'blocker_first'})
        shape,kw=captured[0]
        self.assertEqual(shape,(12,12))
        self.assertEqual(kw['frozen_route_assessment']['blocking_relations'][0]['blocker_id'],2)
        self.assertEqual(kw['frozen_route_assessment']['route_mode'],'blocker_first')
        self.assertEqual(kw['model_name'],'mimo-v2.5')
        self.assertNotIn('difficulty',kw)

    def test_derived_integrity_rejects_mask_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);files={}
            for arm in 'ADE':
                for kind,ext in [('rows','json'),('predictions','npz')]:
                    p=root/kind/arm/('k.'+ext);p.parent.mkdir(parents=True)
                    p.write_bytes(b'fixture');files[p.relative_to(root).as_posix()]=X.sha(p)
            seal={'status':'complete','case_ids':['k'],'files':files}
            self.assertTrue(X.verify_derived(root,seal))
            (root/'predictions/E/k.npz').write_bytes(b'tampered')
            with self.assertRaises(ValueError):X.verify_derived(root,seal)

if __name__=='__main__':unittest.main(verbosity=2)
