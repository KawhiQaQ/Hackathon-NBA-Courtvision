"""Resolve user-owned AWS resources; no account or competition defaults."""
import json
import os
from pathlib import Path
import boto3
ROOT = Path(__file__).resolve().parents[1]

def session(profile=None, region=None):
    return boto3.Session(profile_name=profile or os.getenv('AWS_PROFILE') or None,
                         region_name=region or os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1')

def outputs():
    data = json.loads((ROOT/'infra/cdk-outputs.json').read_text())
    name = os.getenv('HIAGENT_STACK_NAME', 'HiAgent')
    if name in data:
        return data[name]
    matches = [value for value in data.values() if 'MediaBucket' in value and 'FrontendUrl' in value]
    if len(matches) == 1:
        return matches[0]
    raise ValueError('Set HIAGENT_STACK_NAME to the deployed stack name.')
