"""Private local S3 backup and explicit restore; never upload this snapshot to Git."""
import argparse, concurrent.futures, hashlib, json, mimetypes, shutil
from pathlib import Path
from datetime import datetime, timezone
import boto3
from botocore.config import Config
ROOT = Path(__file__).resolve().parents[1]

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def safe_path(root, key):
    dest = (root / key).resolve()
    if not dest.is_relative_to(root.resolve()): raise ValueError('Unsafe object path')
    return dest

def local_matches(path, obj):
    if not path.exists() or path.stat().st_size != obj['Size']: return False
    parts = []
    whole = hashlib.md5()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            whole.update(chunk); parts.append(hashlib.md5(chunk).digest())
    etag = obj['ETag'].strip('"')
    return etag == whole.hexdigest() or etag == hashlib.md5(b''.join(parts)).hexdigest() + '-' + str(len(parts))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'verify', 'restore'])
    parser.add_argument('directory', type=Path)
    parser.add_argument('--profile', default='nba')
    parser.add_argument('--bucket', help='Explicit destination bucket required for restore')
    args = parser.parse_args(); base = args.directory.resolve(); manifest_path = base / 'manifest.json'
    if args.action == 'verify':
        manifest = json.loads(manifest_path.read_text())
        for obj in manifest['objects']:
            p = safe_path(base / 'objects', obj['key'])
            if not p.exists() or sha256(p) != obj['sha256']: raise ValueError('Checksum mismatch: '+obj['key'])
        print('Verified', len(manifest['objects']), 'objects'); return
    session = boto3.Session(profile_name=args.profile, region_name='us-east-1')
    s3 = session.client('s3', config=Config(max_pool_connections=16))
    if args.action == 'backup':
        outputs = json.loads((ROOT/'infra/cdk-outputs.json').read_text())['HiddenImpactTeam14']
        bucket = args.bucket or outputs['MediaBucket']; base.mkdir(parents=True, exist_ok=True)
        objects = [o for page in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket) for o in page.get('Contents', [])]
        print('Backing up', len(objects), 'objects,', sum(o['Size'] for o in objects), 'bytes', flush=True)
        def download(o):
            dest = safe_path(base/'objects', o['Key']); dest.parent.mkdir(parents=True, exist_ok=True)
            if not local_matches(dest, o):
                local = ROOT/'models/basketball'/Path(o['Key']).name if o['Key'].startswith('models/basketball-v1/') else None
                part = dest.with_name(dest.name+'.downloading')
                if local and local_matches(local, o): shutil.copy2(local, part)
                else: s3.download_file(bucket, o['Key'], str(part))
                part.replace(dest)
            if dest.stat().st_size != o['Size']: raise ValueError('Incomplete object '+o['Key'])
            return {'key':o['Key'], 'size':o['Size'], 'etag':o['ETag'], 'sha256':sha256(dest)}
        saved=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            for row in executor.map(download, objects):
                saved.append(row)
                if len(saved)%50==0: print('Saved',len(saved),'/',len(objects),flush=True)
        for name in ['.cloud-config.json', '.team-access-code', 'infra/cdk-outputs.json']:
            dest=base/'private-config'/Path(name).name; dest.parent.mkdir(exist_ok=True)
            if (ROOT/name).exists(): shutil.copy2(ROOT/name,dest); dest.chmod(0o600)
        manifest={'createdAt':datetime.now(timezone.utc).isoformat(),'sourceBucket':bucket,'region':'us-east-1','objects':saved}
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));manifest_path.chmod(0o600)
        print('Backup complete:',manifest_path,flush=True)
    else:
        if not args.bucket: parser.error('restore requires --bucket for the NEW deployment')
        manifest=json.loads(manifest_path.read_text())
        # Validate every file before the first upload.
        for o in manifest['objects']:
            if sha256(safe_path(base/'objects',o['key']))!=o['sha256']: raise ValueError('Checksum mismatch: '+o['key'])
        def upload(o):
            s3.upload_file(str(safe_path(base/'objects',o['key'])),args.bucket,o['key'],ExtraArgs={'ContentType':mimetypes.guess_type(o['key'])[0] or 'application/octet-stream'})
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor: list(executor.map(upload,manifest['objects']))
        print('Restored',len(manifest['objects']),'objects into',args.bucket)
if __name__=='__main__': main()
