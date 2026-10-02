"""Separate post-prediction scorer, official IoU loop and current ID mapping."""
import pathlib,sys,json,hashlib,collections
import numpy as np
O=pathlib.Path(__file__).resolve().parent;phase=sys.argv[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
prep=json.loads((O/'preparation.json').read_text());assert sha(O/'score_only.json')==prep['score_sha256']
truth={r['case']:r for r in json.loads((O/'score_only.json').read_text())};seal=json.loads((O/phase/'seal.json').read_text());results=[]
for stem in seal['completed']:
 p=O/phase/(stem+'.json');assert sha(p)==seal['output_hashes'][p.name];rec=json.loads(p.read_text());case=rec['case'];t=truth[case];d=t['detail']
 mpath=O/phase/(stem+'.npz');assert sha(mpath)==rec['mask_sha256'];mask=np.load(mpath)['mask'].astype(bool).squeeze();assert mask.ndim==2
 assert sha(pathlib.Path(t['gt_file']))==t['gt_sha256'];z=np.load(t['gt_file'],allow_pickle=True);gt=z['instances_objects'] if 'instances_objects' in z else z['instances_objects.npy']
 iou=0.
 for gid in d['gt_ids']:
  target=gt==gid if gt.ndim==2 else gt[gid-1]>0
  union=np.logical_or(mask,target).sum();iou=float(np.logical_and(mask,target).sum()/union) if union else 0.
  if iou>=.5:break
 mp=pathlib.Path(t['mapping_file']);assert sha(mp)==t['mapping_sha256'];lines=[l.split() for l in mp.read_text().splitlines() if l.strip()];header=lines[0];mapping={int(l[header.index('Molmo_ID')]):int(l[header.index('GT_ID')]) for l in lines[1:]}
 sid=rec['reasoning']['selected_object_id'];mapped=mapping[int(sid)];rsr=int(mapped in d['gt_ids']);ssr=int(iou>=.5)
 results.append({'case':case,'arm':rec['arm'],'subset':t['subset'],'scene':d['scene_id'],'object':d['object_id'],'ssr':ssr,'rsr':rsr,'iou':iou,'selected_id':sid,'mapped_id':mapped,'class':rec['class'],
 'historical_ssr':d['ssr_correct'],'historical_rsr':d['rsr_correct'],'parity':ssr==d['ssr_correct'] and rsr==d['rsr_correct'] and abs(iou-d['iou'])<=.001 and sid==d['reasoning']['selected_object_id']})
summary={}
for arm in sorted({r['arm'] for r in results}):
 rr=[r for r in results if r['arm']==arm];summary[arm]={'n':len(rr),'planned':24,'ssr':sum(r['ssr'] for r in rr),'rsr':sum(r['rsr'] for r in rr)}
pairs={}
if phase=='paid':
 for a,b in [('baseline','uniform'),('baseline','adaptive'),('uniform','adaptive')]:
  aa={r['case']:r for r in results if r['arm']==a};bb={r['case']:r for r in results if r['arm']==b};keys=sorted(aa.keys()&bb.keys());out={}
  for metric in ['ssr','rsr']:
   loss=sum(aa[k][metric]==1 and bb[k][metric]==0 for k in keys);gain=sum(aa[k][metric]==0 and bb[k][metric]==1 for k in keys)
   clusters=collections.defaultdict(list)
   for k in keys:clusters[(aa[k]['scene'],aa[k]['object'])].append(bb[k][metric]-aa[k][metric])
   vals=list(clusters.values());rng=np.random.default_rng(20260929);boot=[]
   if vals:
    for _ in range(5000):
     sample=[vals[i] for i in rng.integers(len(vals),size=len(vals))];boot.append(100*sum(sum(v) for v in sample)/sum(len(v) for v in sample))
   out[metric]={'n_pairs':len(keys),'gain':gain,'loss':loss,'net':gain-loss,'cluster_95ci_pp':np.percentile(boot,[2.5,97.5]).tolist() if boot else None}
  pairs[a+'_vs_'+b]=out
out={'status':seal['status'],'n':len(results),'planned':24 if phase=='replay' else 72,'parity_gate':'PASS' if phase=='replay' and len(results)==24 and all(r['parity'] for r in results) else 'NOT_PASSED' if phase=='replay' else 'N/A',
     'summary':summary,'paired':pairs,'rows':results,'evidence':'C-diagnostic; exposed stratified 24-row test; no generalization claim'}
with (O/(phase+'_score.json')).open('x') as f:json.dump(out,f,indent=2)
print(json.dumps({k:v for k,v in out.items() if k!='rows'}))
