import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/agent'))
from basketball import ground_roster,player_reports

def fixture():
 frames=[]
 for i in range(10):
  people=[{'trackId':tid,'x':x,'y':.3,'w':.04,'h':.2,'confidence':.96,'association':.95} for tid,x in [('T1',.4),('T2',.45+i*.025),('T3',.43),('T9',.1)]]
  frames.append({'time':i*.2,'scene':0,'anchor':True,'people':people})
 raw={'players':[{'id':pid,'label':pid,'team':team,'role':role,'observations':[{'time':f['time'],'trackId':tid,'ball':ball,'note':'位置观察'} for f in frames]} for pid,tid,team,role,ball in [('P1','T1','A','offense','off'),('P2','T2','A','offense','on'),('P3','T3','B','defense','off')]]}
 return raw,{'frames':frames,'aspectRatio':16/9}
class BasketballTests(unittest.TestCase):
 def test_nonplayer_removed_and_every_recognized_player_reported(self):
  raw,v=fixture();roster,v=ground_roster(raw,v);reports,events=player_reports(roster,v)
  self.assertEqual(len(reports),3);self.assertEqual(v['filter']['excludedDetections'],10);self.assertFalse(any(p['trackId']=='T9' for f in v['frames'] for p in f['people']))
  self.assertTrue(all(r['evidence'] for r in reports));self.assertTrue(events);self.assertGreater(next(r['score'] for r in reports if r['id']=='P1'),0)
 def test_invalid_detector_reference_is_not_a_player(self):
  raw,v=fixture();raw['players'][0]['observations']=[{'time':0,'trackId':'T999'}];roster,v=ground_roster(raw,v);self.assertNotIn('P1',[p['id'] for p in roster])
 def test_defenders_do_not_receive_attack_score(self):
  raw,v=fixture();roster,v=ground_roster(raw,v);reports,_=player_reports(roster,v);p=next(p for p in reports if p['id']=='P3');self.assertEqual(p['status'],'defense');self.assertIsNone(p['score'])
 def test_static_video_has_reports_and_zero_not_fake_credit(self):
  raw,v=fixture()
  for f in v['frames']:f['people'][1]['x']=.5
  roster,v=ground_roster(raw,v);reports,events=player_reports(roster,v);self.assertFalse(events);self.assertEqual(next(p['score'] for p in reports if p['id']=='P1'),0)
 def test_ballhandler_excluded_from_offball_credit(self):
  raw,v=fixture()
  for o in raw['players'][0]['observations']:o['ball']='on'
  roster,v=ground_roster(raw,v);reports,events=player_reports(roster,v);self.assertFalse(events)
 def test_no_identity_propagation_across_scene_or_long_gap(self):
  raw,v=fixture();raw['players'][0]['observations']=raw['players'][0]['observations'][:1];v['frames'][-1]['scene']=1
  roster,v=ground_roster(raw,v);self.assertFalse(any(p['trackId']=='P1' for p in v['frames'][-1]['people']));self.assertFalse(any(p['trackId']=='P1' for p in v['frames'][-2]['people']))
 def test_static_spacing_support_requires_known_ballhandler(self):
  raw,v=fixture()
  for f in v['frames']:f['people'][1]['x']=.84
  roster,grounded=ground_roster(raw,v);reports,_=player_reports(roster,grounded);p=next(p for p in reports if p['id']=='P1');self.assertGreater(p['spacingSupport']['points'],0);self.assertLessEqual(p['score'],20)
  for o in raw['players'][1]['observations']:o['ball']='unknown'
  roster,grounded=ground_roster(raw,v);reports,_=player_reports(roster,grounded);self.assertNotIn('spacingSupport',next(p for p in reports if p['id']=='P1'))
 def test_current_game_jersey_colors_reject_cross_team_identity_switch(self):
  raw,v=fixture()
  for f in v['frames']:
   for p in f['people']:p['jerseyColor']=[.88,.88,.86] if p['trackId'] in ['T1','T2'] else [.12,.13,.15]
  v['frames'][4]['people'][0]['jerseyColor']=[.12,.13,.15]
  roster,grounded=ground_roster(raw,v)
  self.assertTrue(grounded['jerseyCalibration']['active']);self.assertEqual(grounded['filter']['jerseyRejected'],1);self.assertNotIn('P1',[p['trackId'] for p in grounded['frames'][4]['people']])
 def test_already_distant_defender_is_not_credited_as_released_matchup(self):
  raw,v=fixture()
  for i,f in enumerate(v['frames']):f['people'][1]['x']=.76+i*.005
  for o in raw['players'][1]['observations']:o['ball']='unknown'
  roster,grounded=ground_roster(raw,v);reports,events=player_reports(roster,grounded);self.assertFalse(events)
 def test_unknown_possession_is_not_zero_contribution(self):
  raw,v=fixture()
  for o in raw['players'][1]['observations']:o['ball']='unknown'
  for f in v['frames']:f['people'][1]['x']=.5
  roster,grounded=ground_roster(raw,v);reports,events=player_reports(roster,grounded)
  p=next(p for p in reports if p['id']=='P1')
  self.assertIsNone(p['score']);self.assertEqual(p['status'],'insufficient');self.assertEqual(p['diagnostics']['knownHandlerFrames'],0)
 def test_sparse_three_person_coverage_cannot_be_reported_as_zero(self):
  raw,v=fixture()
  for f in v['frames']:
   if f['time']>.2:f['people']=[p for p in f['people'] if p['trackId']!='T3']
  roster,grounded=ground_roster(raw,v);reports,_=player_reports(roster,grounded)
  p=next(p for p in reports if p['id']=='P1');self.assertIsNone(p['score']);self.assertEqual(p['diagnostics']['evaluatedWindows'],0)
 def test_uncertain_actor_ball_state_cannot_earn_dynamic_credit(self):
  raw,v=fixture()
  for i,o in enumerate(raw['players'][0]['observations']):o['ball']='off' if i==3 else 'unknown'
  roster,grounded=ground_roster(raw,v);reports,events=player_reports(roster,grounded)
  self.assertFalse(events);self.assertIsNone(next(p for p in reports if p['id']=='P1')['score'])
 def test_real_report_missing_ballhandler_is_rescored_without_rewriting_original(self):
  import json,copy
  sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
  from review import reviewed_result
  path=Path(__file__).resolve().parents[1]/'tests/fixtures/diagnose-7a9487f5127879232560e8984f57782c.json'
  self.assertTrue(path.exists(),'Committed regression fixture missing')
  original=json.loads(path.read_text());before=copy.deepcopy(original);fixed=reviewed_result(original)
  self.assertEqual(original,before);self.assertFalse(fixed['events'])
  for p in fixed['players']:
   if p['role']=='offense':self.assertIsNone(p['score']);self.assertEqual(p['status'],'insufficient')
