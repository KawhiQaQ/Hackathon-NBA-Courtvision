import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from temporal import reports,ground
from companion import validate_companion

def fixture(moving=True):
 roster=[dict(id=p,label=p,team=t,role=r,summary='',observations=[]) for p,t,r in [('P1','light','offense'),('P2','light','offense'),('P3','dark','defense')]]
 frames=[]
 for i in range(19):
  points=[(4,7),(3+i*.17 if moving else 3,7),(4+i*.04 if moving else 4,7.6+i*.02 if moving else 7.6)]
  people=[dict(trackId=p['id'],team=p['team'],x=.2+i*.003,y=.3,w=.05,h=.2,court=list(xy),ball='on' if j==1 else 'off',confidence=.95,association=.95) for j,(p,xy) in enumerate(zip(roster,points))]
  frames.append(dict(time=i/6,scene=0,active=True,anchor=i%4==0,handler='P2',people=people))
 return roster,dict(frames=frames,aspectRatio=16/9)

class TemporalTests(unittest.TestCase):
 def test_continuous_release_becomes_explainable_event(self):
  r,v=fixture();ps,es=reports(r,v);self.assertTrue(es);e=next(e for e in es if e['actorTrackId']=='P1');self.assertGreater(e['score'],10);self.assertEqual(e['actionType'],'screen');self.assertGreater(e['measurement']['separationAfter'],e['measurement']['separationBefore']);self.assertEqual(len(e['observations']),3)
 def test_pan_without_court_motion_cannot_create_release(self):
  r,v=fixture(False);ps,es=reports(r,v);self.assertFalse(es)
 def test_actor_holds_ball_is_not_offball_candidate(self):
  r,v=fixture()
  for f in v['frames']:
   f['handler']='P1';f['possessionSource']='supplied-tracking'
   for p in f['people']:p['ball']='on' if p['trackId']=='P1' else 'off'
  _,es=reports(r,v);self.assertFalse(any(e['actorTrackId']=='P1' for e in es))
 def test_camera_cut_cannot_be_bridged(self):
  r,v=fixture()
  for i,f in enumerate(v['frames']):f['scene']=i//4
  _,es=reports(r,v);self.assertFalse(es)
 def test_unknown_ball_is_not_zero_score(self):
  r,v=fixture()
  for f in v['frames']:
   f['handler']=None
   for p in f['people']:p['ball']='unknown'
  ps,es=reports(r,v)
  from candidate_review import finalize
  final=finalize({'players':ps,'events':es});self.assertFalse(final['events']);self.assertIsNone(final['players'][0]['score'])
 def test_per_clip_context_does_not_inflate_score(self):
  r,v=fixture();a,e=reports(r,v);b,f=reports(r,v,{'source':'aggregate','gravity':[{'trackId':'P1','time':0,'attentionShare':1}]});self.assertEqual(a[0]['score'],b[0]['score']);self.assertIsNone(f[0]['measurement']['expectedPointsChange'])
 def test_v2_alignment_validated(self):
  d={'schema':'hidden-impact/companion-v2','source':'test','players':[{'trackId':'P1','sourcePlayerId':'abc'}],'frames':[{'time':1,'players':[{'playerId':'abc','x':.5,'y':.3}],'ballHandlerId':'abc'}]};v=validate_companion(d,3);self.assertEqual(v['frames'][0]['players'][0]['x'],.5)
  d['frames'][0]['players'][0]['x']=3
  with self.assertRaises(ValueError):validate_companion(d,3)
 def test_track_from_referee_is_not_kept(self):
  r,v=fixture();v['identitySheets']=[];context={'offenseTeam':'light','attackEnd':2,'identities':[{'id':'P1','kind':'referee','team':'dark'}],'frames':[]};roster,vision=ground(v,context);self.assertFalse(roster);self.assertFalse(any(f['people'] for f in vision['frames']))

class CandidateReviewTests(unittest.TestCase):
 def test_onball_candidate_is_corrected_and_removed(self):
  from candidate_review import apply,finalize
  roster,v=fixture();ps,es=reports(roster,v);v['roster']=roster;r={'players':ps,'events':es,'vision':v};e=es[0]
  fixed=apply(r,[{'id':e['id'],'onBall':True,'samePlayer':None}]);final=finalize(fixed)
  self.assertFalse(any(ev['actorTrackId']==e['actorTrackId'] for ev in final['events']))
  self.assertTrue(any(f.get('possessionSource')=='focused-candidate-vlm-check' for f in fixed['vision']['frames']))
 def test_offball_check_does_not_certify_a_different_beneficiary(self):
  from candidate_review import apply
  roster,v=fixture();ps,es=reports(roster,v);v['roster']=roster;r={'players':ps,'events':es,'vision':v}
  checked=apply(r,[{'id':es[0]['id'],'onBall':False,'samePlayer':True,'isShooter':False}]);self.assertTrue(checked['events'][0]['visualVerified'])
  checked['events'][0]['beneficiaryTrackId']='different'
  again=apply(checked,[]);self.assertFalse(again['events'][0]['visualVerified'])

if __name__=='__main__':unittest.main()

class CacheAndVerificationTests(unittest.TestCase):
 def test_cache_invalidates_on_video_or_anchor_change(self):
  from perception_cache import cache_key
  frames=[{'time':0,'image':'abc'}];a=cache_key('clip','etag-a',frames)
  self.assertEqual(a,cache_key('clip','etag-a',frames))
  self.assertNotEqual(a,cache_key('clip','etag-b',frames))
  self.assertNotEqual(a,cache_key('clip','etag-a',[{'time':0,'image':'different'}]))
 def test_explicit_identity_mismatch_cannot_pass(self):
  from candidate_review import apply,finalize
  roster,v=fixture();ps,es=reports(roster,v);v['roster']=roster
  r=apply({'players':ps,'events':es,'vision':v},[{'id':es[0]['id'],'onBall':False,'samePlayer':False}]);self.assertFalse(finalize(r)['events'])
 def test_spacing_requires_visible_ball_handler(self):
  from candidate_review import apply
  roster,v=fixture();ps,es=reports(roster,v);v['roster']=roster;es[0]['actionType']='spacing'
  r=apply({'players':ps,'events':es,'vision':v},[{'id':es[0]['id'],'onBall':False,'samePlayer':True,'beneficiaryOnBall':None}]);self.assertFalse(r['events'][0]['visualVerified'])

class OutcomeReviewTests(unittest.TestCase):
 def test_later_shooter_is_not_hidden_mvp(self):
  from candidate_review import apply,finalize
  roster,v=fixture();ps,es=reports(roster,v);v['roster']=roster
  r=finalize(apply({'players':ps,'events':es,'vision':v},[{'id':es[0]['id'],'onBall':False,'samePlayer':True,'isShooter':True}]))
  self.assertFalse(r['events']);self.assertEqual(next(p for p in r['players'] if p['id']==es[0]['actorTrackId'])['status'],'shooter')
 def test_unknown_outcome_cannot_certify_mvp(self):
  from candidate_review import apply
  roster,v=fixture();ps,es=reports(roster,v);v['roster']=roster
  r=apply({'players':ps,'events':es,'vision':v},[{'id':es[0]['id'],'onBall':False,'samePlayer':True}]);self.assertFalse(r['events'][0]['visualVerified'])

class ReleaseVetoTests(unittest.TestCase):
 def test_real_later_shooter_cannot_pass_an_incorrect_vlm_verdict(self):
  import json
  from candidate_review import apply,finalize,release_suspects
  root=Path(__file__).resolve().parents[1]
  r=json.loads((root/'tests/fixtures/latest-user-result.json').read_text());e=r['events'][0]
  self.assertIn('P1',release_suspects(r['vision']))
  fixed=finalize(apply(r,[{'id':e['id'],'onBall':False,'isShooter':False,'samePlayer':True}]))
  self.assertFalse(any(e['actorTrackId']=='P1' for e in fixed['events']))
  self.assertEqual(next(p for p in fixed['players'] if p['id']=='P1')['status'],'release-review')
 def test_stationary_ball_or_scene_cut_cannot_trigger_release(self):
  from candidate_review import release_suspects
  people=[dict(trackId='P1',x=.2,y=.3,w=.1,h=.3,association=.9)]
  frames=[dict(time=t,scene=0,people=people,ballCandidates=[dict(x=.25,y=.32,confidence=.9)]) for t in [0,.16,.33]]
  self.assertFalse(release_suspects({'frames':frames}))
  frames[1]['ballCandidates'][0]['y']=.26;frames[1]['scene']=1
  self.assertFalse(release_suspects({'frames':frames}))
