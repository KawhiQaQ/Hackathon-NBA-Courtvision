from app_config import session as aws_session, outputs as deployment_outputs
import json
from pathlib import Path
import boto3
ROOT=Path(__file__).resolve().parents[1]
config=deployment_outputs()
s3=aws_session().client('s3')
for item in json.loads((ROOT/'web/data/nba-catalog.json').read_text()):
 s3.upload_file(str(ROOT/f"data/videos/nba-public/{item['id']}.mp4"),config['MediaBucket'],item['key'],ExtraArgs={'ContentType':'video/mp4'})
 s3.put_object(Bucket=config['MediaBucket'],Key=f"library/{item['id']}.json",Body=json.dumps(item,ensure_ascii=False).encode(),ContentType='application/json')
 print('published',item['id'],flush=True)
