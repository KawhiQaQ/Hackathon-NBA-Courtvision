import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from narration_facts import facts_for
from actor_profile import build_profile

class NarrationFactsTests(unittest.TestCase):
    def payload(self):
        profile=json.loads((ROOT/'data/reference/dallas-practice-actor-profile.json').read_text())
        deep={'videoId':'v','official':{'playerId':'shooter','gameId':'0022500701','eventId':666,'shot':{'value':.51,'shotType':'2分投篮'}},'alignment':{'shotVideoTime':17},'playerProfiles':[profile],
              'playerShots':{'playerId':'shooter','gameId':'0022500701','shotList':[{'value':v,'shotType':'2分投篮'} for v in [.49,.51]]}}
        p={'video':{'id':'v','duration':21.55},'deepData':deep}
        p['narrationContext']={'actorEvidence':build_profile(p,'1629655')}
        return p
    def test_actual_source_values_and_distinct_statistical_scopes(self):
        p=self.payload();facts={f['id']:f for f in facts_for(p)}
        self.assertEqual(facts['actor-creation']['values']['creation'],.33)
        prior=facts['actor-prior-finishing'];self.assertIn('8投7中',prior['text']);self.assertIn('13.4个百分点',prior['text'])
        self.assertAlmostEqual(prior['values']['deltaPercentagePoints'],13.3625)
        self.assertIn('之前',prior['scope'])
        self.assertIn('1.0个百分点',facts['shot-opportunity']['text'])
        self.assertAlmostEqual(facts['shot-opportunity']['values']['baseline'],.5)
    def test_shot_facts_do_not_leak_before_aligned_window(self):
        p=self.payload();p['narrationWindow']={'start':0,'end':4}
        self.assertEqual([f['id'] for f in facts_for(p)],['actor-creation','actor-prior-finishing'])
        p['narrationWindow']={'start':15,'end':18};self.assertIn('shot-opportunity',[f['id'] for f in facts_for(p)])
    def test_missing_or_mismatched_data_never_invents_a_comparison(self):
        p=self.payload();p['deepData']['playerShots']['playerId']='other'
        shot=facts_for(p)[-1];self.assertIsNone(shot['values']['baseline']);self.assertNotIn('均值',shot['text'])
        p['narrationContext']['actorEvidence']=None
        self.assertEqual([f['id'] for f in facts_for(p)],['shot-opportunity'])
        p['deepData']['videoId']='other';self.assertEqual(facts_for(p),[])
    def test_runtime_and_api_share_the_same_fact_contract(self):
        self.assertEqual((ROOT/'cloud/api/narration_facts.py').read_bytes(),(ROOT/'cloud/agent/narration_facts.py').read_bytes())

if __name__=='__main__':unittest.main()
