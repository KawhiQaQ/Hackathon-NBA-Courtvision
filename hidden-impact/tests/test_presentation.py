import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from presentation import build,insights,motion
from playmaking import candidates
from candidate_review import apply,finalize


def fixture():
    roster=[dict(id=k,label=name,team=t,role=role) for k,name,t,role in [('lead-x','甲队接应者','A','offense'),('finish-y','甲队终结者','A','offense'),('guard-z','乙队防守者','B','defense')]]
    frames=[]
    for i in range(25):
        t=i/10; handler='lead-x' if i<12 else 'finish-y'
        coords=[(4,7),(9,7),(6.5-min(t,1.2),7)]
        people=[dict(trackId=p['id'],team=p['team'],x=.2+j*.25+t*.01,y=.3,w=.06,h=.3,court=list(xy),ball='on' if p['id']==handler else 'off',confidence=.98,association=.97) for j,(p,xy) in enumerate(zip(roster,coords))]
        frames.append(dict(time=t,scene=0,active=True,handler=handler,people=people))
    vision=dict(frames=frames,roster=roster,aspectRatio=16/9)
    events=candidates(roster,vision)
    players=[dict(p,status='candidate' if p['id']=='lead-x' else 'observed',score=events[0]['score'] if p['id']=='lead-x' else None,eventIds=[events[0]['id']] if p['id']=='lead-x' else []) for p in roster]
    result=dict(scoringVersion='temporal-impact-v5',version='basketball-roster-v3',video={'id':'arbitrary-clip','duration':2.5,'title':'甲队对乙队'},vision=vision,events=events,players=players,model='test-double',modelInvoked=False,
        narration={'schema':'hidden-impact/timed-narration-v1','status':'generated','source':'test-double','modelInvoked':False,'segments':[
            {'start':0,'end':1.2,'title':'接应推进','text':'接应者迎球，防守者靠近。','frameTimes':[0,.8]},
            {'start':1.2,'end':2.5,'title':'转移球权','text':'球权转向外线队友。','frameTimes':[1.2,2.1]}]})
    return result


def verified():
    r=fixture();e=r['events'][0]
    return finalize(apply(r,[dict(id=e['id'],onBall=True,samePlayer=True,isShooter=False,passObserved=True,beneficiaryIsShooter=True,defenderResponds=True)]))


class PlaymakingTests(unittest.TestCase):
    def test_observed_handoff_is_candidate_not_automatic_mvp(self):
        r=fixture();self.assertEqual(r['events'][0]['actionType'],'draw-kick')
        self.assertEqual(build(r)['status'],'insufficient')
        good=verified();self.assertEqual(good['events'][0]['actorTrackId'],'lead-x')
        self.assertEqual(build(good)['actor']['id'],'lead-x')
    def test_same_possession_and_camera_cut_do_not_create_pass(self):
        for mode in ['holder','cut','unknown']:
            r=fixture()
            for f in r['vision']['frames']:
                if mode=='holder':f['handler']='lead-x'
                elif mode=='unknown':f['handler']=None
                else:f['scene']=0 if f['time']<1.2 else 1
            self.assertFalse(candidates(r['vision']['roster'],r['vision']))
    def test_every_visual_pass_check_is_required(self):
        for field in ['onBall','samePlayer','passObserved','beneficiaryIsShooter','defenderResponds']:
            r=fixture();c=dict(id=r['events'][0]['id'],onBall=True,samePlayer=True,isShooter=False,passObserved=True,beneficiaryIsShooter=True,defenderResponds=True);c[field]=None
            self.assertFalse(finalize(apply(r,[c]))['events'],field)
    def test_visual_contradiction_vetoes_high_geometric_offball_score(self):
        for key in ['defenderResponds','beneficiaryIsShooter']:
            r=fixture();r['events'][0]['actionType']='decoy'
            c=dict(id=r['events'][0]['id'],onBall=False,samePlayer=True,isShooter=False)
            c[key]=False
            self.assertFalse(finalize(apply(r,[c]))['events'])
    def test_aligned_shot_requires_matching_outcome_not_an_earlier_pass(self):
        for observed in [None, .1, 2.3]:
            r=fixture();r['deepData']={'alignment':{'shotVideoTime':2.3}}
            c=dict(id=r['events'][0]['id'],onBall=True,samePlayer=True,isShooter=False,passObserved=True,beneficiaryIsShooter=True,defenderResponds=True,observedShotTime=observed)
            self.assertEqual(bool(finalize(apply(r,[c]))['events']),observed==2.3)
    def test_review_keeps_shot_frames_when_actor_leaves_view(self):
        import base64,io
        from PIL import Image
        from candidate_review import prepare
        r=fixture();r['deepData']={'alignment':{'shotVideoTime':3.5}}
        event=r['events'][0];event.update(start=0,end=1)
        r['vision']['frames'].extend([dict(time=t,scene=0,people=[]) for t in [3,4]])
        buf=io.BytesIO();Image.new('RGB',(128,72)).save(buf,format='JPEG')
        frames=[dict(time=t,image=base64.b64encode(buf.getvalue()).decode()) for t in [0,.5,1,3,4]]
        candidate=prepare(r,frames,[event])['candidates'][0]
        self.assertEqual(candidate['shotVideoTime'],3.5)
        self.assertEqual([f['time'] for f in candidate['frames'] if f['phase']=='outcome'],[3,4])

    def test_explicit_shooter_never_becomes_hidden_mvp(self):
        r=fixture();c=dict(id=r['events'][0]['id'],onBall=True,samePlayer=True,isShooter=True,passObserved=True,beneficiaryIsShooter=True,defenderResponds=True)
        self.assertFalse(finalize(apply(r,[c]))['events'])
    def test_rejected_higher_event_does_not_leave_inflated_score(self):
        r=verified();r['players'][0]['score']=99
        r=finalize(r);self.assertEqual(r['players'][0]['score'],r['events'][0]['score'])


class PresentationTests(unittest.TestCase):
    def test_unconfirmed_mvp_still_has_factual_data_broadcast_without_fake_roles(self):
        r=fixture();r['events']=[]
        r['deepData']={'videoId':r['video']['id'],'official':{'gameId':'g','eventId':2,'playerId':'p','shot':{'value':.3,'shotType':'2分投篮','success':0}}}
        p=build(r)
        self.assertEqual(p['status'],'ready');self.assertEqual(p['analysisStatus'],'unconfirmed-mvp')
        self.assertEqual(p['roles'],[]);self.assertIsNone(p['score']);self.assertIsNone(p['actor']['id'])
        self.assertTrue(p['evidence']);self.assertTrue(all(not f['people'] and f['heroArrow'] is None for f in r['presentationMotion']['frames']))
    def test_generic_contract_contains_real_segments_and_annotated_frame_requests(self):
        r=verified();p=build(r)
        self.assertEqual(p['mode'],'analysis');self.assertEqual(p['score'],r['events'][0]['score'])
        self.assertEqual(p['insights']['narration'],r['narration'])
        self.assertEqual([f['time'] for f in p['evidence']],[.8,2.1])
        self.assertEqual([x['id'] for x in p['roles']],['lead-x','finish-y','guard-z'])
        self.assertNotIn('44号',json.dumps(p,ensure_ascii=False));self.assertNotIn('demo/',json.dumps(p))
        self.assertTrue(any(f['heroArrow'] for f in r['presentationMotion']['frames']))
        self.assertTrue(all(len(f['people'])==3 for f in r['presentationMotion']['frames']))
    def test_missing_narration_uses_measurements_without_claiming_model(self):
        r=verified();r['narration']={'status':'unavailable','segments':[]};p=build(r)
        self.assertEqual(p['insights']['narration']['segments'],[])
        self.assertTrue(all(f['source']=='measured-observation' for f in p['evidence']))
    def test_missing_people_keep_identity_not_fictional_positions_or_routes(self):
        r=verified()
        for f in r['vision']['frames']:
            if .3<f['time']<1.5:f['people']=[p for p in f['people'] if p['trackId']!='lead-x']
        m=motion(r,r['events'][0],fps=10);frame=m['frames'][10]
        self.assertTrue(frame['people'][0]['offscreen']);self.assertIsNone(frame['heroArrow'])
    def test_scene_cut_does_not_interpolate_or_preview_across_cut(self):
        r=verified()
        for f in r['vision']['frames']:
            if f['time']>=1.2:f['scene']=1
        m=motion(r,r['events'][0],fps=20)
        self.assertIsNone(m['frames'][23]['heroArrow'])
    def test_baseline_requires_matching_full_shooter_data(self):
        r=verified();r['deepData']={'videoId':r['video']['id'],'official':{'gameId':'g','eventId':2,'playerId':'p','shot':{'value':.3,'shotType':'2分投篮','success':0}}}
        out=insights(r);self.assertEqual(out['shot']['points'],2);self.assertFalse(out['shot']['made']);self.assertIsNone(out['shot']['baseline'])
        r['deepData']['playerShots']={'gameId':'g','playerId':'p','shotList':[{'shotType':'2分投篮','value':.3},{'shotType':'2分投篮','value':.5},{'shotType':'3分投篮','value':.9}]}
        self.assertEqual(insights(r)['shot']['baseline'],.4)
        r['deepData']['playerShots']['playerId']='wrong';self.assertIsNone(insights(r)['shot']['baseline'])
        r['deepData']['videoId']='other';self.assertIsNone(insights(r)['shot'])
    def test_review_rejects_derived_showcase_too(self):
        from review import reviewed_result,REJECTIONS
        r=verified();build(r);r['job']=next(iter(REJECTIONS));r['tacticalReplay']={'url':'bad'}
        out=reviewed_result(r)
        for key in ['presentation','presentationMotion','narration','tacticalReplay']:self.assertNotIn(key,out)
    def test_real_renderer_exports_full_clip_story_images_and_cjk(self):
        import subprocess
        from render_video import ffmpeg,render
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);source=directory/'input.mp4';r=verified();build(r,fps=10)
            subprocess.run([ffmpeg(),'-v','error','-f','lavfi','-i','color=c=gray:s=320x180:r=10:d=2.5','-c:v','libx264',str(source)],check=True)
            output=directory/'replay.mp4';meta=render(source,r,output)
            self.assertEqual(meta['start'],0);self.assertEqual(meta['frameCount'],25)
            for f in r['presentation']['evidence']:
                with Image.open(directory/f['image']) as im:self.assertEqual(im.size,(960,684))
            self.assertGreater(output.stat().st_size,1000)

if __name__=='__main__':unittest.main()
