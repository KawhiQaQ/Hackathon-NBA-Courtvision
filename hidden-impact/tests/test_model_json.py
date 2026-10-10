import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from model_json import parse_model_json
class ModelJSONTests(unittest.TestCase):
 def test_missing_comma(self):
  self.assertEqual(parse_model_json('{"players":[{"id":"P1" "n":2} {"id":"P2"}],"ok":true}'),{'players':[{'id':'P1','n':2},{'id':'P2'}],'ok':True})
 def test_trailing_comma(self):
  self.assertEqual(parse_model_json('```json\n{"x":[1,2,],}\n```'),{'x':[1,2]})
 def test_retry(self):
  class Client:
   calls=0
   def converse(self,**kwargs):
    self.calls+=1
    return {'output':{'message':{'content':[{'text':'{"players":[]}'}]}}}
  client=Client()
  self.assertEqual(parse_model_json('{broken',client,'model'),{'players':[]})
  self.assertEqual(client.calls,1)
 def test_invalid_fails(self):
  with self.assertRaises(ValueError):parse_model_json('{broken')
