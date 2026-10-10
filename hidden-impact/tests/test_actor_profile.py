import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/api'))
from actor_profile import build_profile
from broadcast import card_at
class ActorProfileTests(unittest.TestCase):
 def setUp(self):
  self.profile=json.loads((ROOT/'data/reference/dallas-practice-actor-profile.json').read_text())
  self.r=dict(video={'id':'v'},deepData={'videoId':'v','official':{'gameId':'0022500701','eventId':666},'playerProfiles':[self.profile]})
 def test_real_official_values_and_pre_possession_shots(self):
  p=build_profile(self.r,'1629655');self.assertEqual(p['creation'],.33);self.assertEqual(p['scoring'],.24)
  f=p['finishing'];self.assertEqual((f['made'],f['sampleCount']),(7,8));self.assertAlmostEqual(f['expected'],.741375)
  extra=copy.deepcopy(self.profile['shots']['shotList'][0]);extra['eventId']=700
  self.profile['shots']['shotList'].append(extra)
  self.assertEqual(build_profile(self.r,'1629655')['finishing']['sampleCount'],8)
 def test_no_cross_player_game_or_video_profile(self):
  self.assertIsNone(build_profile(self.r,'1642843'))
  self.r['deepData']['official']['gameId']='other';self.assertIsNone(build_profile(self.r,'1629655'))
  self.r['deepData']['videoId']='other';self.assertIsNone(build_profile(self.r,'1629655'))
 def test_component_comparison_does_not_claim_causal_uplift(self):
  p=build_profile(self.r,'1629655');info={'actorProfile':p,'shotVideoTime':17.3,'shot':{'probability':.51}}
  c=card_at(info,3,21.55);self.assertEqual(c['kind'],'actor-creation');self.assertIsNone(c['delta'])
  c=card_at(info,7.5,21.55);self.assertEqual(c['kind'],'actor-finishing');self.assertEqual(c['domain'],[0,100]);self.assertEqual(c['headline'],'7 / 8')
  self.assertEqual(card_at(info,16,21.55)['kind'],'shot')
 def test_bad_row_ids_are_excluded(self):
  self.profile['leverage']['PLAYERID']='wrong';self.profile['shots']['shotList'][0]['playerId']='wrong'
  p=build_profile(self.r,'1629655');self.assertIsNone(p['creation']);self.assertEqual(p['finishing']['sampleCount'],7)
 def test_three_point_threat_and_missing_expected_values(self):
  self.profile['shots']['shotList']=[dict(playerId='1629655',gameId='0022500701',eventId=i,shotType='3分投篮',success=1,value=None) for i in [1,2,3]]
  self.profile['shots']['shotList'].append(dict(self.profile['shots']['shotList'][0]))
  p=build_profile(self.r,'1629655');f=p['shooting']['three']
  self.assertEqual(f['sampleCount'],3);self.assertEqual(f['made'],3);self.assertIsNone(f['expected'])
  c=card_at({'actorProfile':p,'shotVideoTime':17},9,20)
  self.assertEqual(c['headlineUnit'],'三分命中');self.assertEqual(len(c['rows']),1)
if __name__=='__main__':unittest.main()
