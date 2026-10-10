"""Presentation export preserves rendered geometry while archiving the original record."""
import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from showcase_payload import export_payload
class PayloadTest(unittest.TestCase):
 def setUp(self):self.audit=json.loads((ROOT/'data/review-archive/showcase-audit.json').read_text())
 def test_coordinates_arrows_and_story_are_unchanged(self):
  current=json.loads((ROOT/'tests/fixtures/legacy-showcase/analysis.json').read_text());original=self.audit['analysis']
  for before,after in zip(original['presentationMotion']['frames'],current['presentationMotion']['frames']):
   self.assertEqual(before['time'],after['time']);self.assertEqual(before['heroArrow']['points'],after['heroArrow']['points'])
   for a,b in zip(before['people'],after['people']):
    for key in ['trackId','x','y','w','h','offscreen']:self.assertEqual(a.get(key),b.get(key))
  self.assertEqual(json.loads((ROOT/'tests/fixtures/legacy-showcase/showcase.json').read_text())['evidence'],self.audit['showcase']['evidence'])
 def test_export_uses_an_allowlist_and_keeps_audit(self):
  self.audit['analysis']['unusedInternalField']='test'
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'web/demo').mkdir(parents=True)
   public,manifest=export_payload(self.audit['analysis'],self.audit['showcase'],root)
   self.assertNotIn('unusedInternalField',public)
   saved=json.loads((root/'data/review-archive/showcase-audit.json').read_text())
   self.assertEqual(saved['analysis'],self.audit['analysis'])
   self.assertEqual(public['presentationScore']['kind'],'presentation');self.assertEqual(manifest['scoreKind'],'presentation')
   with self.assertRaises(ValueError):export_payload(public,manifest,root)
if __name__=='__main__':unittest.main()
