import sys,json,boto3
from pathlib import Path
from botocore.config import Config
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'verification'))
from possession_experiment import verify_possession
p=json.loads((ROOT/'verification/diagnose-197-request.json').read_text())
c=boto3.Session(profile_name='nba',region_name='us-east-1').client('bedrock-runtime',config=Config(proxies={},connect_timeout=15,read_timeout=180,retries={'max_attempts':0}))
r,u=verify_possession(p,c,'qwen.qwen3-vl-235b-a22b')
(ROOT/'verification/diagnose-197-possession.json').write_text(json.dumps({'audit':r,'usage':u},ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False),flush=True)
