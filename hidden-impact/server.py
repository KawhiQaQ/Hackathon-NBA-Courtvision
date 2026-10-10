"""Local static showcase and optional cloud proxy. Offline is the default."""
import argparse,json,re,sys,urllib.request,urllib.error
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'cloud/api'))
from analysis import analyze_document
class Handler(SimpleHTTPRequestHandler):
 def json_reply(self,status,body):
  raw=json.dumps(body,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
 def proxy(self,body=None):
  if not getattr(self.server,'cloud_enabled',False):return self.json_reply(503,{'error':'当前为本地演示，不调用 AWS。云端恢复后可用 --cloud 启用。'})
  origin=self.headers.get('Origin')
  if origin and origin not in ['http://127.0.0.1:'+str(self.server.server_port),'http://localhost:'+str(self.server.server_port)]:return self.json_reply(403,{'error':'来源不匹配。'})
  try:
   url=json.loads((ROOT/'.cloud-config.json').read_text())['url'];token=(ROOT/'.team-access-code').read_text().strip()
   req=urllib.request.Request(url+self.path,data=body,headers={'Content-Type':'application/json','X-Team-Key':token})
   try:
    with urllib.request.urlopen(req,timeout=35) as response:return self.json_reply(response.status,json.loads(response.read()))
   except urllib.error.HTTPError as exc:
    try:payload=json.loads(exc.read())
    except Exception:payload={'error':'云端返回错误。'}
    return self.json_reply(exc.code,payload)
  except Exception as exc:return self.json_reply(502,{'error':'云端连接失败：'+str(exc)[:160]})
 def send_head(self):
  # Native seeking requires byte ranges; never expose source/config directories.
  self._byte_range=None
  path=Path(self.translate_path(self.path))
  try:path.resolve().relative_to(Path(self.directory).resolve())
  except ValueError:self.send_error(403);return None
  if path.suffix.lower()=='.mp4' and path.is_file():
   size=path.stat().st_size;start,end=0,size-1;header=self.headers.get('Range')
   if header:
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
    if not match or not any(match.groups()):self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return None
    a,b=match.groups()
    if a:start=int(a);end=min(int(b),size-1) if b else size-1
    else:start=max(0,size-int(b))
    if start>end or start>=size:self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return None
   self.send_response(206 if header else 200);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
   if header:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
   self.end_headers();f=path.open('rb');f.seek(start);self._byte_range=end-start+1;return f
  return super().send_head()
 def copyfile(self,source,outputfile):
  try:
   if self._byte_range is None:return super().copyfile(source,outputfile)
   remaining=self._byte_range
   while remaining:
    block=source.read(min(256*1024,remaining))
    if not block:break
    outputfile.write(block);remaining-=len(block)
  except (BrokenPipeError,ConnectionResetError):pass
 def do_GET(self):
  if self.path=='/readme':self.path='/readme.html'
  if self.path=='/api/session' and not getattr(self.server,'cloud_enabled',False):return self.json_reply(200,{'mode':'offline','teamId':'14'})
  if self.path.startswith('/api/'):return self.proxy()
  return super().do_GET()
 def do_POST(self):
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=5*1024*1024:return self.json_reply(413,{'error':'请求过大。'})
   body=self.rfile.read(n)
   if self.path=='/api/game-summary':
    from game_summary import aggregate
    data=json.loads(body)
    return self.json_reply(200,aggregate(data['rounds'],data['gameId'],data['team']))
   if self.path=='/api/analyze':return self.json_reply(200,analyze_document(json.loads(body)))
   if self.path.startswith('/api/'):return self.proxy(body)
   return self.json_reply(404,{'error':'接口不存在。'})
  except (ValueError,TypeError,KeyError) as exc:return self.json_reply(400,{'error':str(exc)[:250]})
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--cloud',action='store_true',help='Explicitly enable the AWS proxy');args=parser.parse_args()
 server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(ROOT/'web')));server.cloud_enabled=args.cloud
 print(f'Hidden Impact http://127.0.0.1:{args.port} ({"cloud" if args.cloud else "offline"})',flush=True);server.serve_forever()
