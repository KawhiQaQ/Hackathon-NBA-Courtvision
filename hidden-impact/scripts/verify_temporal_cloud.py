"""Exercise the deployed authenticated video -> perception -> VLM -> score -> MP4 pipeline."""
import json,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1];url=json.loads((root/'.cloud-config.json').read_text())['url'];key=(root/'.team-access-code').read_text().strip()
def api(path,body=None):
 req=urllib.request.Request(url+'/api'+path,data=json.dumps(body).encode() if body else None,headers={'content-type':'application/json','X-Team-Key':key})
 with urllib.request.urlopen(req,timeout=50) as response:return json.load(response)
p=json.loads((root/'data/frames/nba-public/nba-0042500404-197-request.json').read_text());p.pop('deepData',None);p['force']=True
job=api('/jobs',p)['job'];print('JOB',job,flush=True);(root/'verification/temporal-cloud-job.txt').write_text(job)
last=None
for i in range(250):
 r=api('/jobs/'+job);status=(r['status'],r.get('stage'),r.get('done'))
 if status!=last:print(status,flush=True);last=status
 if r['status'] in ['completed','failed']:
  (root/'verification/temporal-cloud.json').write_text(json.dumps(r,ensure_ascii=False))
  if r['status']=='failed':raise RuntimeError(r.get('error'))
  print('RESULT',[(p['id'],p['score']) for p in r['result']['players']],bool(r['result'].get('tacticalReplay')),flush=True);break
 time.sleep(4)
else:raise RuntimeError('Cloud job timed out')
