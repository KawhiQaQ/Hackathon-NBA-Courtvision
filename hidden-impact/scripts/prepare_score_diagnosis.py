from app_config import session as aws_session, outputs as deployment_outputs
import sys,json,boto3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/api'))
from vision import sample_video,build_vision
s=aws_session().client('s3');bucket=deployment_outputs()['MediaBucket']
p=json.loads(s.get_object(Bucket=bucket,Key='jobs/7a9487f5127879232560e8984f57782c/request.json')['Body'].read())
p['_denseFrames']=sample_video(ROOT/'data/videos/nba-public/nba-0042500404-197.mp4',p['video']['duration'])
v,frames=build_vision(p);p.pop('_denseFrames');p['vision']=v;p['frames']=frames
(ROOT/'verification/diagnose-197-request.json').write_text(json.dumps(p));print('Prepared',len(v['frames']),'frames',flush=True)
