"""Frozen B1 execution, isolated predictions, bounded requests; never scores."""
import os,sys,pathlib,json,hashlib,time,copy,collections,random,socket
O=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('/home/public/zb/FreeGrasp_code-freegrasp_codex')
phase=sys.argv[1];assert phase in ('replay','paid')
# Execution order is a scheduling variable only: it cannot change a prediction.
# Frozen seed; the derived order and its hash are recorded in the seal.
RUN_ORDER_SEED=20260930
sys.dont_write_bytecode=True
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',CUDA_VISIBLE_DEVICES='3',TOKENIZERS_PARALLELISM='false')
sys.path.insert(0,str(R))
from protocol import augment,classify,evidence,tests
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def dump(p,obj):
 with pathlib.Path(p).open('x') as f:json.dump(obj,f,indent=2,ensure_ascii=False)
class Stop(BaseException):pass
def audit(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=os.fsdecode(args[0]);mode=args[1] or '';flags=args[2] or 0
  if 'score_only.json' in p or '/npz_file/' in p or '/data/output/molmo_output/' in p:
   raise Stop('FORBIDDEN_INFERENCE_FILE')
  if p.startswith(str(R)+'/') and (any(c in mode for c in 'wax+') or flags & (os.O_WRONLY|os.O_RDWR)):
   raise Stop('FROZEN_REPO_WRITE')
sys.addaudithook(audit)
if phase=='replay':
 def deny(*a,**kw):raise Stop('REPLAY_NETWORK_ATTEMPT')
 socket.socket.connect=deny;socket.socket.connect_ex=deny
dest=O/phase;dest.mkdir()
start=time.time();state={'phase':phase,'status':'running','completed':[],'api_attempts':0,'mimo_attempts':0,'qwen_attempts':0,'qwen_cost_cny':0.,'mimo_equivalent_cny':0.,'tokens':{},'cache_hits':0,'cache_misses':0}
def event(rec):
 with (dest/'events.jsonl').open('a') as f:f.write(json.dumps(rec,ensure_ascii=False)+'\n')
current={};counts={};request_seq=0
try:
 import numpy as np,torch,httpx
 from PIL import Image
 import evaluate_mimo as M
 M.ensure_unused_dashscope_key_for_import()
 import utils.utils as U
 import utils.eghc_adjudicator as A
 from models.langsam.langsam_actor import LangSAM
 torch.set_num_threads(4)
 prep=json.loads((O/'preparation.json').read_text());assert sha(O/'inputs.json')==prep['inputs_sha256']
 for n,h in prep['repo_code'].items():assert sha(R/n)==h
 for n,h in prep['scripts'].items():assert sha(O/n)==h
 assert tests()==9
 rows=json.loads((O/'inputs.json').read_text())
 run_order=list(range(len(rows)));random.Random(RUN_ORDER_SEED).shuffle(run_order)
 order_cases=[rows[i]['case'] for i in run_order]
 order_sha256=hashlib.sha256(json.dumps(order_cases).encode()).hexdigest()
 state.update(order_seed=RUN_ORDER_SEED,execution_order=order_cases,execution_order_sha256=order_sha256)
 if phase=='paid':
  gate=json.loads((O/'replay_score.json').read_text());assert gate['parity_gate']=='PASS' and gate['n']==24
  assert os.environ.get('MIMO_API_KEY','').startswith('tp-'),'Expected existing Token Plan'
  assert A.resolve_qwen_api_key()
  assert os.environ.get('MIMO_BASE_URL','https://token-plan-cn.xiaomimimo.com/v1').rstrip('/')=='https://token-plan-cn.xiaomimimo.com/v1'
 actor=LangSAM(sam_type='vit_h',ckpt_path='/home/wyl/.cache/torch/hub/checkpoints/sam_vit_h_4b8939.pth',use_gpu=True,sam_backend='sam1')
 U.get_langsam_actor=lambda **kw:actor
 original_predict=actor.predict
 cache=O/'mask_cache';cache.mkdir(exist_ok=True)
 def cached_predict(image,query,*a,**kw):
  identity=[current['image_hash'],query,a,kw,prep['assets'],prep['repo_code']['models/langsam/langsam_actor.py'],torch.__version__]
  key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();p=cache/(key+'.npz');meta=cache/(key+'.json')
  if meta.exists():
   info=json.loads(meta.read_text());assert sha(p)==info['sha256'];z=np.load(p);state['cache_hits']+=1
   return torch.from_numpy(z['masks']),torch.from_numpy(z['boxes']),info['phrases'],torch.from_numpy(z['logits'])
  if p.exists():raise Stop('INCOMPLETE_CACHE')
  with torch.inference_mode():m,b,phr,l=original_predict(image,query,*a,**kw)
  np.savez_compressed(p,masks=m.cpu().numpy(),boxes=b.cpu().numpy(),logits=l.cpu().numpy());dump(meta,{'sha256':sha(p),'phrases':phr,'query':query});state['cache_misses']+=1
  return m,b,phr,l
 actor.predict=cached_predict
 client=httpx.Client(timeout=120,trust_env=False)
 def api(provider,messages,max_tokens,model):
  global request_seq
  if time.time()-start>7200:raise Stop('TIME_BUDGET')
  if state['api_attempts']>=216:raise Stop('CALL_BUDGET')
  if counts.get(provider,0)>=(2 if provider=='mimo' else 1):raise Stop('ROW_CALL_BUDGET')
  # One <=2MP image; UTF-8 text bytes + conservative 16K image token reserve.
  text_bytes=sum(len(str(part.get('text','')).encode()) for msg in messages for part in (msg['content'] if isinstance(msg['content'],list) else [{'text':msg['content']}]))
  if text_bytes>32000:raise Stop('INPUT_SIZE_BUDGET')
  reserve=(text_bytes+16384)*2/1e6+max_tokens*12/1e6
  if provider=='qwen' and state['qwen_cost_cny']+reserve>5:raise Stop('COST_BUDGET')
  counts[provider]=counts.get(provider,0)+1;state['api_attempts']+=1;state[provider+'_attempts']+=1;request_seq+=1
  rid=f'r{request_seq:04d}';request_hash=hashlib.sha256(json.dumps(messages,sort_keys=True).encode()).hexdigest()
  event({'event':'dispatch','request':rid,'case':current['row']['case'],'arm':current['arm'],'provider':provider,'model':model,'request_sha256':request_hash,'output_limit':max_tokens})
  if provider=='mimo':
   url='https://token-plan-cn.xiaomimimo.com/v1/chat/completions';headers={'api-key':os.environ['MIMO_API_KEY']}
   payload=M.build_mimo_payload(model=model,messages=messages,max_tokens=max_tokens,temperature=0,top_p=1,frequency_penalty=0,presence_penalty=0,seed=0)
  else:
   url=A.QWEN_BASE_URL+'/chat/completions';headers={'Authorization':'Bearer '+A.resolve_qwen_api_key()}
   payload={'model':model,'messages':messages,'temperature':0,'top_p':1,'max_tokens':max_tokens}
  try:response=client.post(url,headers=headers,json=payload)
  except Exception as e:raise Stop('API_TRANSPORT_'+type(e).__name__)
  if response.status_code!=200:
   event({'event':'http_error','request':rid,'status':response.status_code});raise Stop('HTTP_'+str(response.status_code))
  try:data=response.json()
  except Exception:raise Stop('RESPONSE_NOT_JSON')
  # Only model response/usage, never request headers or credentials.
  dump(dest/(rid+'_response.json'),data)
  if data.get('model') != model:raise Stop('MODEL_IDENTITY_MISMATCH')
  usage=data.get('usage',{});pin=usage.get('prompt_tokens');pout=usage.get('completion_tokens')
  if pin is None or pout is None:raise Stop('MISSING_USAGE')
  state['tokens'][provider]=state['tokens'].get(provider,0)+pin+pout
  if provider=='qwen':state['qwen_cost_cny']+=(pin*2+pout*12)/1e6
  else:state['mimo_equivalent_cny']+=(pin+pout*2)/1e6
  if pin>text_bytes+16384 or state['qwen_cost_cny']>5:raise Stop('TOKEN_RESERVE_EXCEEDED')
  choices=data.get('choices',[])
  if not choices or choices[0].get('finish_reason') not in ('stop',None):raise Stop('TRUNCATED_OR_MISSING_COMPLETION')
  content=choices[0].get('message',{}).get('content') or choices[0].get('message',{}).get('reasoning_content') or ''
  if not content:raise Stop('EMPTY_CONTENT')
  event({'event':'response','request':rid,'usage':usage,'model_reported':data.get('model'),'content_sha256':hashlib.sha256(content.encode()).hexdigest()})
  return content
 def call(messages,model,max_tokens):
  if current['replay']:
   if not current['queue']:raise Stop('REPLAY_QUEUE_EMPTY')
   return current['queue'].pop(0)
  if current['router_pending']:
   current['router_pending']=False
   return current['row']['router_output']
  # Do not pre-validate the planner output here: the frozen B1 protocol owns
  # invalid-ID handling (adjudication, then at most one directed repair). Only
  # the final gate below may fail closed.
  return api('mimo',augment(messages,current['row']['route'],current['arm']),max_tokens,model)
 def qwen(messages,**kw):
  if current['replay']:
   if current['row']['replay_qwen_error']:
    event({'event':'historical_verifier_timeout_replayed','case':current['row']['case'],'arm':current['arm']})
    raise TimeoutError('Recorded historical verifier timeout; offline replay only')
   if not current['queue']:raise Stop('QWEN_REPLAY_EMPTY')
   out=current['queue'].pop(0)
   if out!=current['row']['replay_qwen']:raise Stop('QWEN_REPLAY_MISMATCH')
   return out
  out=api('qwen',messages,kw.get('max_output_tokens',512),'qwen3.6-plus')
  try:json.loads(out.strip().removeprefix('```json').removesuffix('```').strip())
  except Exception:raise ValueError('QWEN_PARSE')
  return out
 U._call_reasoning_model=call;A.call_qwen_adjudicator=qwen
 # Interleave arms per row, rotate order independent of outcomes.
 for i,row_index in enumerate(run_order):
  row=rows[row_index]
  for p,h in row['hashes'].items():assert sha(p)==h
  arms=['replay'] if phase=='replay' else ['baseline','uniform','adaptive']
  if phase=='paid':arms=arms[i%3:]+arms[:i%3]
  for arm in arms:
   if time.time()-start>7200:raise Stop('TIME_BUDGET')
   current={'row':row,'arm':arm,'replay':phase=='replay' or row['route']['route_mode']=='direct','queue':list(row['replay_outputs']),
            'router_pending':True,'visible':[x[0] for x in U.parse_visible_points(pathlib.Path(row['point_dir'])/f"{row['scene']}_id.txt")[0]],'image_hash':row['hashes'][row['image']]}
   counts={};im=Image.open(row['image']).convert('RGB');assert im.width*im.height<=2000000
   pred=U.get_prediction_result(im,row['point_dir'],row['scene'],row['instruction'],return_metadata=True,prompt_variant='legacy',model_name='mimo-v2.5',max_output_tokens=1024,mimo_retry_mode='none',segmentation_variant='eghc_mask_repair_v1',routing_variant='evidence_gated_cascade',feature_source='predicted',protocol_ablation='full',route_guard_variant='pathb_blk_arb_v1',sam_backend='sam1')
   if pred.get('error'):raise Stop('PIPELINE_ERROR')
   if current['replay'] and current['queue']:raise Stop('UNCONSUMED_REPLAY_OUTPUTS')
   rr=pred['reasoning']
   if rr.get('parse_status')!='valid_id':raise Stop('FINAL_INVALID_ID')
   if rr.get('qwen_adjudication',{}).get('decision')=='verifier_error_keep' and not (current['replay'] and row['replay_qwen_error']):raise Stop('VERIFIER_FAILURE')
   mask=pred['mask'];mask=mask.cpu().numpy() if hasattr(mask,'cpu') else np.asarray(mask)
   stem=row['case']+'_'+arm;mp=dest/(stem+'.npz');np.savez_compressed(mp,mask=mask)
   dump(dest/(stem+'.json'),{'case':row['case'],'arm':arm,'reasoning':rr,'mask_sha256':sha(mp),'class':classify(evidence(row['route'])),'reused_direct':phase=='paid' and current['replay'],'calls':dict(counts)})
   state['completed'].append(stem);print(json.dumps({'phase':phase,'completed':len(state['completed']),'planned':24 if phase=='replay' else 72,'calls':state['api_attempts']}),flush=True)
 state['status']='complete'
except BaseException as e:
 state['status']='stopped';state['error_type']=type(e).__name__;state['reason']=str(e)[:160] if isinstance(e,(Stop,AssertionError)) else 'see sanitized traceback locations'
 import traceback
 state['traceback_locations']=[{'file':x.filename,'line':x.lineno,'function':x.name} for x in traceback.extract_tb(e.__traceback__)]
 print(json.dumps({'status':state['status'],'reason':state['reason'],'error_type':state['error_type']}),flush=True)
finally:
 state['elapsed_seconds']=time.time()-start;state['output_hashes']={p.name:sha(p) for p in dest.glob('c*.json')};state['scripts']={p.name:sha(p) for p in O.glob('*.py')};dump(dest/'seal.json',state)
if state['status']!='complete':sys.exit(1)