import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/agent'));sys.path.insert(0,str(ROOT/'cloud/api'))
from impact_score import score_event
from companion import validate_companion
from logic import normalize_hybrid

def fixture():
 frames=[]
 for i in range(5):
  people=[]
  for id,x in [('T1',.4),('T2',.45+i*.045),('T3',.43)]:people.append({'trackId':id,'x':x,'y':.3,'w':.04,'h':.2,'confidence':.95,'association':.95})
  frames.append({'time':1+i*.5,'scene':0,'people':people})
 return {'frames':frames,'aspectRatio':16/9},dict(actorTrackId='T1',beneficiaryTrackId='T2',defenderTrackId='T3',start=1,end=3,actionType='screen')
class HybridTests(unittest.TestCase):
 def test_separation_creates_positive_continuous_score(self):
  v,e=fixture();s=score_event(e,v);self.assertGreater(s['score'],0);self.assertGreater(s['separationGain'],0);self.assertLess(s['score'],s['rawScore'])
 def test_common_camera_translation_and_zoom_do_not_create_gain(self):
  v,e=fixture();expected=score_event(e,v)
  for f in v['frames']:
   for p in f['people']:
    p.update(x=p['x']*.8+.1,y=p['y']*.8+.08,w=p['w']*.8,h=p['h']*.8)
  actual=score_event(e,v);self.assertEqual(actual['score'],expected['score']);self.assertAlmostEqual(actual['separationGain'],expected['separationGain'])
 def test_static_spacing_gets_no_release_or_persistence_points(self):
  v,e=fixture()
  for f in v['frames']:f['people'][1]['x']=.6
  s=score_event(e,v);self.assertEqual(s['score'],0);self.assertEqual(s['components'][0]['points'],0);self.assertEqual(s['components'][2]['points'],0)
 def test_scene_cut_abstains(self):
  v,e=fixture();v['frames'][-1]['scene']=1;self.assertIsNone(score_event(e,v)['score'])
 def test_weak_identity_association_abstains(self):
  v,e=fixture()
  for f in v['frames']:
   for p in f['people']:p['association']=.1
  self.assertIsNone(score_event(e,v)['score'])
 def test_duplicate_roles_abstain(self):
  v,e=fixture();e['actorTrackId']='T2';self.assertIsNone(score_event(e,v)['score'])
 def test_gap_abstains(self):
  v,e=fixture()
  for f,t in zip(v['frames'],[1,1.2,2.7,2.8,3]):f['time']=t
  self.assertIsNone(score_event(e,v)['score'])
 def test_supplied_opportunity_is_separate_from_score(self):
  v,e=fixture();before=score_event(e,v);after=score_event(e,v,{'opportunity':[{'time':1,'expectedPoints':.6},{'time':3,'expectedPoints':1.2}]});self.assertEqual(before['score'],after['score']);self.assertEqual(after['expectedPointsChange'],.6)
 def test_hybrid_never_uses_vlm_coordinates(self):
  v,e=fixture();e.update(offBall=True,confidence='high',observations=[{'time':t,'text':'观察','marks':[{'x':999}]} for t in [1,2,3]])
  p={'vision':v,'frames':[{'time':f['time']} for f in v['frames']],'video':{'id':'test'}}
  out=normalize_hybrid({'events':[e]},p);self.assertEqual(out['events'][0]['observations'][0]['marks'][0]['x'],.4)
 def test_companion_rejects_nonfinite_and_out_of_clip_times(self):
  for t in [float('nan'),-1,11]:
   with self.assertRaises(ValueError):validate_companion({'schema':'hidden-impact/companion-v1','source':'test','opportunity':[{'time':t,'expectedPoints':1}]},10)
