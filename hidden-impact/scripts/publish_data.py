from app_config import session as aws_session, outputs as deployment_outputs
import json
from pathlib import Path
import boto3
root=Path(__file__).resolve().parents[1]
config=deployment_outputs()
s3=aws_session().client('s3')
for gid in ['114243','184439']:
 s3.upload_file(str(root/f'web/data/{gid}.json'),config['MediaBucket'],f'datasets/{gid}.json',ExtraArgs={'ContentType':'application/json'})
 print('published SkillCorner',gid)
(root/'.cloud-config.json').write_text(json.dumps({'url':config['FrontendUrl']}));(root/'.cloud-config.json').chmod(0o600)
