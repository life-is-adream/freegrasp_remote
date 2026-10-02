"""Custodian: freeze inputs and keep scores in a separate file."""
import pathlib,json,hashlib,subprocess,io,collections
import pyarrow.parquet as pq
from PIL import Image
from protocol import tests,evidence,classify
O=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('/home/public/zb/FreeGrasp_code-freegrasp_codex')
SOURCE=R/'data/output/ablation_matrix/PATHB_FULL_B1_blk_arb_v25_envcheck_split0'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def dump(n,v):
 with (O/n).open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False)
chosen=[];sources={}
for p in sorted((SOURCE/'split_0').glob('details_*.json')):
 sources[str(p)]=sha(p);rows=json.loads(p.read_text());assert len(rows)==50
 # Selection depends only on opaque row identity, not predictions or outcomes.
 rows.sort(key=lambda d:hashlib.sha256(('20260929|'+str(d['scene_id'])+'|'+d['annotation']).encode()).hexdigest())
 chosen.extend((p.stem.removeprefix('details_'),d) for d in rows[:4])
assert len(chosen)==24
needed={d['scene_id'] for _,d in chosen};images={};(O/'images').mkdir();(O/'points').mkdir()
for p in sorted((R/'data').glob('*.parquet')):
 for row in pq.read_table(p,columns=['sceneId','image']).to_pylist():
  s=row['sceneId']
  if s in needed and s not in images:
   out=O/'images'/f'{s}.png';Image.open(io.BytesIO(row['image']['bytes'])).convert('RGB').save(out);images[s]=str(out)
inputs=[];truth=[]
for i,(subset,d) in enumerate(chosen):
 r=d['reasoning'];case=f'c{i:03d}';s=d['scene_id'];folder=R/f'data/output/molmo_output/scene{s}'
 # Copy only visual point ID columns; GT mapping is physically excluded from inference.
 raw=(folder/f'{s}_id.txt').read_text().splitlines();sanitized=[]
 for line in raw:
  if line.strip():sanitized.append(' '.join(line.split()[:3]))
 pointdir=O/'points'/case;pointdir.mkdir()
 (pointdir/f'{s}_id.txt').write_text('\n'.join(sanitized)+'\n')
 (pointdir/f'{s}.png').write_bytes((folder/f'{s}.png').read_bytes())
 inp={'case':case,'scene':s,'instruction':d['annotation'],'image':images[s],
      'point_dir':str(pointdir),'route':r['pre_guard_route_assessment'],
      'router_output':r['router_raw_output'],'replay_outputs':r['raw_outputs'],
      'replay_qwen':r.get('qwen_adjudication_raw_output'),
      'replay_qwen_error':r.get('qwen_adjudication',{}).get('decision')=='verifier_error_keep',
      'hashes':{str(p):sha(p) for p in [pathlib.Path(images[s]),pointdir/f'{s}_id.txt',pointdir/f'{s}.png']}}
 inputs.append(inp);truth.append({'case':case,'subset':subset,'detail':d,'mapping_file':str(folder/f'{s}_id.txt'),
                                'mapping_sha256':sha(folder/f'{s}_id.txt'),'gt_file':str(R/f'data/npz_file/{s}.npz'),
                                'gt_sha256':sha(R/f'data/npz_file/{s}.npz')})
dump('inputs.json',inputs);dump('score_only.json',truth)
old=json.loads((O.parent/'segmentation_replay_20260929_v1/preparation_manifest.json').read_text())
for p,h in old['assets'].items():assert sha(pathlib.Path(p))==h
codes=['utils/utils.py','utils/eghc_router.py','utils/eghc_adjudicator.py','models/langsam/langsam_actor.py','reasoning_eval.py','evaluate_mimo.py','utils/config.py']
dump('preparation.json',{'n':24,'source':str(SOURCE),'sources':sources,'inputs_sha256':sha(O/'inputs.json'),
 'score_sha256':sha(O/'score_only.json'),'repo_code':{n:sha(R/n) for n in codes},'assets':old['assets'],
 'git_status':subprocess.check_output(['git','status','--porcelain'],cwd=R,text=True),
 'git_diff_sha256':hashlib.sha256(subprocess.check_output(['git','diff','--binary','HEAD'],cwd=R)).hexdigest(),
 'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
 'scripts':{p.name:sha(p) for p in O.glob('*.py')},'tests':tests(),
 'diagnostic_classes':dict(collections.Counter(classify(evidence(r['route'])) for r in inputs)),
 'direct':sum(r['route']['route_mode']=='direct' for r in inputs),
 'data_exposure':'exposed-retrospective','source_chain_status':'pending_replay'})
print(json.dumps({'prepared':len(inputs),'tests':tests(),'classes':dict(collections.Counter(classify(evidence(r['route'])) for r in inputs))}))
