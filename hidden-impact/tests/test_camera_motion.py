"""Camera motion must not reverse a player's forward direction cue."""
import copy,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from camera_motion import translation
from presentation import motion
from test_presentation import verified

class CameraMotionTests(unittest.TestCase):
 def test_defender_has_independent_direction_and_disappears_on_missing_track(self):
  r=verified()
  for f in r['vision']['frames']:
   for p in f['people']:
    p['x']=.45+f['time']*(.06 if p['trackId']=='lead-x' else -.06)
  frames=motion(r,r['events'][0])['frames']
  hero=frames[0]['heroArrow'];defender=frames[0]['defenderArrow']
  self.assertEqual(defender['trackId'],'guard-z')
  self.assertGreater(hero['points'][-1][0],hero['points'][0][0])
  self.assertLess(defender['points'][-1][0],defender['points'][0][0])
  self.assertGreater(len(defender['points']),2)
  for f in r['vision']['frames']:
   if .3<f['time']<1.5:f['people']=[p for p in f['people'] if p['trackId']!='guard-z']
  frame=motion(r,r['events'][0],fps=10)['frames'][10]
  self.assertIsNone(frame['defenderArrow']);self.assertIsNotNone(frame['heroArrow'])

 def test_background_translation_and_featureless_rejection(self):
  a=np.random.default_rng(4).normal(size=(54,320))
  shift=translation(a,np.roll(a,(-2,-9),(0,1)))
  self.assertIsNotNone(shift);self.assertEqual(shift[:2],(-9.,-2.))
  self.assertIsNone(translation(np.zeros((54,320)),np.zeros((54,320))))
 def test_pan_compensation_reverses_false_backward_arrow(self):
  r=verified()
  for f in r['vision']['frames']:
   for p in f['people']:p['x']=.5-f['time']*.05
   f['cameraOffset']=[-f['time']*.09,0]
  compensated=motion(r,r['events'][0])['frames'][0]['heroArrow']['points']
  self.assertGreater(compensated[-1][0],compensated[0][0])
  for f in r['vision']['frames']:f.pop('cameraOffset')
  uncorrected=motion(r,r['events'][0])['frames'][0]['heroArrow']['points']
  self.assertLess(uncorrected[-1][0],uncorrected[0][0])
