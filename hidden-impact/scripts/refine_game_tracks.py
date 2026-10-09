"""Fit reviewed identity paths to actual basketball detector boxes.
Review anchors choose identities. Model boxes refine localization only; this
never turns human identity choices into a claim of automatic player selection.
"""
import base64,io,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'cloud/api'))
from vision import sample_video
from court_vision import infer
from game_review_annotations import CLIPS


def generate():
 out=ROOT/'data/review-archive/game';out.mkdir(exist_ok=True)
 for eid,cfg in CLIPS.items():
  cache=out/f'detections-{eid}.json'
  if cache.exists():continue
  frames=sample_video(ROOT/f'data/videos/nba-public/nba-0042500404-{eid}.mp4',9.2);rows=[]
  for f in frames:
   im=Image.open(io.BytesIO(base64.b64decode(f['image']))).convert('RGB');people=[]
   for d in infer(im,'player'):
    if d['class']!=4 or d['confidence']<.4:continue
    x,y,x2,y2=d['box']
    crop=np.asarray(im.crop((int((x+(x2-x)*.2)*im.width),int((y+(y2-y)*.2)*im.height),int((x2-(x2-x)*.2)*im.width),int((y+(y2-y)*.5)*im.height))))/255
    if not crop.size:continue
    white=float(np.mean((crop.min(2)>.63)&(crop.max(2)-crop.min(2)<.22)))
    people.append({**d,'white':white})
   rows.append({'time':f['time'],'people':people})
  cache.write_text(json.dumps({'source':'basketball-player-onnx','identitySource':'separate-human-anchors','frames':rows}));print(eid,len(rows),flush=True)

if __name__=='__main__':generate()
