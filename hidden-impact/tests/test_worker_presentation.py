"""Worker/API orchestration with in-memory AWS doubles, real renderer + MP4.
This verifies wiring, not cloud permissions or model accuracy.
"""
import base64,copy,importlib.util,io,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from test_presentation import fixture,ROOT
from perception_cache import cache_key

class WorkerPresentationTests(unittest.TestCase):
 def test_model_narration_to_rendered_job_and_signed_viewer(self):
  import subprocess
  from render_video import ffmpeg
  result=fixture();img=io.BytesIO();Image.new('RGB',(320,180),'gray').save(img,format='JPEG')
  frames=[dict(time=t,image=base64.b64encode(img.getvalue()).decode()) for t in [0,.4,.8,1.2,1.6,2.1]]
  request={'mode':'video','video':result['video'],'frames':frames}
  job='parity-job';prefix=f'jobs/{job}/';calls=[]
  class Store:
   def __init__(self):self.data={}
   def put_object(self,Key,Body,**kw):self.data[Key]=Body
   def get_object(self,Key,**kw):return {'Body':io.BytesIO(self.data[Key])}
   def head_object(self,**kw):return {'ETag':'etag'}
   def upload_file(self,path,bucket,key,**kw):self.data[key]=Path(path).read_bytes()
   def download_file(self,bucket,key,path):Path(path).write_bytes(self.data[key])
   def generate_presigned_url(self,operation,Params,**kw):return 'https://assets.example/'+Params['Key']+'?signature=test'
  class Agent:
   def invoke_agent_runtime(self,payload,**kw):
    document=json.loads(payload);mode=document.get('mode');calls.append(mode)
    if mode=='verify-temporal-candidates':
     value={'checks':[dict(id=c['id'],onBall=True,samePlayer=True,isShooter=False,passObserved=True,beneficiaryIsShooter=True,defenderResponds=True) for c in document['candidates']]}
    elif mode=='narrate-video':value=result['narration']
    elif mode=='explain-temporal-candidate':value={'commentary':'接应者持球后转移球权。'}
    else:value=copy.deepcopy(result)
    return {'response':io.BytesIO(json.dumps({'ok':True,'result':value}).encode())}
   def stop_runtime_session(self,**kw):pass
  store=Store();agent=Agent()
  boto=types.SimpleNamespace(client=lambda name,**kw:store if name=='s3' else agent)
  vision=types.SimpleNamespace(build_vision=lambda *a:None,sample_video=lambda *a:None)
  with tempfile.TemporaryDirectory() as temp,patch.dict(sys.modules,{'boto3':boto,'vision':vision}),patch.dict(os.environ,{'AGENT_RUNTIME_ARN':'test','TEAM_KEY':'test-key'}):
   source=Path(temp)/'source.mp4'
   subprocess.run([ffmpeg(),'-v','error','-f','lavfi','-i','color=c=gray:s=320x180:r=24:d=2.5','-c:v','libx264',str(source)],check=True)
   store.data['videos/source.mp4']=source.read_bytes()
   store.data[prefix+'request.json']=json.dumps(request).encode()
   store.data['library/arbitrary-clip.json']=json.dumps({'key':'videos/source.mp4'}).encode()
   store.data[cache_key('videos/source.mp4','etag',frames)]=json.dumps({'vision':result['vision'],'frames':frames}).encode()
   spec=importlib.util.spec_from_file_location('parity_handler',ROOT/'cloud/api/handler.py');handler=importlib.util.module_from_spec(spec);spec.loader.exec_module(handler)
   handler.worker({'job':job})
   status=json.loads(store.data[prefix+'status.json']);self.assertEqual(status['status'],'completed',status)
   self.assertIn('narrate-video',calls);self.assertIn('verify-temporal-candidates',calls)
   saved=json.loads(store.data[prefix+'result.json']);self.assertTrue(saved['presentation']['rendered'])
   self.assertEqual(saved['presentation']['insights']['narration']['segments'],result['narration']['segments'])
   self.assertTrue(store.data[prefix+'tactical.mp4'])
   self.assertTrue(any(k.startswith(prefix+'presentation/frame-') for k in store.data))
   reply=handler.handler({'rawPath':'/api/jobs/'+job,'headers':{'x-team-key':'test-key'}},None)
   view=json.loads(reply['body'])['result']['presentation']
   self.assertIn('signature=test',view['video']);self.assertIn('signature=test',view['original'])
   self.assertTrue(all('signature=test' in f['image'] for f in view['evidence']))
   denied=handler.handler({'rawPath':'/api/jobs/'+job,'headers':{}},None);self.assertEqual(denied['statusCode'],401)

   # Real API endpoints aggregate signed job presentations and persist only job references.
   event={'rawPath':'/api/games','requestContext':{'http':{'method':'POST'}},'headers':{'x-team-key':'test-key'},'body':json.dumps({'jobIds':[job,job],'gameId':'match-a','team':'尼克斯','identities':{job:'44'}})}
   response=handler.handler(event,None);self.assertEqual(response['statusCode'],200,response)
   collection=json.loads(response['body']);self.assertEqual(collection['summary']['creditedRounds'],1);self.assertEqual(collection['summary']['winner']['jersey'],'44')
   response=handler.handler({'rawPath':'/api/games/'+collection['id'],'headers':{'x-team-key':'test-key'}},None)
   self.assertEqual(json.loads(response['body'])['roundCount'],1)
   denied=handler.handler({'rawPath':'/api/games/'+collection['id'],'headers':{}},None);self.assertEqual(denied['statusCode'],401)
