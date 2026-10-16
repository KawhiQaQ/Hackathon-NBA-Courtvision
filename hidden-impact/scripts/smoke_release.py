"""Read-only deployment/static smoke test; optional real job via --request.
Never rewrites showcase data. A real job is billed by AWS and explicitly requested.
"""
import argparse
import http.client
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url', help='Local or deployed site; defaults to .cloud-config.json')
    parser.add_argument('--request', type=Path, help='Submit this keyframe request to the real pipeline')
    parser.add_argument('--public-only', action='store_true')
    parser.add_argument('--api-only', action='store_true',help='Validate API before the first public result is published')
    parser.add_argument('--job', help='Resume checking an existing job without submitting again')
    parser.add_argument('--output',type=Path,default=ROOT/'verification/cloud-release-smoke.json',help='Save the real job response for verification')
    args=parser.parse_args()
    base=(args.url or json.loads((ROOT/'.cloud-config.json').read_text())['url']).rstrip('/')+'/'
    origin=urlparse(base).netloc
    token=(ROOT/'.team-access-code').read_text().strip() if not args.public_only else None
    checked=set()
    def fetch(path, body=None, asset=False, authenticated=False):
        url=urljoin(base,path)
        if urlparse(url).netloc!=origin and not asset:
            raise ValueError('API request must use deployment origin')
        headers={'Content-Type':'application/json'}
        if authenticated:headers['X-Team-Key']=token
        if asset:headers['Range']='bytes=0-1023'
        req=urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,headers=headers)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req,timeout=50) as response:
                    raw=response.read(1024) if asset else response.read()
                    if not raw:raise RuntimeError('Empty response: '+path)
                    if asset and path.split('?')[0].endswith('.mp4') and b'ftyp' not in raw[:40]:raise RuntimeError('Invalid MP4 response')
                    return raw
            except (urllib.error.URLError,TimeoutError,http.client.RemoteDisconnected) as exc:
                # GET retries are safe; an uncertain POST must never enqueue twice.
                if body is not None or attempt==3 or isinstance(exc,urllib.error.HTTPError) and exc.code not in [429,502,503,504]:raise
                time.sleep(.5*2**attempt)
    def data(path, body=None):return json.loads(fetch(path,body,authenticated=not args.public_only))
    for path in ['','workbench.html','showcase.js','story-playback.js','app.js','game-view.js','insights-view.js',
                 'showcase.css','studio-theme.css','studio-workbench.css','flow-view.js','upload-flow.js']:
        fetch(path);checked.add(path)
    if not args.api_only:
        note=fetch('readme').decode('utf-8')
        if '{{JOB_ID}}' in note or '{{VIDEO_SOURCE}}' in note:raise RuntimeError('Unfilled public project notes')
        checked.add('readme')
    game=data('demo/game.json') if not args.api_only else {'rounds':[]}
    rounds=game.get('rounds',[game])
    if not args.api_only and not rounds:raise RuntimeError('No published result')
    for round_ in rounds:
        for asset in filter(None,[round_['video'],round_.get('original')]+[f['image'] for f in round_['evidence']]):
            if asset not in checked:fetch(urljoin('demo/game.json',asset),asset=True);checked.add(asset)
    print('Static resources OK:',len(rounds),'published rounds,',len(checked),'assets',flush=True)
    if args.public_only:return
    assert data('api/health')['ok']
    assert data('api/session')['ok']
    library=data('api/library')['videos']
    print('Authenticated API OK; library items:',len(library),flush=True)
    if not args.request and not args.job:return
    if args.job:job=args.job;print('Resuming job:',job,flush=True)
    else:
        payload=json.loads(args.request.read_text());payload.pop('deepData',None);payload['force']=True
        job=data('api/jobs',payload)['job'];print('Job submitted:',job,flush=True)
    started=time.monotonic();last=None
    while time.monotonic()-started<1020:
        response=data('api/jobs/'+job);stage=(response['status'],response.get('stage'))
        if stage!=last:print('Job status:',stage,'elapsed:',round(time.monotonic()-started,1),'s',flush=True);last=stage
        if response['status']=='failed':raise RuntimeError(response.get('error','Job failed'))
        if response['status']=='completed':break
        time.sleep(4)
    else:raise RuntimeError('Job did not complete within 17 minutes: '+job)
    out=args.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(response,ensure_ascii=False,indent=2))
    result=response['result'];p=result.get('presentation') or {}
    if not result.get('modelInvoked'):raise RuntimeError('No real analysis model invocation recorded')
    if result.get('renderError'):raise RuntimeError(result['renderError'])
    if not p.get('rendered'):raise RuntimeError('Analysis completed but rendered presentation is unavailable; inspect verification report')
    if result.get('narration',{}).get('status')=='unavailable' or not result.get('narration',{}).get('segments'):
        raise RuntimeError('Analysis completed but timed commentary is unavailable')
    if not result['narration'].get('modelInvoked'):raise RuntimeError('Timed commentary did not invoke the model')
    if not p.get('evidence') or any(not 0<=f['time']<result['video']['duration'] for f in p['evidence']):
        raise RuntimeError('Story evidence is missing or outside the clip')
    fetch(p['video'],asset=True)
    for frame in p.get('evidence',[]):fetch(frame['image'],asset=True)
    if p.get('analysisStatus') not in ['unconfirmed-mvp','reviewed-story']:
        summary=data('api/games',{'gameId':p.get('gameId') or 'smoke-'+job,'team':p.get('team') or 'smoke-team','jobIds':[job]})
        data('api/games/'+summary['id'])
        print('Game aggregation OK',flush=True)
    print('Real analysis, narration, MP4 and evidence frames OK; MVP:',p.get('analysisStatus','verified'),flush=True)

if __name__=='__main__':main()
