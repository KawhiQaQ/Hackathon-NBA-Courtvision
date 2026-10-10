"""Worker/API orchestration with in-memory AWS doubles, real renderer + MP4.
This verifies wiring, not cloud permissions or model accuracy.
"""
import base64,copy,importlib.util,io,json,os,sys,tempfile,types,unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from test_presentation import fixture,ROOT
from perception_cache import cache_key

class WorkerPresentationTests(unittest.TestCase):
 def test_model_narration_to_rendered_job_and_signed_viewer(self):
  self.run_pipeline()

 def test_commentary_failure_preserves_rendered_job(self):
  self.run_pipeline(commentary_failure=True)

 def test_normal_job_renders_actor_evidence_and_board_without_review(self):
  self.run_pipeline(with_profile=True)

 def test_render_failure_is_failed_not_a_completed_job(self):
  self.run_pipeline(render_failure=True)

 def test_force_recomputes_visual_detection_even_with_existing_cache(self):
  self.run_pipeline(force=True)

 def test_perception_checkpoints_before_agent_and_continues_from_cache(self):
  self.run_pipeline(force=True,checkpoint=True)

 def run_pipeline(self,commentary_failure=False,with_profile=False,render_failure=False,force=False,checkpoint=False):
  import subprocess
  from render_video import ffmpeg
  result=fixture()
  if with_profile:
   profile=json.loads((ROOT/'data/reference/dallas-practice-actor-profile.json').read_text())
   result['deepData']={'videoId':result['video']['id'],'official':{'gameId':'0022500701','eventId':666},'playerProfiles':[profile],'companion':{'players':[{'trackId':'lead-x','sourcePlayerId':'1629655'}]}}
  img=io.BytesIO();Image.new('RGB',(320,180),'gray').save(img,format='JPEG')
  frames=[dict(time=t,image=base64.b64encode(img.getvalue()).decode()) for t in [0,.4,.8,1.2,1.6,2.1]]
  request={'mode':'video','video':result['video'],'frames':frames,'force':force}
  job='parity-job';prefix=f'jobs/{job}/';calls=[]
  class Store:
   def __init__(self):self.data={}
   def put_object(self,Key,Body,**kw):self.data[Key]=Body
   def get_object(self,Key,**kw):return {'Body':io.BytesIO(self.data[Key])}
   def head_object(self,**kw):return {'ETag':'etag'}
   def upload_file(self,path,bucket,key,**kw):self.data[key]=Path(path).read_bytes()
   def download_file(self,bucket,key,path):Path(path).write_bytes(self.data[key])
   def generate_presigned_url(self,operation,Params,**kw):return 'https://assets.example/'+Params['Key']+'?signature=test'
  dispatched=[]
  class Agent:
   def invoke(self,Payload,**kw):dispatched.append(json.loads(Payload));return {'StatusCode':202}
   def invoke_agent_runtime(self,payload,**kw):
    document=json.loads(payload);mode=document.get('mode');calls.append(mode)
    if mode=='resolve-replay-roles':
     t=document['frames'][0]['time']
     value={'beneficiaryIsFinalShooter':True,'distinctRoles':True,'shotTime':2.1,'roles':[{'role':role,'team':'甲队' if i<2 else '乙队','jersey':str(i+1),'reference':{'time':t,'detectionId':f'D{i}'}} for i,role in enumerate(['actor','beneficiary','defender'])]}
    elif mode=='locate-replay-roles':
     value={'frames':[{'time':f['time'],'roles':{role:{'detectionId':f'D{i}','confidence':.99} for i,role in enumerate(['actor','beneficiary','defender'])}} for f in document['frames']]}
    elif mode=='verify-temporal-candidates':
     value={'checks':[dict(id=c['id'],onBall=True,samePlayer=True,isShooter=False,passObserved=True,beneficiaryIsShooter=True,defenderResponds=True) for c in document['candidates']]}
    elif mode=='narrate-video':
     if with_profile:assert document['narrationContext']['actorEvidence']['finishing']['made']==7
     value=result['narration']
    elif mode=='explain-temporal-candidate':
     if commentary_failure:raise RuntimeError('temporary commentary throttling')
     value={'commentary':'接应者持球后转移球权。'}
    else:value=copy.deepcopy(result)
    return {'response':io.BytesIO(json.dumps({'ok':True,'result':value}).encode())}
   def stop_runtime_session(self,**kw):pass
  store=Store();agent=Agent()
  boto=types.SimpleNamespace(client=lambda name,**kw:store if name=='s3' else agent)
  visual_calls=[]
  def detect(payload,progress):
   visual_calls.append('detect');return copy.deepcopy(result['vision']),frames
  vision=types.SimpleNamespace(build_vision=detect,sample_video=lambda *a:frames)
  with tempfile.TemporaryDirectory() as temp,patch.dict(sys.modules,{'boto3':boto,'vision':vision}),patch.dict(os.environ,{'AGENT_RUNTIME_ARN':'test','TEAM_KEY':'test-key',**({'AWS_LAMBDA_FUNCTION_NAME':'worker'} if checkpoint else {})}):
   source=Path(temp)/'source.mp4'
   subprocess.run([ffmpeg(),'-v','error','-f','lavfi','-i','color=c=gray:s=320x180:r=24:d=2.5','-c:v','libx264',str(source)],check=True)
   store.data['videos/source.mp4']=source.read_bytes()
   store.data[prefix+'request.json']=json.dumps(request).encode()
   store.data['library/arbitrary-clip.json']=json.dumps({'key':'videos/source.mp4'}).encode()
   store.data[cache_key('videos/source.mp4','etag',frames)]=json.dumps({'vision':result['vision'],'frames':frames}).encode()
   spec=importlib.util.spec_from_file_location('parity_handler',ROOT/'cloud/api/handler.py');handler=importlib.util.module_from_spec(spec);spec.loader.exec_module(handler)
   with patch('render_video.render',side_effect=RuntimeError('encoder failed')) if render_failure else nullcontext():
    handler.worker({'job':job})
    if checkpoint:
     self.assertEqual(calls,[]);self.assertEqual(dispatched,[{'internal':'analyze','job':job,'phase':'analysis'}])
     self.assertNotIn(prefix+'result.json',store.data)
     handler.worker(dispatched[0])
   self.assertEqual(len(visual_calls),1 if force else 0)
   if render_failure:
    status=json.loads(store.data[prefix+'status.json'])
    self.assertEqual(status['status'],'failed')
    self.assertIn('战术视频生成失败',status['error'])
    saved=json.loads(store.data[prefix+'result.json'])
    self.assertFalse(saved['presentation']['rendered'])
    self.assertNotIn(prefix+'tactical.mp4',store.data)
    return
   status=json.loads(store.data[prefix+'status.json']);self.assertEqual(status['status'],'completed',status)
   self.assertIn('narrate-video',calls);self.assertIn('verify-temporal-candidates',calls);self.assertIn('locate-replay-roles',calls)
   saved=json.loads(store.data[prefix+'result.json']);self.assertTrue(saved['presentation']['rendered'])
   if with_profile:
    self.assertEqual(saved['presentation']['insights']['actorProfile']['playerId'],'1629655')
    self.assertEqual(saved['presentation']['direction']['source'],'verified-event')
    self.assertEqual(saved['presentation']['direction']['board']['coordinateSystem'],'image-relative')
    self.assertEqual(len(saved['presentation']['direction']['board']['trackIds']),3)
    self.assertNotIn('presentationReview',saved)
   if commentary_failure:self.assertEqual(saved['commentaryStatus'],'unavailable')
   self.assertEqual(saved['presentation']['insights']['narration']['segments'],result['narration']['segments'])
   self.assertTrue(store.data[prefix+'tactical.mp4'])
   self.assertTrue(any(k.startswith(prefix+'presentation/frame-') for k in store.data))
   reply=handler.handler({'rawPath':'/api/jobs/'+job,'headers':{'x-team-key':'test-key'}},None)
   view=json.loads(reply['body'])['result']['presentation']
   self.assertIn('signature=test',view['video']);self.assertIn('signature=test',view['original'])
   self.assertTrue(all('signature=test' in f['image'] for f in view['evidence']))
   denied=handler.handler({'rawPath':'/api/jobs/'+job,'headers':{}},None);self.assertEqual(denied['statusCode'],401)

   # Real API endpoints aggregate signed job presentations and persist only job references.
   event={'rawPath':'/api/games','requestContext':{'http':{'method':'POST'}},'headers':{'x-team-key':'test-key'},'body':json.dumps({'jobIds':[job,job],'gameId':'0022500701' if with_profile else 'match-a','team':'尼克斯','identities':{job:'44'}})}
   response=handler.handler(event,None);self.assertEqual(response['statusCode'],200,response)
   collection=json.loads(response['body']);self.assertEqual(collection['summary']['creditedRounds'],1);self.assertEqual(collection['summary']['winner']['jersey'],'44')
   response=handler.handler({'rawPath':'/api/games/'+collection['id'],'headers':{'x-team-key':'test-key'}},None)
   self.assertEqual(json.loads(response['body'])['roundCount'],1)
   denied=handler.handler({'rawPath':'/api/games/'+collection['id'],'headers':{}},None);self.assertEqual(denied['statusCode'],401)
