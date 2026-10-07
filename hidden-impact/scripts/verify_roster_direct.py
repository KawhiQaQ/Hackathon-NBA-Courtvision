"""Real inference using cached original video; isolated from asynchronous worker for diagnosis."""
import sys,json,base64,uuid,time
from pathlib import Path
import boto3
from botocore.config import Config
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/api'))
from vision import build_vision,sample_video
id='nba-0042500404-622';payload=json.loads((ROOT/f'data/frames/nba-public/{id}-request.json').read_text());original=payload['frames'];payload['_denseFrames']=sample_video(ROOT/f'data/videos/nba-public/{id}.mp4',payload['video']['duration']);vision,frames=build_vision(payload);payload.pop('_denseFrames');payload['vision']=vision;payload['frames']=frames
(ROOT/'verification/roster-request.json').write_text(json.dumps(payload));print('vision_ready',len(vision['frames']),flush=True)
s=boto3.Session(profile_name='nba',region_name='us-east-1');c=s.client('bedrock-runtime',config=Config(read_timeout=300,retries={'total_max_attempts':1}))
from logic import analyze
r=analyze(payload,c);r['thumbnails']=[{'time':f['time'],'url':'data:image/jpeg;base64,'+f['image']} for f in original]
(ROOT/'verification/roster-direct.json').write_text(json.dumps({'analysis':r},ensure_ascii=False,indent=2));print('complete',len(r['players']),[(p['label'],p['score'],p['role']) for p in r['players']],flush=True)
