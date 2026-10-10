import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/api'))
from game_summary import aggregate,identity,round_score,measured_action
from companion import validate_companion
from presentation import build
from test_presentation import verified


def round_(key,jersey='23',score=60,game='game',team='尼克斯'):
 return dict(gameId=game,team=team,roundKey=key,videoId='v-'+key,identity={'jersey':jersey,'confirmed':True},impact={'score':score,'coverage':1})

class GameSummaryTests(unittest.TestCase):
 def test_weighted_score_missing_and_outcomes(self):
  data={'probability':.6,'baseline':.4,'made':False}
  self.assertEqual(round_score(80,data)['score'],79)
  data['made']=True;self.assertEqual(round_score(80,data)['score'],79)
  self.assertEqual(round_score(80,{})['score'],80)
  self.assertEqual(round_score(80,{})['coverage'],.65)
  self.assertLess(round_score(80,{'probability':.3,'baseline':.6})['score'],round_score(80,data)['score'])
  for value in [None,0,True,float('nan'),float('inf'),-1,101]:self.assertIsNone(round_score(value,data)['score'])
  self.assertEqual(round_score(80,{'probability':float('nan'),'baseline':.5})['coverage'],.65)
 def test_duplicate_upload_not_extra_mvp(self):
  rounds=[round_('a'),round_('b'),round_('a')];rounds[-1]['videoId']='new-upload-id'
  s=aggregate(rounds,'game','尼克斯');self.assertEqual(s['creditedRounds'],2);self.assertEqual(s['roundCount'],2)
  self.assertEqual(s['winner']['total'],120);self.assertEqual(s['winner']['average'],60);self.assertEqual(s['winner']['wins'],2)
 def test_tracks_do_not_cross_match_unconfirmed_identities(self):
  rows=[round_('a'),round_('b')];rows[1]['identity']={'confirmed':False,'jersey':'P1'}
  s=aggregate(rows,'game','尼克斯');self.assertEqual(s['creditedRounds'],1);self.assertEqual(s['roundCount'],2)
  self.assertNotEqual(identity('尼克斯','00')['key'],identity('尼克斯','0')['key'])
  with self.assertRaises(ValueError):identity('尼克斯','P1')
  with self.assertRaises(ValueError):identity('尼克斯','２３')
 def test_wrong_game_team_empty_rejected(self):
  for rows in [[round_('a',game='other')],[round_('a',team='马刺')],[],[None],[{**round_('a'),'identity':'bad'}]]:
   with self.assertRaises(ValueError):aggregate(rows,'game','尼克斯')
  with self.assertRaises(ValueError):aggregate([round_('a')],'game','')
 def test_tie_does_not_arbitrarily_award_one_player(self):
  rows=[round_('a','23'),round_('b','32')];s=aggregate(rows,'game','尼克斯')
  self.assertTrue(s['tie']);self.assertIsNone(s['winner']);self.assertEqual(len(s['leaders']),2)
  self.assertEqual(s['ranking'],aggregate(rows[::-1],'game','尼克斯')['ranking'])
 def test_jersey_and_shot_context_work_without_tracking(self):
  data={'schema':'hidden-impact/companion-v2','source':'test-feed','players':[{'trackId':'lead-x','sourcePlayerId':'abc','jersey':'44'}],
   'shotContext':{'gameId':'game','team':'尼克斯','eventId':2,'playerId':'finish','shooter':'尼克斯 8号',
    'shot':{'value':.6,'shotType':'3分投篮','success':1},'playerShots':{'gameId':'game','playerId':'finish','shotList':[{'value':.4,'shotType':'3分投篮'},{'value':.6,'shotType':'3分投篮'}]}}}
  clean=validate_companion(data,3);r=verified();r['deepData']={'videoId':r['video']['id'],'official':clean['shotContext'],'companion':clean,'opportunitySource':'test-feed'}
  p=build(r);self.assertEqual(p['insights']['shot']['baseline'],.5);self.assertEqual(p['identity']['jersey'],'44');self.assertEqual(p['impact']['coverage'],1)
  self.assertEqual(p['insights']['probabilitySource'],'配套数据预期命中率')
  for change in ['wrongGame','badProbability','badJersey']:
   bad=copy.deepcopy(data)
   if change=='wrongGame':bad['shotContext']['playerShots']['gameId']='other'
   elif change=='badProbability':bad['shotContext']['shot']['value']=float('nan')
   else:bad['players'][0]['jersey']='P6'
   with self.assertRaises(ValueError):validate_companion(bad,3)
 def test_five_real_assets_and_reproducible_rankings(self):
  s=json.loads((ROOT/'tests/fixtures/legacy-showcase/game.json').read_text());self.assertEqual(len(s['rounds']),5)
  self.assertEqual(len({r['videoId'] for r in s['rounds']}),5)
  again=aggregate(s['rounds'],s['gameId'],s['team']);self.assertEqual(s['ranking'],again['ranking'])
  for r in s['rounds']:
   self.assertEqual(r['impact'],round_score(r['score'],r['insights']['shot']))
   self.assertEqual(len(r['roles']),3);self.assertGreaterEqual(len(r['evidence']),4)
   self.assertNotIn('阿努诺比',json.dumps({'roles':r['roles'],'evidence':r['evidence'],'narration':r['insights']['narration']},ensure_ascii=False))
   for asset in [r['video'],r['original'],*[f['image'] for f in r['evidence']]]:
    p=ROOT/'tests/fixtures/legacy-showcase'/asset.split('?')[0];self.assertTrue(p.is_file(),p);self.assertGreater(p.stat().st_size,5000)
   self.assertFalse(r['generation']['modelInvoked'])
 def test_measured_action_is_bounded_not_constant(self):
  low=[dict(time=t,engagement=5,separation=.3) for t in [0,1,2]]
  high=[dict(time=t,engagement=1,separation=1+t) for t in [0,1,2]]
  self.assertLess(measured_action(low),measured_action(high));self.assertLessEqual(measured_action(high),100)

class GameExportTest(unittest.TestCase):
 def test_generic_cli_exports_two_rounds_and_real_media(self):
  import tempfile,subprocess
  sys.path.insert(0,str(ROOT/'scripts'))
  from export_game import export_game
  from render_video import ffmpeg
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);source=d/'input.mp4'
   subprocess.run([ffmpeg(),'-v','error','-f','lavfi','-i','color=c=gray:s=320x180:r=24:d=2.5','-c:v','libx264',str(source)],check=True)
   entries=[]
   for i in range(2):
    r=verified();r['video']['id']='new-clip-'+str(i)
    (d/f'analysis-{i}.json').write_text(json.dumps(r))
    entries.append({'analysis':f'analysis-{i}.json','video':'input.mp4','jersey':'07'})
   (d/'project.json').write_text(json.dumps({'gameId':'new-game','team':'新球队','rounds':entries}))
   result=export_game(d/'project.json',d/'out');self.assertEqual(result['creditedRounds'],2);self.assertEqual(result['winner']['jersey'],'07')
   for r in result['rounds']:
    self.assertTrue((d/'out'/r['video']).is_file());self.assertTrue(all((d/'out'/f['image']).is_file() for f in r['evidence']))
    self.assertEqual(r['generation']['narration']['source'],'test-double')
    self.assertNotIn('demo/',json.dumps(r));self.assertTrue(r['rendered'])
