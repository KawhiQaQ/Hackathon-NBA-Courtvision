"""Build an explicitly labeled offline showcase from a saved geometry run.
No model calls, credentials or cloud dependencies. Re-run before static deployment.
"""
import argparse,json,shutil,subprocess,sys,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from render_video import ffmpeg,people_at,projection

def build(source):
 out=ROOT/'web/demo';out.mkdir(exist_ok=True)
 r=json.loads((ROOT/'tests/fixtures/temporal-cloud.json').read_text())['result']
 e=r['events'][0];frames=r['vision']['frames'];w,h,fps=960,540,24
 roles=[(e['actorTrackId'],'主角','#f4c45e'),(e['beneficiaryTrackId'],'收益队友','#77cfe4'),(e['defenderTrackId'],'防守者','#ee927f')]
 fontpath=Path('/System/Library/Fonts/STHeiti Light.ttc')
 font=ImageFont.truetype(str(fontpath),17) if fontpath.exists() else ImageFont.load_default(size=17)
 def annotate(raw,t):
  im=Image.frombytes('RGB',(w,h),raw);d=ImageDraw.Draw(im,'RGBA');people=people_at(frames,t)
  for pid,label,color in roles:
   p=next((p for p in people if p['trackId']==pid),None)
   if not p:continue
   x=(p['x']+p['w']/2)*w;y=(p['y']+p['h'])*h
   # Keep one meaningful projected trail, rather than every player's entire path.
   if pid==e['actorTrackId']:
    current=min(frames,key=lambda f:abs(f['time']-t));matrix=(current.get('calibration') or {}).get('courtToImage');last=None
    for f in frames:
     if f['scene']!=current['scene'] or not t-1.2<=f['time']<=t:continue
     q=next((q for q in f['people'] if q['trackId']==pid),None)
     pt=projection(matrix,q['court']) if q and matrix and q.get('court') else None
     if pt:
      xy=(pt[0]*w,pt[1]*h)
      if last and f['time']-last[1]<.4:d.line([last[0],xy],fill=color+'bb',width=4)
      last=(xy,f['time'])
     else:last=None
   d.ellipse((x-19,y-6,x+19,y+6),fill=color+'55',outline=color,width=3)
   ly=max(40,p['y']*h-24);text=label+' '+pid;tw=d.textlength(text,font=font)
   lx=max(4,min(w-tw-16,x-tw/2));d.rounded_rectangle((lx,ly,lx+tw+12,ly+24),5,fill='#102b2ce6');d.text((lx+6,ly+3),text,font=font,fill=color)
  d.rounded_rectangle((14,12,296,39),5,fill='#102b2ce6');d.text((23,17),'TEAM 14 · 演示预设 / 非正式结果',font=font,fill='white')
  return im
 dec=subprocess.Popen([ffmpeg(),'-v','error','-i',str(source),'-vf',f'fps={fps},scale={w}:{h}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE)
 enc=subprocess.Popen([ffmpeg(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','pipe:0','-i',str(source),'-map','0:v','-map','1:a?','-c:v','libx264','-preset','veryfast','-crf','21','-c:a','aac','-shortest','-movflags','+faststart',str(out/'replay.mp4')],stdin=subprocess.PIPE)
 i=0
 try:
  while raw:=dec.stdout.read(w*h*3):
   if len(raw)!=w*h*3:raise RuntimeError('Incomplete video frame')
   enc.stdin.write(annotate(raw,i/fps).tobytes());i+=1
 finally:
  enc.stdin.close();dec.stdout.close()
 if dec.wait() or enc.wait():raise RuntimeError('Video render failed')
 shutil.copyfile(source,out/'original.mp4')
 evidence=[]
 for k,t in enumerate([8.63,9.0,10.0]):
  raw=subprocess.check_output([ffmpeg(),'-v','error','-ss',str(t),'-i',str(source),'-frames:v','1','-vf',f'scale={w}:{h}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
  annotate(raw,t).save(out/f'frame-{k+1}.jpg',quality=90);evidence.append({'time':t,'image':f'demo/frame-{k+1}.jpg','label':['跑位开始','防守响应','空间变化'][k]})
 manifest={'schema':'hidden-impact/showcase-v1','teamId':'14','mode':'demo','title':'让镜头跟随，得分之外的那个人。','matchup':'尼克斯 × 马刺','source':'NBA China · Inside the Game','sourceFile':source.name,'duration':i/fps,'video':'demo/replay.mp4','original':'demo/original.mp4','poster':'demo/frame-1.jpg','provenance':'真实视频与历史视觉轨迹；候选选择、63 分和文字为流程演示预设，未调用 VLM，未核验因果贡献。','actor':{'id':e['actorTrackId'],'label':'浅色球衣 P13'},'roles':[{'id':pid,'label':label,'color':color} for pid,label,color in roles],'score':63,'components':e['components'],'evidence':evidence,'intervals':[{'start':8.63,'end':9.0,'title':'跟着主角，看防守响应','text':'主角 P13 沿底线移动；同时观察防守者 P3 的位置变化，以及收益队友 P2 一侧的空间。此处展示如何把跑位与防守反应串联起来。'},{'start':9.0,'end':10.0,'title':'从防守响应，回看队友空间','text':'历史轨迹中，P2 与 P3 的投影间距继续增大。回放用于检查这一变化是否与 P13 的跑位有关；最终幕后 MVP 归因仍需正式模型核验。'}]}
 (out/'showcase.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 # Sanitized preview result for the secondary workbench. Never give it a verified version/job.
 r['demo']=True;r['source']='offline-preview';r['usage']={};r['review']={};r['model']='offline-preview';r['modelInvoked']=False;r.pop('job',None);r['verificationVersion']='demo-unverified';r['overview']=manifest['provenance'];r['candidateChecks']=[]
 for event in r['events']:
  event['visualVerified']=False;event['identityVerification']='demo-unverified';event['commentary']='演示预设：'+manifest['intervals'][0]['text'];event['summary']=manifest['provenance']
 r['tacticalReplay']={'url':'demo/replay.mp4'}
 (out/'analysis.json').write_text(json.dumps(r,ensure_ascii=False,separators=(',',':')))
 print(f'Built {i} frames, {i/fps:.2f}s in {out}')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--video',type=Path,default=ROOT/'data/videos/nba-public/nba-0042500404-197.mp4');a=p.parse_args();build(a.video)
