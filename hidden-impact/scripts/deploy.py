"""Deploy HiAgent into your AWS account and provision its inference weights."""
import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path
from app_config import session
from deployment_assets import preflight, publish_models

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default=os.getenv('AWS_PROFILE'))
    parser.add_argument('--region', default=os.getenv('AWS_REGION', 'us-east-1'))
    parser.add_argument('--stack', default=os.getenv('HIAGENT_STACK_NAME', 'HiAgent'))
    args = parser.parse_args()
    print('Deployment preflight:', preflight(), flush=True)
    aws = session(args.profile, args.region)
    account = aws.client('sts').get_caller_identity()['Account']
    token = ROOT/'.team-access-code'
    if not token.exists():
        token.write_text(secrets.token_urlsafe(24))
    token.chmod(0o600)
    env = {**os.environ, 'CDK_DEFAULT_ACCOUNT': account, 'CDK_DEFAULT_REGION': args.region,
           'AWS_REGION': args.region, 'HIAGENT_STACK_NAME': args.stack}
    cmd = [str(ROOT/'infra/node_modules/.bin/cdk'), 'deploy', '--require-approval', 'never',
           '--parameters', 'TeamKey='+token.read_text().strip(), '--outputs-file', str(ROOT/'infra/cdk-outputs.json')]
    if args.profile:
        cmd.extend(['--profile', args.profile])
    subprocess.run(cmd, cwd=ROOT/'infra', env=env, check=True)
    outputs = json.loads((ROOT/'infra/cdk-outputs.json').read_text())[args.stack]
    publish_models(aws.client('s3'), outputs['MediaBucket'])
    config = ROOT/'.cloud-config.json'
    config.write_text(json.dumps({'url': outputs['FrontendUrl']})+'\n')
    config.chmod(0o600)
    print('Deployed:', outputs['FrontendUrl'])
    print('Workspace access code: .team-access-code (keep private).')
    print('Run a real video job to verify model access and output quality in this account.')

if __name__ == '__main__':
    main()
