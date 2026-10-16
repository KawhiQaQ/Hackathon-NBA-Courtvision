"""Restore pinned model artifacts from a user-owned S3 bucket."""
import argparse,hashlib,json,os
from pathlib import Path
import boto3
ROOT=Path(__file__).resolve().parents[1]

def restore(bucket,profile=None,root=ROOT):
    client=boto3.Session(profile_name=profile,region_name=os.getenv('AWS_REGION','us-east-1')).client('s3')
    folder=root/'models/basketball';manifest=json.loads((folder/'manifest.json').read_text())
    def valid(path,record):
        if not path.is_file() or path.stat().st_size!=record['size']:return False
        with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()==record['sha256']
    for name,record in manifest.items():
        path=folder/(name+'.onnx')
        if valid(path,record):print('Verified',name);continue
        temp=path.with_suffix('.download')
        try:
            client.download_file(bucket,record['key'],str(temp))
            if not valid(temp,record):raise ValueError('Model checksum mismatch: '+name)
            temp.replace(path)
        finally:temp.unlink(missing_ok=True)
        print('Restored',name)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--bucket',required=True);ap.add_argument('--profile',default=None);args=ap.parse_args();restore(args.bucket,args.profile)
