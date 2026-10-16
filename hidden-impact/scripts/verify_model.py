from app_config import session as aws_session, outputs as deployment_outputs
import sys,json
from pathlib import Path
import boto3
from botocore.config import Config
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/agent'))
from logic import analyze
client=aws_session().client('bedrock-runtime',config=Config(read_timeout=180,retries={'total_max_attempts':1}))
payload=json.loads((ROOT/'data/frames/nba-sample-1-request.json').read_text())
result=analyze(payload,client)
(ROOT/'verification/direct-qwen-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
