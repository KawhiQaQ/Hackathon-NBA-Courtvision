"""Real end-to-end CloudFront → Lambda → AgentCore → Qwen invocation and evidence cache."""
import json,time,urllib.request,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from review import reviewed_result, REJECTIONS
(ROOT/'web/data/nba-ai-reviews.json').write_text(json.dumps(REJECTIONS,ensure_ascii=False,indent=2))
url=json.loads((ROOT/'.cloud-config.json').read_text())['url'];token=(ROOT/'.team-access-code').read_text().strip()
def api(path,body=None):
 req=urllib.request.Request(url+'/api'+path,data=json.dumps(body).encode() if body else None,headers={'content-type':'application/json','X-Team-Key':token})
 with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)
items=json.loads((ROOT/'web/data/nba-catalog.json').read_text());examples={}
cache=ROOT/'web/data/nba-ai-examples.json'
if cache.exists():examples={k:reviewed_result(v) for k,v in json.loads(cache.read_text()).items()}
cache.write_text(json.dumps(examples,ensure_ascii=False,indent=2))
for item in items:
 id=item['id']
 if id in examples and examples[id].get('version')=='video-evidence-v1.2':continue
 payload=json.loads((ROOT/f'data/frames/nba-public/{id}-request.json').read_text());payload.pop('deepData',None)
 job=api('/jobs',payload)['job'];print('submitted',id,job,flush=True)
 start=time.monotonic()
 while time.monotonic()-start<650:
  response=api('/jobs/'+job)
  if response['status'] in ['completed','failed']:break
  time.sleep(4)
 if response['status']!='completed':print('FAILED',id,response,flush=True);continue
 result=reviewed_result(response['result']);thumbs=[]
 for event in result['events']:
  for obs in event['observations']:
   i=min(range(len(payload['frames'])),key=lambda i:abs(payload['frames'][i]['time']-obs['time']))
   name=f'{id}-{i:02}.jpg';src=ROOT/f'data/frames/nba-public/{name}';dst=ROOT/'web/posters'/name;dst.write_bytes(src.read_bytes());thumbs.append({'time':obs['time'],'url':'posters/'+name})
 result['thumbnails']=thumbs;examples[id]=result;cache.write_text(json.dumps(examples,ensure_ascii=False,indent=2))
 (ROOT/f'verification/{id}-cloud.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print('completed',id,'events',len(result['events']),'scores',[e['score'] for e in result['events']],'tokens',result['usage'],flush=True)
print('RESULTS',len(examples),flush=True)
