"""Local UI and same-origin cloud proxy. Credentials never sent to the browser."""
import argparse,json,sys,urllib.request,urllib.error
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'src'))
from analysis import analyze_document
class Handler(SimpleHTTPRequestHandler):
 def json_reply(self,status,body):
  raw=json.dumps(body,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
 def proxy(self,body=None):
  origin=self.headers.get('Origin')
  if origin and origin not in ['http://127.0.0.1:'+str(self.server.server_port),'http://localhost:'+str(self.server.server_port)]:return self.json_reply(403,{'error':'来源不匹配。'})
  try:
   url=json.loads((ROOT/'.cloud-config.json').read_text())['url']
   token=(ROOT/'.team-access-code').read_text().strip()
   req=urllib.request.Request(url+self.path,data=body,headers={'Content-Type':'application/json','X-Team-Key':token})
   try:
    with urllib.request.urlopen(req,timeout=35) as response:return self.json_reply(response.status,json.loads(response.read()))
   except urllib.error.HTTPError as exc:
    try:payload=json.loads(exc.read())
    except Exception:payload={'error':'云端返回错误。'}
    return self.json_reply(exc.code,payload)
  except Exception as exc:return self.json_reply(502,{'error':'云端连接失败：'+str(exc)[:160]})
 def do_GET(self):
  if self.path.startswith('/api/'):return self.proxy()
  return super().do_GET()
 def do_POST(self):
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=5*1024*1024:return self.json_reply(413,{'error':'请求过大。'})
   body=self.rfile.read(n)
   if self.path=='/api/analyze':return self.json_reply(200,analyze_document(json.loads(body)))
   if self.path.startswith('/api/'):return self.proxy(body)
   return self.json_reply(404,{'error':'接口不存在。'})
  except (ValueError,TypeError,KeyError) as exc:return self.json_reply(400,{'error':str(exc)[:250]})
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
 print(f'Hidden Impact http://127.0.0.1:{args.port}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(ROOT/'web'))).serve_forever()
