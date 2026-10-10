import sys,unittest,math,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from tactical_board import build_board,board_state,marker_centers
from presentation import arrow_anchor

class TacticalBoardTests(unittest.TestCase):
 def setup_board(self):
  roles=[dict(id=str(i)) for i in range(3)]
  motion=dict(width=1280,height=720,fps=10,frames=[dict(time=i/10,people=[dict(trackId=str(j),x=.2+j*.2+i*.005,y=.3,w=.05,h=.2,scene=0) for j in range(3)]) for i in range(40)])
  manifest=dict(roles=roles,direction={'focusWindow':[0,3.9]},evidence=[{'time':2}])
  return motion,build_board(motion,manifest)
 def test_board_uses_same_positions_and_fixed_viewport(self):
  motion,b=self.setup_board();before=copy.deepcopy(b)
  a,_=board_state(motion,b,.2);z,_=board_state(motion,b,2)
  self.assertEqual(set(a),{'0','1','2'});self.assertGreater(z['0'][0],a['0'][0]);self.assertEqual(before,b)
  self.assertEqual(b['coordinateSystem'],'image-relative')
 def test_arrows_only_at_evidence_and_never_bridge_a_cut_or_missing_player(self):
  motion,b=self.setup_board()
  self.assertFalse(board_state(motion,b,.2)[1]);self.assertTrue(board_state(motion,b,2)[1])
  for f in motion['frames'][21:]:
   f['people'][0]['scene']=1;f['people'][1]['offscreen']=True
  arrows=board_state(motion,b,2)[1]
  self.assertNotIn('0',arrows);self.assertNotIn('1',arrows)
 def test_unlocalized_people_do_not_get_substitute_dots(self):
  motion,b=self.setup_board();motion['frames'][20]['people'][0]['offscreen']=True
  self.assertNotIn('0',board_state(motion,b,2)[0])
 def test_number_badges_separate_without_changing_measured_points(self):
  points={'a':(70,60),'b':(74,60),'c':(160,70)};before=copy.deepcopy(points)
  markers=marker_centers(points,(0,0,280,126))
  self.assertGreaterEqual(math.dist(markers['a'],markers['b']),23.9)
  self.assertEqual(points,before)
 def test_route_begins_within_six_pixels_of_feet_at_1280_width(self):
  p=dict(x=.4,y=.3,w=.07,h=.25);feet=((p['x']+p['w']/2)*1280,(p['y']+p['h'])*720)
  for angle in range(0,360,30):
   u=(math.cos(math.radians(angle)),math.sin(math.radians(angle)))
   self.assertLessEqual(math.dist(feet,arrow_anchor(p,u,1280,720)),6.001)
if __name__=='__main__':unittest.main()
