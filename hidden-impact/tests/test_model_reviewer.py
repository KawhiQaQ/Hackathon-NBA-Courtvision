import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from model_reviewer import run,validate_source,SOURCE
from reviewed_presentation import build,validate
from role_model import parse_response


class ModelReviewerTests(unittest.TestCase):
    def setUp(self):
        self.roles=[dict(role=k,id=k,team=team,jersey=j,name=team+j+'号',sourcePlayerId=str(i+1))
                    for i,(k,team,j) in enumerate([('actor','甲队','7'),('beneficiary','甲队','00'),('defender','乙队','10')])]
        self.frames=[dict(time=t,scene=0,people=[dict(trackId=r['id'],x=.15+i*.2,y=.3,w=.07,h=.3,confidence=.9,detectorTrackId='D'+str(i)) for i,r in enumerate(self.roles)]) for t in [0,1,2]]
        self.lock=dict(status='locked',roles=self.roles,frames=self.frames,eventId='visual-role-story',source='bedrock-vlm-detector-grounding',shotTime=2.5,
                       actorAction='甲队7号提供掩护。',actionWindow={'start':0,'end':2},beneficiaryIsFinalShooter=True,coverage={r['role']:1 for r in self.roles})
        self.source=dict(video={'id':'clip','duration':3},model='unit-model',modelInvoked=True,events=[],players=[],vision={'frames':self.frames},narration={'segments':[]})
        self.narration=dict(model='unit-model',modelInvoked=True,source='model-test',segments=[dict(start=0,end=1.5,title='掩护',text='队友上提提供掩护。',frameTimes=[0,1]),dict(start=1.5,end=3,title='出手',text='终结者完成出手。',frameTimes=[2])])

    def review(self):
        def resolve(current,vision,frames,invoke,progress):
            invoke({'mode':'locate-known-roles'})
            return copy.deepcopy(self.lock)
        def invoke(document):
            if document['mode']=='narrate-video':
                self.assertIn('reviewDraft',document)
                return self.narration
            return {'model':'unit-model','modelInvoked':True,'requestId':'test-request'}
        with patch('role_localization.resolve',resolve):
            return run(self.source,[{'time':i/6,'image':'test'} for i in range(18)],invoke,'a'*64,'jobs/original/result.json')

    def test_model_review_produces_grounded_references_and_renderable_plan(self):
        before=copy.deepcopy(self.source);plan,report,refs=self.review()
        result=build(self.source,plan,'a'*64,'original',model_review=report)
        self.assertEqual(self.source,before)
        self.assertEqual(plan['source'],SOURCE)
        self.assertEqual(len(refs['roles']),3)
        self.assertEqual(refs['roles'][0]['box']['x'],.15)
        self.assertEqual(plan['roles'][0]['anchors'][0],[0,(.15+.07/2)*640,.6*360,.3*360])
        self.assertEqual(result['presentationPlan']['source'],SOURCE)
        self.assertTrue(result['narration']['modelInvoked'])
        self.assertTrue(all(f['source']==SOURCE for f in result['presentation']['evidence']))
        self.assertEqual(result['events'],before['events'])
        self.assertIsNone(result['presentation']['score'])
        self.assertEqual(len(report['calls']),2)

    def test_edited_plan_cannot_reuse_model_receipt(self):
        plan,report,_=self.review();plan['segments'][0]['text']='changed'
        with self.assertRaisesRegex(ValueError,'receipt'):build(self.source,plan,'a'*64,'original',model_review=report)

    def test_http_editor_cannot_claim_model_output(self):
        plan,_,_=self.review()
        with self.assertRaises(ValueError):validate(plan,self.source,'a'*64)

    def test_human_annotations_not_used_as_automatic_review_input(self):
        for field in ['presentationReview','modelReview']:
            source={**self.source,field:{'source':'edited'}}
            with self.assertRaises(ValueError):validate_source(source)
        source={**self.source,'narration':{'source':'human-reviewed-video'}}
        with self.assertRaises(ValueError):validate_source(source)

    def test_role_json_can_follow_reasoning_but_invalid_output_is_rejected(self):
        self.assertEqual(parse_response('说明\n```json\n{"roles":{}}\n```'),{'roles':{}})
        with self.assertRaises(ValueError):parse_response('{broken')

    def test_runtime_retries_transient_errors_and_closes_every_session(self):
        import io,json
        from unittest.mock import Mock
        from botocore.exceptions import ClientError
        from reviewer_runtime import invoke
        agent=Mock();sleep=Mock()
        temporary=ClientError({'Error':{'Code':'502'},'ResponseMetadata':{'HTTPStatusCode':502}},'InvokeAgentRuntime')
        stream=io.BytesIO(json.dumps({'ok':True,'result':{'modelInvoked':True}}).encode())
        agent.invoke_agent_runtime.side_effect=[temporary,{'response':stream}]
        self.assertEqual(invoke(agent,'arn',{},sleep)['runtimeAttempts'],2)
        self.assertEqual(agent.stop_runtime_session.call_count,2)
        self.assertTrue(stream.closed);sleep.assert_called_once_with(2)
        agent.reset_mock();agent.invoke_agent_runtime.side_effect=temporary
        with self.assertRaises(ClientError):invoke(agent,'arn',{},sleep)
        self.assertEqual(agent.invoke_agent_runtime.call_count,3)
        agent.reset_mock()
        agent.invoke_agent_runtime.side_effect=ClientError({'Error':{'Code':'AccessDeniedException'},'ResponseMetadata':{'HTTPStatusCode':403}},'InvokeAgentRuntime')
        with self.assertRaises(ClientError):invoke(agent,'arn',{},sleep)
        self.assertEqual(agent.invoke_agent_runtime.call_count,1)

    def test_reviewer_api_authenticates_and_only_queues_source_reference(self):
        import importlib.util,io,json,os,types
        data={'analyses/original/result.json':json.dumps(self.source).encode(),
              'library/clip.json':json.dumps({'sha256':'a'*64}).encode()}
        class Store:
            def get_object(self,Key,**kwargs):return {'Body':io.BytesIO(data[Key])}
            def put_object(self,Key,Body,**kwargs):data[Key]=Body
        class Queue:
            def invoke(self,**kwargs):return {'StatusCode':202}
        store=Store();queue=Queue()
        with patch.dict(sys.modules,{'boto3':types.SimpleNamespace(client=lambda name,**kwargs:store if name=='s3' else queue)}),patch.dict(os.environ,{'TEAM_KEY':'test','WORKER_NAME':'test'}):
            spec=importlib.util.spec_from_file_location('reviewer_api_test',ROOT/'cloud/api/handler.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
            event={'rawPath':'/api/reviews','requestContext':{'http':{'method':'POST'}},'headers':{},
                   'body':json.dumps({'sourceAnalysis':'original','review':{'source':'pretend-model'}})}
            self.assertEqual(h.handler(event,None)['statusCode'],401)
            event['headers']={'x-team-key':'test'}
            response=h.handler(event,None);self.assertEqual(response['statusCode'],202,response)
            job=json.loads(response['body'])['job'];request=json.loads(data[f'jobs/{job}/request.json'])
            self.assertEqual(request,{'sourceAnalysis':'original','mode':'model-reviewed-presentation'})
            event['body']=json.dumps({'sourceAnalysis':'../private'})
            self.assertEqual(h.handler(event,None)['statusCode'],400)
