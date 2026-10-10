import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/api'))
from story_direction import build_direction,phase_at
from presentation import build
from test_presentation import verified
from companion import validate_companion
from narration import request_for_result

class StoryDirectionTests(unittest.TestCase):
 def test_automatic_contract_has_same_profile_chapters_and_narrator_input(self):
  r=verified();profile=json.loads((ROOT/'data/reference/dallas-practice-actor-profile.json').read_text())
  companion=validate_companion({'schema':'hidden-impact/companion-v2','source':'verified roster','players':[{'trackId':'lead-x','sourcePlayerId':'1629655','jersey':'21'}]},2.5)
  r['deepData']={'videoId':r['video']['id'],'official':{'gameId':'0022500701','eventId':666},'companion':companion,'playerProfiles':[profile]}
  p=build(r);a=p['insights']['actorProfile'];self.assertEqual(a['playerId'],'1629655');self.assertEqual(a['finishing']['made'],7)
  self.assertEqual(p['direction']['source'],'verified-event');self.assertIsNotNone(p['direction']['focusWindow'])
  q=request_for_result(r,[{'time':.4}]);self.assertEqual(q['narrationContext']['actorEvidence'],a)
  r['events'][0]['visualVerified']=False;self.assertIsNone(request_for_result(r,[])['narrationContext']['actorEvidence'])
 def test_rejected_or_missing_evidence_has_no_focus_claim(self):
  self.assertIsNone(build_direction({'roles':[]},20)['focusWindow'])
  d=build_direction({'roles':[{}, {}, {}],'insights':{'shotVideoTime':15}},20,{'start':4,'end':10})
  self.assertEqual([phase_at(d,t) for t in (2,6,17)],[0,1,2])
 def test_api_and_runtime_profile_calculations_are_identical(self):
  self.assertEqual((ROOT/'cloud/api/actor_profile.py').read_bytes(),(ROOT/'cloud/agent/actor_profile.py').read_bytes())
if __name__=='__main__':unittest.main()
