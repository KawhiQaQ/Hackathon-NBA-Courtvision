"""Request a fresh model Reviewer job; leaves the public showcase unchanged."""
import argparse
import json
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--source-job')
    source.add_argument('--source-analysis')
    parser.add_argument('--wait',action='store_true')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--strategy',choices=['auto','vlm'],default='auto')
    args=parser.parse_args()
    base=json.loads((ROOT/'.cloud-config.json').read_text())['url'].rstrip('/')
    token=(ROOT/'.team-access-code').read_text().strip()
    def api(path,body=None):
        request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,
                                       headers={'Content-Type':'application/json','X-Team-Key':token})
        with urllib.request.urlopen(request,timeout=45) as response:return json.load(response)
    payload={'sourceJob':args.source_job} if args.source_job else {'sourceAnalysis':args.source_analysis}
    payload['strategy']=args.strategy
    job=api('/api/reviews',payload)['job'];print('Reviewer job:',job,flush=True)
    if not args.wait:return
    deadline=time.monotonic()+1000;previous=None
    while time.monotonic()<deadline:
        response=api('/api/jobs/'+job)
        progress=(response['status'],response.get('stage'),response.get('done'))
        if progress!=previous:print('Reviewer:',progress,flush=True);previous=progress
        if response['status']=='failed':raise RuntimeError(response.get('error','Reviewer failed'))
        if response['status']=='completed':break
        time.sleep(5)
    else:raise TimeoutError('Reviewer job remains pending: '+job)
    if args.out:
        args.out.mkdir(parents=True,exist_ok=True)
        (args.out/'result.json').write_text(json.dumps(response['result'],ensure_ascii=False,indent=2))
        for name,url in response['result'].get('reviewArtifactUrls',{}).items():
            if name not in ['review.json','references.json','review-report.json','presentation-plan.json']:continue
            with urllib.request.urlopen(url,timeout=45) as stream:(args.out/name).write_bytes(stream.read())
    print('Open:',base+'/?job='+job,flush=True)

if __name__=='__main__':main()
