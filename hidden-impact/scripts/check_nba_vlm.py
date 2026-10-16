from app_config import session as aws_session, outputs as deployment_outputs
import json,sys
from pathlib import Path
import boto3
from botocore.config import Config
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/agent'))
from logic import analyze
payload=json.loads((ROOT/'data/frames/nba-public/nba-0042500404-658-request.json').read_text())
client=aws_session().client('bedrock-runtime',config=Config(read_timeout=180,retries={'total_max_attempts':1}))
class Capture:
 def converse(self,**kwargs):
  response=client.converse(**kwargs)
  (ROOT/'verification/nba-vlm-raw.json').write_text(json.dumps(response,ensure_ascii=False,default=str))
  return response
result=analyze(payload,Capture())
(ROOT/'verification/nba-vlm-direct.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='deepData'},ensure_ascii=False,indent=2))
