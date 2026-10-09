"""Every displayed frame retains three identities and exactly one direction cue."""
import json,math,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from showcase_motion import BroadcastRenderer,W,H
class ContinuityTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.result=json.loads((ROOT/'web/demo/analysis.json').read_text())
 def test_no_role_or_arrow_dropouts(self):
  motion=self.result['presentationMotion'];frames=motion['frames']
  self.assertGreaterEqual(len(frames),404)
  for f in frames:
   self.assertEqual({p['trackId'] for p in f['people']},{'P6','P1','P30'})
   path=f['heroArrow']['points'];self.assertGreater(math.dist(path[0],path[-1]),85)
   self.assertTrue(all(math.isfinite(x) and math.isfinite(y) and 0<=x<=1280 and 0<=y<=720 for x,y in path))
 def test_exit_docks_identity_instead_of_freezing_on_another_player(self):
  for f in self.result['presentationMotion']['frames']:
   hero=f['people'][0]
   if f['time']>=11.4:self.assertTrue(hero['offscreen']);self.assertGreater(hero['x'],.9)
 def test_renderer_draws_only_hero_arrow_even_through_previous_gaps(self):
  renderer=BroadcastRenderer(self.result);self.assertEqual(len(renderer.roles),3)
  for t in [0,3,5,6.5,8.25,10.5,11.6,13.3]:
   with patch('showcase_motion.draw_future_arrow') as arrow:
    renderer.render(bytes(W*H*3),t);self.assertEqual(arrow.call_count,1)
if __name__=='__main__':unittest.main()
