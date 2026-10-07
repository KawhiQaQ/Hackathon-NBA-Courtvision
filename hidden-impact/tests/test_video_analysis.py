import base64,copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/agent'))
from logic import validate_payload,normalize_result
class VideoAnalysisTests(unittest.TestCase):
 def setUp(self):
  self.payload={'video':{'id':'test','title':'test','duration':10},'frames':[{'time':t,'image':base64.b64encode(b'\xff\xd8test').decode()} for t in [1,2,3]],'deepData':{'videoId':'test','official':{'playerId':'1','rosterGravity':[{'id':'1'},{'id':'2'}]}}}
  self.event={'title':'掩护','start':1,'end':3,'actor':'队友','actorPlayerId':'2','confidence':'high','observations':[{'time':1,'text':'队友站位','marks':[]},{'time':2,'text':'防守人开始移动','marks':[]},{'time':3,'text':'接球出手','marks':[]}],'rubric':{'screen':[0],'defenderShift':[0,1],'spaceCreated':[1],'beneficiary':[2]}}
 def norm(self):return normalize_result({'overview':'test','events':[self.event]},self.payload)
 def test_shooter_is_never_hidden_contributor(self):
  self.event['actorPlayerId']='1';self.assertEqual(self.norm()['events'],[])
 def test_score_requires_actual_cited_evidence(self):
  e=self.norm()['events'][0];self.assertEqual(e['score'],45);self.assertEqual(e['components'][0]['points'],0);self.assertEqual(e['components'][2]['points'],0)
 def test_low_confidence_abstains(self):
  self.event['confidence']='low';self.assertIsNone(self.norm()['events'][0]['score'])
 def test_no_synthetic_frame_times(self):
  self.event['observations']=[{'time':1.5,'text':'编造时间','marks':[]},{'time':1,'text':'唯一合法','marks':[]}];self.assertEqual(self.norm()['events'],[])
 def test_invalid_boxes_removed(self):
  self.event['observations'][0]['marks']=[{'label':'bad','role':'actor','x':.9,'y':.1,'w':.3,'h':.3}];self.assertEqual(self.norm()['events'][0]['observations'][0]['marks'],[])
 def test_gravity_not_part_of_score(self):
  before=self.norm()['events'][0]['score'];self.payload['deepData']['official']['rosterGravity'][1]['gravity']={'OFF_BALL_PERIM_GRAV':999};self.assertEqual(before,self.norm()['events'][0]['score'])
 def test_unordered_frames_rejected(self):
  self.payload['frames'].reverse()
  with self.assertRaises(ValueError):validate_payload(self.payload)
 def test_mismatched_video_data_rejected(self):
  self.payload['deepData']['videoId']='another'
  with self.assertRaises(ValueError):validate_payload(self.payload)
 def test_no_events_is_valid(self):
  self.assertEqual(normalize_result({'events':[]},self.payload)['events'],[])
if __name__=='__main__':unittest.main()
