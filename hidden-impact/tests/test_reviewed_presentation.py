import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from reviewed_presentation import build,validate

class ReviewedPresentationTests(unittest.TestCase):
    def setUp(self):
        self.review=json.loads((ROOT/'data/reference/dallas-presentation-review.json').read_text())
        self.source=dict(video={'id':'dallas-practice','duration':21.55},events=[{'id':'original-event','score':0}],players=[{'id':'original-player','score':None}],modelInvoked=True,narration={'status':'generated','modelInvoked':True,'segments':[{'text':'original'}]})
        self.sha=self.review['videoSha256']
    def test_review_does_not_rewrite_model_scores_or_claim_generated_commentary(self):
        before=copy.deepcopy(self.source);r=build(self.source,self.review,self.sha,'source-job')
        self.assertEqual(before,self.source)
        for key in ['events','players']:self.assertEqual(r[key],before[key])
        self.assertEqual(r['originalNarration'],before['narration'])
        self.assertFalse(r['narration']['modelInvoked']);self.assertIsNone(r['presentation']['score'])
        self.assertEqual(r['presentationReview']['sourceJob'],'source-job')
    def test_gravity_context_is_bound_and_validated(self):
        r=build(self.source,self.review,self.sha,'source-job')
        self.assertEqual(r['presentation']['insights']['gravityContexts'],self.review['gravityContexts'])
        for change in [{'metric':'MADE_UP'},{'start':-1},{'end':30},{'playerId':''}]:
            review=copy.deepcopy(self.review);review['gravityContexts'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate(review,self.source,self.sha)
    def test_fixed_roles_and_continuous_cues_for_visible_action(self):
        r=build(self.source,self.review,self.sha,'source-job');frames=r['presentationMotion']['frames']
        for f in frames:
            self.assertEqual([p['trackId'] for p in f['people']],['review-actor','review-beneficiary','review-defender'])
            if .2<=f['time']<20.25:
                self.assertTrue(all(not p.get('offscreen') for p in f['people']))
                self.assertIsNotNone(f['heroArrow']);self.assertIsNotNone(f['defenderArrow'])
        self.assertTrue(frames[0]['people'][0]['offscreen'])
        self.assertTrue(frames[-1]['people'][0]['offscreen'])
        self.assertFalse(frames[-1]['people'][1].get('offscreen'))
    def test_video_hash_identity_and_timeline_mismatches_rejected(self):
        for mode in ['hash','identity','time','bounds','coverage','segment','duplicate','source']:
            review=copy.deepcopy(self.review)
            if mode=='hash':review['videoSha256']='a'*64
            elif mode=='identity':review['videoId']='other'
            elif mode=='time':review['roles'][0]['anchors'][2][0]=0
            elif mode=='bounds':review['roles'][0]['anchors'][2][1]=900
            elif mode=='coverage':review['roles'][0]['anchors'].pop()
            elif mode=='segment':review['segments'][1]['start']=0
            elif mode=='duplicate':review['roles'][1]['jersey']='21'
            elif mode=='source':review['source']='automatic'
            with self.subTest(mode=mode),self.assertRaises(ValueError):validate(review,self.source,self.sha)
    def test_frame_sources_and_story_are_shared_with_replay(self):
        r=build(self.source,self.review,self.sha,'source-job');p=r['presentation']
        self.assertEqual([f['text'] for f in p['evidence']],[s['text'] for s in r['narration']['segments']])
        self.assertEqual(len(p['evidence']),6)
        self.assertTrue(all(f['source']=='human-reviewed-video' for f in p['evidence']))

if __name__=='__main__':unittest.main()

class ReviewApiTests(unittest.TestCase):
    def test_authenticated_review_dispatch_render_and_ranking_boundary(self):
        import importlib.util,io,os,types
        from unittest.mock import patch
        review=json.loads((ROOT/'data/reference/dallas-presentation-review.json').read_text())
        source=dict(video={'id':'dallas-practice','duration':21.55},events=[],players=[],modelInvoked=True,vision={'aspectRatio':16/9},narration={'segments':[]})
        class Store:
            def __init__(self):self.data={}
            def put_object(self,Key,Body,**kw):self.data[Key]=Body
            def get_object(self,Key,**kw):return {'Body':io.BytesIO(self.data[Key])}
            def generate_presigned_url(self,operation,Params,**kw):return 'https://example.test/'+Params['Key']
        class Lambda:
            def invoke(self,**kwargs):return {'StatusCode':202}
            def stop_runtime_session(self,**kwargs):pass
        store=Store();client=Lambda()
        for key,value in [('jobs/source/result.json',source),('jobs/source/status.json',{'status':'completed'}),('library/dallas-practice.json',{'key':'videos/input.mp4','sha256':review['videoSha256']})]:store.data[key]=json.dumps(value).encode()
        boto=types.SimpleNamespace(client=lambda name,**kw:store if name=='s3' else client)
        with patch.dict(sys.modules,{'boto3':boto}),patch.dict(os.environ,{'AGENT_RUNTIME_ARN':'test','TEAM_KEY':'test','WORKER_NAME':'test'}):
            spec=importlib.util.spec_from_file_location('review_test_handler',ROOT/'cloud/api/handler.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
            event={'rawPath':'/api/presentations','requestContext':{'http':{'method':'POST'}},'headers':{},'body':json.dumps({'sourceJob':'source','review':review})}
            self.assertEqual(h.handler(event,None)['statusCode'],401)
            event['headers']={'x-team-key':'test'}
            reply=h.handler(event,None);self.assertEqual(reply['statusCode'],202,reply);job=json.loads(reply['body'])['job']
            def render(r,item,prefix):
                r['presentation'].update(rendered=True,videoKey=prefix+'tactical.mp4');r['tacticalReplay']={'key':prefix+'tactical.mp4'}
                for f in r['presentation']['evidence']:f['imageKey']=prefix+'presentation/'+f['image']
            with patch.object(h,'render_result',render):h.worker({'job':job})
            result=json.loads(store.data['jobs/'+job+'/result.json'])
            self.assertEqual(result['presentationReview']['sourceJob'],'source')
            self.assertEqual(json.loads(store.data['jobs/source/result.json']),source)
            status=json.loads(store.data['jobs/'+job+'/status.json']);self.assertEqual(status['status'],'completed')
            with self.assertRaisesRegex(ValueError,'不能计入'):
                h.game_result({'jobIds':[job],'gameId':'game','team':'独行侠','identities':{}},'test')
            review['videoSha256']='b'*64;event['body']=json.dumps({'sourceJob':'source','review':review})
            self.assertEqual(h.handler(event,None)['statusCode'],400)
