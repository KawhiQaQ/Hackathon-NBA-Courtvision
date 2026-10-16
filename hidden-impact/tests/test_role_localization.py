import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from role_localization import grounded_reference,reject_jumps
from role_model import visual_event
from companion import validate_companion

class RoleTests(unittest.TestCase):
 def test_reference_cannot_invent_frame_or_box(self):
  frame={'time':1,'boxes':{'D0':{'x':.2}}}
  self.assertIsNone(grounded_reference({'time':1.5,'detectionId':'D0'},[frame]))
  self.assertIsNone(grounded_reference({'time':1,'detectionId':'D9'},[frame]))
  self.assertEqual(grounded_reference({'time':1,'detectionId':'D0'},[frame])[1],{'x':.2})
 def test_isolated_teleport_removed_but_scene_cut_not_interpolated(self):
  frames=[dict(time=i*.5,scene=0,cameraOffset=[0,0],people=[dict(trackId='actor',x=x,y=.4,w=.08,h=.2)]) for i,x in enumerate([.2,.8,.22])]
  reject_jumps(frames);self.assertEqual(frames[1]['people'],[])
 def test_visual_story_has_no_fabricated_score(self):
  lock=dict(status='locked',beneficiaryIsFinalShooter=True,roles=[{'id':s} for s in ['actor','shooter','defender']],eventId='visual',actionWindow={'start':4,'end':7},shotTime=9,actorAction='抢回篮板，传出球')
  out=visual_event(lock,12);self.assertIsNone(out['score']);self.assertEqual(out['beneficiaryTrackId'],'shooter')
  lock['actionWindow']['end']=10;self.assertIsNone(visual_event(lock,12))
 def test_exam_companion_preserves_double_zero_and_profile_scope(self):
  import json
  p=Path(__file__).resolve().parents[2]/'examples/dallas/companion.json'
  data=json.loads(p.read_text());out=validate_companion(data,23.78)
  self.assertEqual(out['shotContext']['shooterJersey'],'00');self.assertEqual(out['shotContext']['eventId'],273)
  self.assertEqual(len(out['playerProfiles']),10);self.assertEqual(len(out['roster']),10)
  self.assertEqual(out['alignment']['shotVideoTime'],13.5)
  wrong=copy.deepcopy(data);wrong['playerProfiles'][0]['gameId']='other'
  with self.assertRaises(ValueError):validate_companion(wrong,23.78)
if __name__=='__main__':unittest.main()
