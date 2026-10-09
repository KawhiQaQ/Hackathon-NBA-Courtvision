"""Build an explicitly labeled offline showcase from a saved geometry run.
No model calls, credentials or cloud dependencies. Re-run before static deployment.
"""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from showcase_motion import BroadcastRenderer,W,H,TOTAL
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from render_video import ffmpeg

def build(source):
 out=ROOT/'web/demo';out.mkdir(exist_ok=True)
 r=json.loads((ROOT/'tests/fixtures/temporal-cloud.json').read_text())['result']
 e=r['events'][0];w,h,fps=W,H,30
 roles=[(e['actorTrackId'],'主角','#f4c45e'),(e['beneficiaryTrackId'],'收益队友','#77cfe4'),(e['defenderTrackId'],'防守者','#ee927f')]
 renderer=BroadcastRenderer(r)
 annotate=renderer.render
 dec=subprocess.Popen([ffmpeg(),'-v','error','-i',str(source),'-vf',f'fps={fps},scale={w}:{h}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE)
 enc=subprocess.Popen([ffmpeg(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{TOTAL}','-r',str(fps),'-i','pipe:0','-i',str(source),'-map','0:v','-map','1:a?','-c:v','libx264','-preset','veryfast','-crf','21','-c:a','aac','-shortest','-movflags','+faststart',str(out/'replay.pending.mp4')],stdin=subprocess.PIPE)
 i=0
 try:
  while raw:=dec.stdout.read(w*h*3):
   if len(raw)!=w*h*3:raise RuntimeError('Incomplete video frame')
   enc.stdin.write(annotate(raw,i/fps).tobytes());i+=1
 finally:
  enc.stdin.close();dec.stdout.close()
 if dec.wait() or enc.wait():raise RuntimeError('Video render failed')
 (out/'replay.pending.mp4').replace(out/'replay.mp4')
 if source.resolve()!=(out/'original.mp4').resolve():shutil.copyfile(source,out/'original.mp4')
 evidence=[]
 for k,t in enumerate([8.63,9.0,10.0]):
  raw=subprocess.check_output([ffmpeg(),'-v','error','-ss',str(t),'-i',str(source),'-frames:v','1','-vf',f'scale={w}:{h}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
  annotate(raw,t).save(out/f'frame-{k+1}.jpg',quality=90);evidence.append({'time':t,'image':f'demo/frame-{k+1}.jpg','label':['跑位开始','防守响应','空间变化'][k]})
 manifest={'schema':'hidden-impact/showcase-v1','teamId':'14','mode':'demo','title':'让镜头跟随，得分之外的那个人。','matchup':'尼克斯 × 马刺','source':'NBA China · Inside the Game','sourceFile':source.name,'duration':i/fps,'renderStyle':'broadcast-v2','width':W,'height':TOTAL,'video':'demo/replay.mp4?v=broadcast2','original':'demo/original.mp4','poster':'demo/frame-1.jpg','provenance':'真实视频与历史视觉轨迹；候选选择、63 分和文字为流程演示预设，未调用 VLM，未核验因果贡献。','actor':{'id':e['actorTrackId'],'label':'浅色球衣 P13'},'roles':[{'id':pid,'label':label,'color':color} for pid,label,color in roles],'score':63,'components':e['components'],'evidence':evidence,'intervals':[{'start':8.63,'end':9.0,'title':'跟着主角，看防守响应','text':'主角 P13 沿底线移动；同时观察防守者 P3 的位置变化，以及收益队友 P2 一侧的空间。此处展示如何把跑位与防守反应串联起来。'},{'start':9.0,'end':10.0,'title':'从防守响应，回看队友空间','text':'历史轨迹中，P2 与 P3 的投影间距继续增大。回放用于检查这一变化是否与 P13 的跑位有关；最终幕后 MVP 归因仍需正式模型核验。'}]}
 (out/'showcase.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 # Sanitized preview result for the secondary workbench. Never give it a verified version/job.
 r['demo']=True;r['source']='offline-preview';r['usage']={};r['review']={};r['model']='offline-preview';r['modelInvoked']=False;r.pop('job',None);r['verificationVersion']='demo-unverified';r['overview']=manifest['provenance'];r['candidateChecks']=[]
 for event in r['events']:
  event['visualVerified']=False;event['identityVerification']='demo-unverified';event['commentary']='演示预设：'+manifest['intervals'][0]['text'];event['summary']=manifest['provenance']
 r['tacticalReplay']={'url':'demo/replay.mp4'}
 (out/'analysis.json').write_text(json.dumps(r,ensure_ascii=False,separators=(',',':')))
 print(f'Built {i} frames, {i/fps:.2f}s in {out}')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--video',type=Path,default=ROOT/'web/demo/original.mp4');a=p.parse_args();build(a.video)
