import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from broadcast import card_at

class BroadcastTests(unittest.TestCase):
 def data(self):
  return dict(shotVideoTime=10,shooter='球员',shot=dict(probability=.51,baseline=.5001578947368421,sampleCount=19,deltaPercentagePoints=999,expectedPoints=1.02,made=True,points=2),gravity=dict(player='球员',scope='赛季',axes=[dict(key='OFF_BALL_PERIM_GRAV',value=-2,teamMedian=3)]))
 def test_phase_and_outcome_are_aligned(self):
  d=self.data();self.assertEqual(card_at(d,2,20)['kind'],'gravity');self.assertEqual(card_at(d,5,20)['kind'],'shot')
  self.assertIsNone(card_at(d,9,20)['outcome'])
  self.assertEqual(card_at(d,12,20)['outcome'],'命中 +2 分')
 def test_absent_alignment_does_not_claim_live_outcome(self):
  d=self.data();d.pop('shotVideoTime');c=card_at(d,19,20)
  self.assertIn('数据回看',c['title']);self.assertIsNone(c['outcome'])
 def test_probability_bars_use_full_scale_and_derived_delta(self):
  c=card_at(self.data(),8,20)
  self.assertEqual(c['domain'],[0,100]);self.assertEqual(len(c['rows']),2)
  self.assertAlmostEqual(c['delta'],.98421052631579)
  self.assertEqual(c['rows'][1]['value'],51)
  self.assertTrue(c['rows'][0]['baseline']);self.assertFalse(c['rows'][1]['baseline'])
 def test_signed_gravity_has_shared_zero(self):
  c=card_at(self.data(),2,20)
  self.assertEqual(c['domain'],[-2,3]);self.assertEqual(c['delta'],-5)
  self.assertIn('非本回合增益',c['context'])
 def test_missing_baseline_does_not_invent_comparison(self):
  for baseline in [None,float('nan'),-1,2,True]:
   d=self.data();d['shot']['baseline']=baseline;c=card_at(d,9,20)
   self.assertEqual(len(c['rows']),1);self.assertIsNone(c['delta'])
 def test_missing_or_invalid_is_not_fabricated(self):
  self.assertIsNone(card_at({},2,20));d=self.data();d['shot']['probability']=float('nan')
  self.assertIsNone(card_at(d,15,20))
 def test_equal_zero_gravity_still_has_valid_scale(self):
  d=self.data();d['gravity']['axes'][0].update(value=0,teamMedian=0)
  c=card_at(d,2,20);self.assertLess(c['domain'][0],c['domain'][1]);self.assertEqual(c['delta'],0)

if __name__=='__main__':unittest.main()
