"""Install the bundled historical replay for local browsing; no AWS required."""
import json
import shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def install(root=ROOT):
    source = root.parent/'examples/replay'
    target = root/'web/media/example'
    target.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if path.is_file() and path.suffix in ['.mp4','.jpg','.json']:
            shutil.copyfile(path, target/path.name)
    manifest = json.loads((target/'showcase.json').read_text())
    for key in ['video','poster']:
        if manifest.get(key):manifest[key]='../media/example/'+manifest[key]
    for frame in manifest['evidence']:
        frame['image']='../media/example/'+frame['image']
    (root/'web/demo').mkdir(exist_ok=True)
    (root/'web/demo/game.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return target

if __name__ == '__main__':
    print('Installed:', install())
    print('Run: python server.py → http://127.0.0.1:8765/')
