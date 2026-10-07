import sys,unittest,threading,json,http.client
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/agent'))
import main
class RuntimeHealthTest(unittest.TestCase):
 def test_ping_busy_while_inference_running_then_idle(self):
  entered=threading.Event();release=threading.Event()
  def fake(data,client):entered.set();release.wait(3);return {'ok':True}
  server=main.ThreadingHTTPServer(('127.0.0.1',0),main.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();port=server.server_address[1]
  def request(method,path,body=None):
   c=http.client.HTTPConnection('127.0.0.1',port,timeout=5);c.request(method,path,body=body,headers={'Content-Type':'application/json'});r=json.loads(c.getresponse().read());c.close();return r
  try:
   with patch.object(main,'analyze',fake),patch.object(main,'model_client',return_value=None):
    worker=threading.Thread(target=lambda:request('POST','/invocations','{}'));worker.start();self.assertTrue(entered.wait(2));self.assertEqual(request('GET','/ping')['status'],'HealthyBusy');release.set();worker.join(3);self.assertEqual(request('GET','/ping')['status'],'Healthy')
  finally:release.set();server.shutdown();server.server_close()
