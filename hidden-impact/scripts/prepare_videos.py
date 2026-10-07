"""Prepare user-supplied samples for web playback and dated keyframe VLM requests."""
import base64, json, subprocess
from pathlib import Path
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
f=imageio_ffmpeg.get_ffmpeg_exe()
media=ROOT/'data/videos/web';media.mkdir(exist_ok=True)
frames=ROOT/'data/frames';frames.mkdir(exist_ok=True)
posters=ROOT/'web/posters';posters.mkdir(exist_ok=True)
catalog=[]
for i,duration in [(1,21.55),(2,22.89)]:
 id=f'nba-sample-{i}';src=ROOT/f'data/videos/{id}.mp4';out=media/f'{id}.mp4'
 if not out.exists():subprocess.run([f,'-y','-i',str(src),'-vf','scale=1280:-2','-c:v','libx264','-preset','fast','-crf','23','-r','30','-c:a','aac','-b:a','96k','-movflags','+faststart',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 entries=[]
 for n in range(18):
  t=round(.1+n*(duration-.3)/17,2);jpg=frames/f'{id}-{n:02}.jpg'
  subprocess.run([f,'-y','-ss',str(t),'-i',str(src),'-frames:v','1','-vf','scale=960:-2','-q:v','5',str(jpg)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  entries.append({'time':t,'image':base64.b64encode(jpg.read_bytes()).decode()})
 (posters/f'{id}.jpg').write_bytes((frames/f'{id}-04.jpg').read_bytes())
 video={'id':id,'title':f'NBA 官方参考片段 {i:02}','duration':duration,'source':'用户提供的 train_video.zip'}
 (frames/f'{id}-request.json').write_text(json.dumps({'video':video,'frames':entries},ensure_ascii=False))
 catalog.append(video | {'poster':f'posters/{id}.jpg'})
 print(id,out.stat().st_size,flush=True)
(ROOT/'web/data/videos.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2))
