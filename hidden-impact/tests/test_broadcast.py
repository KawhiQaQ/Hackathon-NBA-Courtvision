import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from broadcast import card_at

class BroadcastTests(unittest.TestCase):
 def data(self):
  return dict(shotVideoTime=10,shooter='球员',shot=dict(probability=.51,baseline=.4,sampleCount=4,deltaPercentagePoints=11,expectedPoints=1.02,made=True,points=2),gravity=dict(player='球员',scope='赛季',axes=[dict(key='OFF_BALL_PERIM_GRAV',value=-2)]))
 def test_phase_and_outcome_are_aligned(self):
  d=self.data();self.assertEqual(card_at(d,2,20)['kind'],'gravity');self.assertEqual(card_at(d,9,20)['kind'],'shot')
  self.assertFalse(any('命中 +' in s for s in card_at(d,9,20)['lines']))
  self.assertIn('命中 +2 分',card_at(d,12,20)['lines'])
 def test_absent_alignment_does_not_claim_live_outcome(self):
  d=self.data();d.pop('shotVideoTime');c=card_at(d,19,20)
  self.assertIn('数据回看',c['title']);self.assertFalse(any('命中 +' in s for s in c['lines']))
 def test_missing_or_invalid_is_not_fabricated(self):
  self.assertIsNone(card_at({},2,20));d=self.data();d['shot']['probability']=float('nan')
  self.assertIsNone(card_at(d,15,20))

if __name__=='__main__':unittest.main()
