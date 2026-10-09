"""Future-route graphics must remain backed by observed same-person, same-scene footage."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from showcase_motion import future_path
class FutureRouteTest(unittest.TestCase):
 def setUp(self):
  self.frames=[];self.matrix=[[1,0,0],[0,1,0],[0,0,1]]
  for i in range(6):
   t=i*.2;x=.2+t*.08;p={'trackId':'hero','court':[x,.5],'x':x-.02,'y':.3,'w':.04,'h':.2,'association':.95}
   self.frames.append({'time':t,'scene':0,'people':[p]})
 def route(self,frames=None):return future_path(frames or self.frames,self.frames[0],self.frames[0]['people'][0],self.matrix,0)
 def test_points_toward_observed_future_not_past(self):
  path,span=self.route();self.assertAlmostEqual(span,1);self.assertGreater(path[-1][0],path[0][0]+80);self.assertAlmostEqual(path[-1][1],path[0][1]);self.assertLessEqual(path[-1][0],.28*1280+1)
 def test_does_not_cross_camera_cut(self):
  for f in self.frames[1:]:f['scene']=1
  self.assertIsNone(self.route())
 def test_does_not_extrapolate_over_missing_track(self):
  self.assertIsNone(self.route([self.frames[0],*self.frames[3:]]))
  for f in self.frames[1:]:f['people'][0]['trackId']='different'
  self.assertIsNone(self.route())
 def test_stationary_player_has_no_fabricated_direction(self):
  for f in self.frames:f['people'][0]['court']=[.2,.5]
  self.assertIsNone(self.route())
if __name__=='__main__':unittest.main()
