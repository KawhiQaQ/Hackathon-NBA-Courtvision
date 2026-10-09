"""Build an explicitly labeled offline showcase from a saved geometry run.
No model calls, credentials or cloud dependencies. Re-run before static deployment.
"""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from showcase_motion import BroadcastRenderer,W,H,TOTAL
from showcase_identity import display_names,TEAM_NAMES
from showcase_role_review import reviewed_demo
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from render_video import ffmpeg

def build(source):
 out=ROOT/'web/demo';out.mkdir(exist_ok=True)
 r=json.loads((ROOT/'tests/fixtures/temporal-cloud.json').read_text())['result']
 r=reviewed_demo(r)
 r['displayNames']=display_names(r);r['teamNames']=TEAM_NAMES
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
 for k,t in enumerate([e['start'],e['keyTime'],e['end']]):
  raw=subprocess.check_output([ffmpeg(),'-v','error','-ss',str(t),'-i',str(source),'-frames:v','1','-vf',f'scale={w}:{h}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
  annotate(raw,t).save(out/f'frame-{k+1}.jpg',quality=90);evidence.append({'time':t,'image':f'demo/frame-{k+1}.jpg','label':['右侧外拉','防守站位','接球出手'][k]})
 manifest={'schema':'hidden-impact/showcase-v1','teamId':'14','mode':'demo','title':'让镜头跟随，得分之外的那个人。','matchup':'尼克斯 × 马刺','source':'NBA China · Inside the Game','sourceFile':source.name,'duration':i/fps,'renderStyle':'reviewed-roles-v5','width':W,'height':TOTAL,'video':'demo/replay.mp4?v=reviewroles5','original':'demo/original.mp4','poster':'demo/frame-1.jpg','provenance':'真实视频与历史视觉轨迹；主角由用户指定，得分者按出手帧绑定；评分已撤回，尚未核验机会创造关系。','actor':{'id':e['actorTrackId'],'label':r['displayNames'][e['actorTrackId']]},'roles':[{'id':pid,'label':label,'displayName':r['displayNames'][pid],'color':color} for pid,label,color in roles],'score':None,'components':e['components'],'evidence':evidence,'intervals':[{'start':7.5,'end':8.63,'title':'跟随右侧主角，观察外拉跑位','text':'尼克斯主角向画面右侧外拉，金色箭头提前展示后续方向。观察附近马刺防守者是否跟随，以及他与左侧出手区域的位置关系。'},{'start':8.63,'end':9.5,'title':'镜头另一侧，收益队友接球出手','text':'左侧尼克斯收益队友接球后出手，对应官方记录中的 OG 阿努诺比。本段用于核验右侧外拉是否牵制了防守，尚不能据此断言是谁创造了这次得分。'}]}
 (out/'showcase.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 # Sanitized preview result for the secondary workbench. Never give it a verified version/job.
 r['demo']=True;r['source']='offline-preview';r['usage']={};r['review']={};r['model']='offline-preview';r['modelInvoked']=False;r.pop('job',None);r['verificationVersion']='demo-unverified';r['overview']=manifest['provenance'];r['candidateChecks']=[]
 for event in r['events']:
  event['visualVerified']=False;event['identityVerification']='demo-unverified';event['commentary']='演示预设：'+manifest['intervals'][0]['text'];event['summary']=manifest['provenance']
 for p in r['players']:
  p['label']=r['displayNames'].get(p['id'],p['label'])
 for event in r['events']:
  event['actor']=r['displayNames'][event['actorTrackId']];event['beneficiary']=r['displayNames'][event['beneficiaryTrackId']]
  event['title']='外拉跑位观察 · '+event['actor']
 r['tacticalReplay']={'url':'demo/replay.mp4'}
 (out/'analysis.json').write_text(json.dumps(r,ensure_ascii=False,separators=(',',':')))
 print(f'Built {i} frames, {i/fps:.2f}s in {out}')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--video',type=Path,default=ROOT/'web/demo/original.mp4');a=p.parse_args();build(a.video)
