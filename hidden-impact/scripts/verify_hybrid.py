"""One real paid cloud invocation; no automatic frontend sample injection."""
import json,time,urllib.request,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];cfg=json.loads((ROOT/'.cloud-config.json').read_text());token=(ROOT/'.team-access-code').read_text().strip()
def api(path,body=None):
 req=urllib.request.Request(cfg['url']+'/api'+path,data=json.dumps(body).encode() if body else None,headers={'content-type':'application/json','X-Team-Key':token})
 with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)
id=sys.argv[1] if len(sys.argv)>1 else 'nba-0042500404-428'
payload=json.loads((ROOT/f'data/frames/nba-public/{id}-request.json').read_text());payload.pop('deepData',None)
job=api('/jobs',payload)['job'];print('job',job,flush=True);last=None
for _ in range(160):
 response=api('/jobs/'+job)
 current=(response['status'],response.get('stage'))
 if current!=last:print('stage',current,flush=True);last=current
 if response['status'] in ['completed','failed']:break
 time.sleep(4)
(ROOT/f'verification/{id}-hybrid.json').write_text(json.dumps(response,ensure_ascii=False,indent=2))
if response['status']!='completed':raise RuntimeError(response)
r=response['result'];print(json.dumps({'version':r['version'],'detector':r.get('vision',{}).get('model'),'tracks':r.get('vision',{}).get('stableTrackCount'),'players':len(r.get('players',[])),'events':len(r['events']),'scores':[e['score'] for e in r['events']],'tokens':r.get('usage'),'modelInvoked':r.get('modelInvoked')},ensure_ascii=False),flush=True)
assert r['version']=='basketball-roster-v3' and r.get('vision',{}).get('frames') and r['modelInvoked']
