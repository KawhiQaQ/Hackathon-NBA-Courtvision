import sys,time,threading,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from logic import analyze
_active=0
_lock=threading.Lock()
_client=None

def model_client():
 global _client
 if _client is None:
  import boto3
  from botocore.config import Config
  _client=boto3.client('bedrock-runtime',region_name='us-east-1',config=Config(read_timeout=300,retries={'total_max_attempts':1}))
 return _client

class Handler(BaseHTTPRequestHandler):
 def reply(self,code,body):
  raw=json.dumps(body,ensure_ascii=False,allow_nan=False).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  self.reply(200 if self.path=='/ping' else 404,{'status':'HealthyBusy' if _active else 'Healthy'})
 def do_POST(self):
  global _active
  if self.path!='/invocations':return self.reply(404,{'error':'Not found'})
  with _lock:_active+=1
  print('invocation_started',flush=True)
  try:
   size=int(self.headers.get('Content-Length','0'))
   if not 1<=size<=5*1024*1024:raise ValueError('请求过大。')
   data=json.loads(self.rfile.read(size));self.reply(200,{'ok':True,'result':analyze(data,model_client())})
  except Exception as exc:
   print(type(exc).__name__,str(exc)[:500],flush=True);self.reply(200,{'ok':False,'error':str(exc)[:500]})
  finally:
   with _lock:_active-=1
   print('invocation_finished',flush=True)
if __name__=='__main__':
 print('runtime_ready',flush=True)
 ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
