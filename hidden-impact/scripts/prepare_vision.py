"""Build the CPU inference Lambda layer from official, pinned wheels and YOLOX weights."""
import hashlib,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];layer=ROOT/'cloud/vision-layer';(layer/'models').mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-m','pip','install','--upgrade','--target',str(layer/'python'),'--platform','manylinux_2_27_aarch64','--platform','manylinux_2_28_aarch64','--platform','manylinux2014_aarch64','--implementation','cp','--python-version','3.13','--only-binary=:all:','onnxruntime==1.30.0','numpy==2.5.3','pillow==12.3.0','flatbuffers==25.12.19','packaging==26.3','protobuf==7.36.2'],check=True)
p=layer/'models/yolox_s.onnx'
if not p.exists():urllib.request.urlretrieve('https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx',p)
if hashlib.sha256(p.read_bytes()).hexdigest()!='c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063':raise ValueError('Unexpected YOLOX model checksum')
urllib.request.urlretrieve('https://raw.githubusercontent.com/Megvii-BaseDetection/YOLOX/main/LICENSE',layer/'models/YOLOX-LICENSE')
print('Vision layer ready:',layer)

# FFmpeg is bundled from the official imageio-ffmpeg PyPI wheel.
import zipfile,tempfile
with tempfile.TemporaryDirectory() as tmp:
 subprocess.run([sys.executable,'-m','pip','download','imageio-ffmpeg==0.6.0','--platform','manylinux2014_aarch64','--only-binary=:all:','--no-deps','--dest',tmp],check=True)
 with zipfile.ZipFile(next(Path(tmp).glob('*.whl'))) as z:
  for x in z.infolist():
   if 'binaries/ffmpeg' in x.filename:
    out=layer/'bin/ffmpeg';out.parent.mkdir(exist_ok=True);out.write_bytes(z.read(x));out.chmod(0o755)
   if 'LICENSE' in x.filename:(layer/Path(x.filename).name).write_bytes(z.read(x))
