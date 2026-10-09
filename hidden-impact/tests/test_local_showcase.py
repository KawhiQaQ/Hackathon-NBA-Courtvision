"""Regression checks for a reviewer who never opens a file or signs into AWS."""
import json,threading,unittest,urllib.request,urllib.error,sys
from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server import Handler
class QuietHandler(Handler):
 def log_message(self,*args):pass
class LocalShowcaseTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'web')))
  cls.server.cloud_enabled=False;cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url=f'http://127.0.0.1:{cls.server.server_port}'
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
 def get(self,path,**headers):return urllib.request.urlopen(urllib.request.Request(self.url+path,headers=headers))
 def test_root_is_precomputed_showcase(self):
  with self.get('/') as r:html=r.read().decode()
  self.assertIn('TEAM 14',html);self.assertIn('demo/replay.mp4',html);self.assertIn('workbench.html',html);self.assertNotIn('type="file"',html)
  with self.get('/demo/showcase.json') as r:d=json.load(r)
  self.assertEqual(d['mode'],'demo')
  for asset in [d['video'],d['original'],d['poster'],*[f['image'] for f in d['evidence']]]:
   with self.get('/'+asset,Range='bytes=0-31') as r:self.assertIn(r.status,[200,206]);self.assertTrue(r.read(32))
 def test_mp4_seek_and_suffix(self):
  raw=(ROOT/'web/demo/replay.mp4').read_bytes()
  with self.get('/demo/replay.mp4',Range='bytes=101-200') as r:
   self.assertEqual(r.status,206);self.assertEqual(r.read(),raw[101:201]);self.assertEqual(r.headers['Content-Range'],f'bytes 101-200/{len(raw)}')
  with self.get('/demo/replay.mp4',Range='bytes=-100') as r:self.assertEqual(r.read(),raw[-100:])
  for val in ['bytes=-0','bytes=20-10','bytes=999999999-','bytes=0-1,3-4']:
   with self.assertRaises(urllib.error.HTTPError) as c:self.get('/demo/replay.mp4',Range=val)
   self.assertEqual(c.exception.code,416)
 def test_offline_never_needs_credentials(self):
  with self.get('/api/session') as r:self.assertEqual(json.load(r)['mode'],'offline')
  with self.assertRaises(urllib.error.HTTPError) as c:self.get('/api/jobs/old')
  self.assertEqual(c.exception.code,503)
  with self.assertRaises(urllib.error.HTTPError) as c:self.get('/.team-access-code')
  self.assertEqual(c.exception.code,404)
 def test_mock_cannot_claim_production_inference(self):
  with self.get('/demo/analysis.json') as r:d=json.load(r)
  self.assertTrue(d['demo']);self.assertFalse(d['modelInvoked']);self.assertNotIn('job',d);self.assertEqual(d['verificationVersion'],'demo-unverified')
  self.assertTrue(all(not e['visualVerified'] for e in d['events']))
if __name__=='__main__':unittest.main()
