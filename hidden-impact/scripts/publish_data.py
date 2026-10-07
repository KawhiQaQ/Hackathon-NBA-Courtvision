import json
from pathlib import Path
import boto3
root=Path(__file__).resolve().parents[1]
config=json.loads((root/'infra/cdk-outputs.json').read_text())['HiddenImpactTeam14']
s3=boto3.Session(profile_name='nba',region_name='us-east-1').client('s3')
for gid in ['114243','184439']:
 s3.upload_file(str(root/f'web/data/{gid}.json'),config['MediaBucket'],f'datasets/{gid}.json',ExtraArgs={'ContentType':'application/json'})
 print('published SkillCorner',gid)
(root/'.cloud-config.json').write_text(json.dumps({'url':config['FrontendUrl']}));(root/'.cloud-config.json').chmod(0o600)
