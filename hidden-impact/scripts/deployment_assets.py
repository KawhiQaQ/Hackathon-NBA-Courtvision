"""Validate deployable artifacts and publish runtime weights before accepting jobs."""
import hashlib
import json
from pathlib import Path
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
MODEL_NAMES = ('player', 'ball', 'court')

def packaged_bytes(folder):
    return sum(p.stat().st_size for p in folder.rglob('*')
               if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')

def preflight(root=ROOT):
    required = [root/'cloud/agent/vendor/boto3/__init__.py',
                root/'cloud/vision-layer/bin/ffmpeg',
                root/'cloud/vision-layer/python/onnxruntime/__init__.py',
                root/'cloud/vision-layer/python/PIL/__init__.py',
                root/'cloud/vision-layer/python/numpy/__init__.py',
                root/'cloud/api/fonts/NotoSansSC.ttf', root/'web/demo/game.json']
    required += [root/f'models/basketball/{name}.onnx' for name in MODEL_NAMES]
    missing = [str(p.relative_to(root)) for p in required if not p.is_file() or not p.stat().st_size]
    if missing:
        raise ValueError('Missing deployment assets; follow docs/RESTORE.md: ' + ', '.join(missing))
    size = packaged_bytes(root/'cloud/api') + packaged_bytes(root/'cloud/vision-layer')
    if size >= 250*1024**2:
        raise ValueError(f'Lambda code + layers exceed the 250 MiB uncompressed limit: {size} bytes')
    binary = (root/'cloud/vision-layer/bin/ffmpeg').read_bytes()[:20]
    if binary[:4] != b'\x7fELF' or int.from_bytes(binary[18:20], 'little') != 183:
        raise ValueError('Lambda FFmpeg must be a Linux ARM64 ELF binary')
    native = list((root/'cloud/vision-layer/python/onnxruntime').rglob('onnxruntime_pybind11_state*.so'))
    if not native or not any('313' in p.name and 'aarch64' in p.name for p in native):
        raise ValueError('ONNX Runtime wheel must target CPython 3.13 / ARM64')
    return {'lambdaUncompressedBytes': size, 'models': len(MODEL_NAMES)}

def publish_models(s3, bucket, root=ROOT):
    published = []
    for name in MODEL_NAMES:
        path = root/f'models/basketball/{name}.onnx'
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        key = f'models/basketball-v1/{name}.onnx'
        try:
            meta = s3.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if exc.response['Error']['Code'] not in ('404', 'NoSuchKey', 'NotFound'):
                raise
            meta = {}
        if meta.get('ContentLength') == path.stat().st_size and meta.get('Metadata', {}).get('sha256') == digest:
            print('Model verified:', name, flush=True)
            continue
        s3.upload_file(str(path), bucket, key, ExtraArgs={'ContentType': 'application/octet-stream', 'Metadata': {'sha256': digest}})
        meta = s3.head_object(Bucket=bucket, Key=key)
        if meta['ContentLength'] != path.stat().st_size or meta.get('Metadata', {}).get('sha256') != digest:
            raise RuntimeError('Model upload verification failed: ' + name)
        published.append(name)
        print('Model published:', name, flush=True)
    return published

if __name__ == '__main__':
    print(json.dumps(preflight(), indent=2))
