"""Install locally obtained basketball weights; export trusted PT inputs to ONNX."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['player', 'ball', 'court']:
        parser.add_argument('--'+name, required=True, type=Path, help='Trusted upstream .pt or exported .onnx')
    args = parser.parse_args()
    folder = ROOT/'models/basketball'
    records = {}
    for name in ['player', 'ball', 'court']:
        source = getattr(args, name).resolve()
        if source.suffix == '.pt':
            from ultralytics import YOLO
            source = Path(YOLO(str(source)).export(format='onnx', imgsz=640, opset=17, simplify=False, dynamic=False))
        if source.suffix != '.onnx' or not source.is_file():
            raise ValueError('Expected an existing .pt or .onnx file: '+str(source))
        import onnxruntime as ort
        session = ort.InferenceSession(str(source), providers=['CPUExecutionProvider'])
        if session.get_inputs()[0].shape != [1,3,640,640]:
            raise ValueError('Expected a 640×640, batch-one model: '+name)
        shape = session.get_outputs()[0].shape
        channels = shape[1] if len(shape)==3 else None
        if (name=='court' and channels!=59) or (name!='court' and channels!=11):
            raise ValueError('Model output does not match the supported basketball class/keypoint layout: '+str(shape))
        destination = folder/(name+'.onnx')
        if source != destination.resolve():
            shutil.copyfile(source, destination)
        with destination.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        records[name] = dict(size=destination.stat().st_size, sha256=digest, key=f'models/basketball-v1/{name}.onnx')
        print('Ready:', name)
    (folder/'installed-models.json').write_text(json.dumps(records, indent=2)+'\n')

if __name__ == '__main__':
    main()
