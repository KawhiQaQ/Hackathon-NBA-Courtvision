"""Deploy, provision required model assets, and save the current frontend URL."""
import json
import os
import secrets
import subprocess
from pathlib import Path
import boto3
from deployment_assets import preflight, publish_models

ROOT = Path(__file__).resolve().parents[1]

def main():
    print('Deployment preflight:', preflight(), flush=True)
    session = boto3.Session(profile_name='nba', region_name='us-east-1')
    account = session.client('sts').get_caller_identity()['Account']
    token = ROOT/'.team-access-code'
    if not token.exists():
        token.write_text(secrets.token_urlsafe(24))
    token.chmod(0o600)
    env = {**os.environ, 'CDK_DEFAULT_ACCOUNT': account, 'CDK_DEFAULT_REGION': 'us-east-1', 'AWS_REGION': 'us-east-1'}
    cmd = [str(ROOT.parent/'aws-preflight/node_modules/.bin/cdk'), 'deploy', '--profile', 'nba',
           '--require-approval', 'never', '--progress', 'events', '--parameters', 'TeamKey='+token.read_text().strip(),
           '--outputs-file', str(ROOT/'infra/cdk-outputs.json')]
    subprocess.run(cmd, cwd=ROOT/'infra', env=env, check=True)
    outputs = json.loads((ROOT/'infra/cdk-outputs.json').read_text())['HiddenImpactTeam14']
    # A successful CloudFormation stack alone does not provision inference weights.
    publish_models(session.client('s3'), outputs['MediaBucket'])
    config = ROOT/'.cloud-config.json'
    config.write_text(json.dumps({'url': outputs['FrontendUrl']})+'\n')
    config.chmod(0o600)
    print('Deployment and model provisioning complete; cloud smoke test still required.')

if __name__ == '__main__':
    main()
