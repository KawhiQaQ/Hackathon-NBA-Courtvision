"""Failure/retry contracts at the real API handler boundary."""
import base64
import importlib.util
import io
import json
import os
import sys
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from botocore.exceptions import ClientError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))

class Store:
 exceptions=types.SimpleNamespace(ClientError=ClientError)
 def __init__(self):self.data={}
 def put_object(self,Key,Body,**kw):self.data[Key]=Body
 def get_object(self,Key,**kw):
  if Key not in self.data:raise ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
  return {'Body':io.BytesIO(self.data[Key])}
 def head_object(self,**kw):return {'ContentLength':100,'ContentType':'video/mp4'}
 def generate_presigned_post(self,**kw):return {'url':'https://upload.example','fields':{}}

class ReliabilityTests(unittest.TestCase):
 def setUp(self):
  self.store=Store();self.dispatch=types.SimpleNamespace(invoke=lambda **kw:{'StatusCode':202})
  boto=types.SimpleNamespace(client=lambda name,**kw:self.store if name=='s3' else self.dispatch)
  self.env=patch.dict(os.environ,{'TEAM_KEY':'test-key','WORKER_NAME':'test-worker','AGENT_RUNTIME_ARN':'test-agent'})
  self.env.start()
  with patch.dict(sys.modules,{'boto3':boto}):
   spec=importlib.util.spec_from_file_location('reliability_handler',ROOT/'cloud/api/handler.py');self.api=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.api)
  self.api.put('library/clip.json',{'id':'clip','key':'videos/clip'})
 def tearDown(self):self.env.stop()
 def call(self,path,body=None):
  event={'rawPath':path,'headers':{'x-team-key':'test-key'},'requestContext':{'http':{'method':'POST' if body is not None else 'GET'}}}
  if body is not None:event['body']=json.dumps(body)
  result=self.api.handler(event,None)
  return result['statusCode'],json.loads(result['body'])
 def payload(self,duration=3):
  return {'video':{'id':'clip','title':'clip','duration':duration},'frames':[{'time':t,'image':base64.b64encode(b'\xff\xd8test').decode()} for t in [0,1,2]]}
 def test_dispatch_failure_is_failed_and_retry_resubmits(self):
  self.dispatch.invoke=lambda **kw:(_ for _ in ()).throw(RuntimeError('queue unavailable'))
  self.assertEqual(self.call('/api/jobs',self.payload())[0],502)
  statuses=[json.loads(v) for k,v in self.store.data.items() if k.endswith('status.json')]
  self.assertEqual(statuses[0]['status'],'failed')
  self.dispatch.invoke=lambda **kw:{'StatusCode':202}
  code,response=self.call('/api/jobs',self.payload());self.assertEqual(code,202);self.assertNotEqual(response['job'],statuses[0]['job'])
 def test_stale_queue_replaced_but_active_queue_reused(self):
  _,response=self.call('/api/jobs',self.payload());job=response['job']
  code,again=self.call('/api/jobs',self.payload());self.assertEqual(code,200);self.assertTrue(again['cached'])
  self.api.put(f'jobs/{job}/status.json',{'job':job,'status':'running','updatedAt':time.time()-1000})
  code,again=self.call('/api/jobs',self.payload());self.assertEqual(code,202);self.assertNotEqual(again['job'],job)
 def test_error_response_does_not_require_lambda_context(self):
  self.store.get_object=lambda **kw:(_ for _ in ()).throw(RuntimeError('storage unavailable'))
  self.assertEqual(self.call('/api/jobs/missing')[0],502)
  self.assertEqual(self.call('/api/games',{'jobIds':['missing'],'gameId':'match','team':'NYK'})[0],400)
 def test_video_limits_and_negative_frames_rejected(self):
  for duration in [41,7200]:self.assertEqual(self.call('/api/jobs',self.payload(duration))[0],400)
  payload=self.payload();payload['frames'][0]['time']=-.5
  self.assertEqual(self.call('/api/jobs',payload)[0],400)
 def test_upload_validation_and_completion(self):
  valid={'size':100,'title':'clip','type':'video/mp4','duration':3}
  for duration in [None,True,float('nan'),float('inf'),.1,41]:
   self.assertEqual(self.call('/api/upload',{**valid,'duration':duration})[0],400)
  self.assertEqual(self.call('/api/upload',{**valid,'size':True})[0],400)
  code,upload=self.call('/api/upload',valid);self.assertEqual(code,200)
  self.assertEqual(self.call('/api/upload/complete',{'id':upload['id']})[0],200)
  _,upload=self.call('/api/upload',{**valid,'size':101})
  self.assertEqual(self.call('/api/upload/complete',{'id':upload['id']})[0],400)
 def test_worker_missing_request_records_failure(self):
  self.api.worker({'job':'missing'})
  status=self.api.get('jobs/missing/status.json');self.assertEqual(status['status'],'failed')
