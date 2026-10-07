import sys,json,boto3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/api'))
from vision import sample_video,build_vision
s=boto3.Session(profile_name='nba',region_name='us-east-1').client('s3');bucket=json.loads((ROOT/'infra/cdk-outputs.json').read_text())['HiddenImpactTeam14']['MediaBucket']
p=json.loads(s.get_object(Bucket=bucket,Key='jobs/7a9487f5127879232560e8984f57782c/request.json')['Body'].read())
p['_denseFrames']=sample_video(ROOT/'data/videos/nba-public/nba-0042500404-197.mp4',p['video']['duration'])
v,frames=build_vision(p);p.pop('_denseFrames');p['vision']=v;p['frames']=frames
(ROOT/'verification/diagnose-197-request.json').write_text(json.dumps(p));print('Prepared',len(v['frames']),'frames',flush=True)
