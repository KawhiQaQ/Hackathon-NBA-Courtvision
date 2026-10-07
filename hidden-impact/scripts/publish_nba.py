import json
from pathlib import Path
import boto3
ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'infra/cdk-outputs.json').read_text())['HiddenImpactTeam14']
s3=boto3.Session(profile_name='nba',region_name='us-east-1').client('s3')
for item in json.loads((ROOT/'web/data/nba-catalog.json').read_text()):
 s3.upload_file(str(ROOT/f"data/videos/nba-public/{item['id']}.mp4"),config['MediaBucket'],item['key'],ExtraArgs={'ContentType':'video/mp4'})
 s3.put_object(Bucket=config['MediaBucket'],Key=f"library/{item['id']}.json",Body=json.dumps(item,ensure_ascii=False).encode(),ContentType='application/json')
 print('published',item['id'],flush=True)
