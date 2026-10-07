"""Basketball-specific ONNX perception. Model facts never come from VLM boxes.
Weights: abdullahtarek/basketball_analysis; see models/basketball/SOURCES.txt.
"""
import base64,io,os,math,time,itertools
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import onnxruntime as ort
_SESSIONS={}
COURT=np.array([(0,0),(0,.91),(0,5.18),(0,10),(0,14.1),(0,15),(14,15),(14,0),(5.79,5.18),(5.79,10),(28,15),(28,14.1),(28,10),(28,5.18),(28,.91),(28,0),(22.21,5.18),(22.21,10)],float)

def session(name):
 if name not in _SESSIONS:
  p=Path(__file__).resolve().parents[2]/'models/basketball'/f'{name}.onnx'
  if not p.exists():
   p=Path('/tmp/hi-models')/f'{name}.onnx';p.parent.mkdir(exist_ok=True)
   if not p.exists():
    import boto3
    temp=p.with_suffix('.part');boto3.client('s3').download_file(os.environ['MEDIA_BUCKET'],f'models/basketball-v1/{name}.onnx',str(temp));temp.replace(p)
  opts=ort.SessionOptions();opts.intra_op_num_threads=4;opts.inter_op_num_threads=1
  _SESSIONS[name]=ort.InferenceSession(str(p),sess_options=opts,providers=['CPUExecutionProvider'])
 return _SESSIONS[name]

def overlap(a,b):
 x=max(a[0],b[0]);y=max(a[1],b[1]);xx=min(a[2],b[2]);yy=min(a[3],b[3]);inter=max(0,xx-x)*max(0,yy-y)
 return inter/max(1e-8,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)

def infer(im,name):
 w,h=im.size;r=min(640/w,640/h);nw,nh=round(w*r),round(h*r);dx=(640-nw)//2;dy=(640-nh)//2
 canvas=Image.new('RGB',(640,640),(114,114,114));canvas.paste(im.resize((nw,nh)),(dx,dy));a=np.asarray(canvas,dtype=np.float32).transpose(2,0,1)[None]/255
 s=session(name);raw=s.run(None,{s.get_inputs()[0].name:np.ascontiguousarray(a)})[0][0].T
 if name=='court':
  q=raw[np.argmax(raw[:,4])]
  if q[4]<.5:return []
  k=q[5:].reshape(-1,3).copy();k[:,0]=(k[:,0]-dx)/r/w;k[:,1]=(k[:,1]-dy)/r/h
  return k.tolist()
 scores=raw[:,4:11];classes=np.argmax(scores,axis=1);confidence=np.max(scores,axis=1);out=[]
 for i in np.argsort(confidence)[::-1]:
  if confidence[i]<.25:break
  cls=int(classes[i])
  if cls not in [0,2,4,5]:continue
  x,y,bw,bh=raw[i,:4];box=[(x-bw/2-dx)/r/w,(y-bh/2-dy)/r/h,(x+bw/2-dx)/r/w,(y+bh/2-dy)/r/h];box=np.clip(box,0,1).tolist()
  if any(overlap(box,q['box'])>.45 and (cls==q['class'] or cls in [4,5] and q['class'] in [4,5]) for q in out):continue
  out.append({'box':box,'confidence':round(float(confidence[i]),3),'class':cls})
 return out

def project(h,pts):
 a=np.c_[np.asarray(pts),np.ones(len(pts))]@np.asarray(h).T
 return a[:,:2]/np.where(abs(a[:,2:])>1e-8,a[:,2:],np.nan)

def fit_h(src,dst):
 # Hartley normalization avoids unstable fits when visible landmarks cover a small area.
 def norm(p):
  c=p.mean(0);scale=2**.5/max(np.mean(np.linalg.norm(p-c,axis=1)),1e-8);t=np.array([[scale,0,-scale*c[0]],[0,scale,-scale*c[1]],[0,0,1.]])
  return project(t,p),t
 s,ts=norm(np.array(src));d,td=norm(np.array(dst));a=[]
 for (x,y),(u,v) in zip(s,d):a.extend([[-x,-y,-1,0,0,0,u*x,u*y,u],[0,0,0,-x,-y,-1,v*x,v*y,v]])
 _,_,v=np.linalg.svd(a);h=np.linalg.inv(td)@v[-1].reshape(3,3)@ts
 if abs(h[2,2])<1e-10:raise ValueError('Degenerate homography')
 return h/h[2,2]

def calibrate(k):
 ids=[i for i,p in enumerate(k) if p[2]>.65 and 0<p[0]<1 and 0<p[1]<1]
 if len(ids)<5:return None
 src=np.array([k[i][:2] for i in ids]);dst=COURT[ids];best=None
 for subset in itertools.islice(itertools.combinations(range(len(ids)),4),100):
  try:
   h=fit_h(dst[list(subset)],src[list(subset)]);err=np.linalg.norm(project(h,dst)-src,axis=1);inside=err<.017
   if sum(inside)<5:continue
   if best is None or sum(inside)>sum(best):best=inside
  except (np.linalg.LinAlgError,ValueError):continue
 if best is None:return None
 try:
  h=fit_h(dst[best],src[best]);inv=np.linalg.inv(h);err=float(np.median(np.linalg.norm(project(h,dst[best])-src[best],axis=1)))
  if err>.012 or not np.isfinite(h).all():return None
  return {'courtToImage':h.round(8).tolist(),'imageToCourt':inv.round(8).tolist(),'inliers':int(sum(best)),'error':round(err,5),'units':'reference-court','source':'estimated-keypoints'}
 except np.linalg.LinAlgError:return None

def assign(cost):
 """Global minimum-cost rectangular assignment (Hungarian), including unmatched columns."""
 n=len(cost)
 if not n:return []
 m=len(cost[0]);u=[0.]*(n+1);v=[0.]*(m+1);p=[0]*(m+1);way=[0]*(m+1)
 for i in range(1,n+1):
  p[0]=i;j0=0;mins=[float('inf')]*(m+1);used=[False]*(m+1)
  while True:
   used[j0]=True;i0=p[j0];delta=float('inf');j1=0
   for j in range(1,m+1):
    if not used[j]:
     cur=cost[i0-1][j-1]-u[i0]-v[j]
     if cur<mins[j]:mins[j]=cur;way[j]=j0
     if mins[j]<delta:delta=mins[j];j1=j
   for j in range(m+1):
    if used[j]:u[p[j]]+=delta;v[j]-=delta
    else:mins[j]-=delta
   j0=j1
   if p[j0]==0:break
  while True:
   j1=way[j0];p[j0]=p[j1];j0=j1
   if j0==0:break
 return [(p[j]-1,j-1) for j in range(1,m+1) if p[j]]

def build(payload,progress=None):
 started=time.monotonic();anchors={round(f['time'],3):f for f in payload['frames']};inputs={round(f['time'],3):f for f in payload.get('_denseFrames',[])};inputs.update(anchors)
 frames=[];annotated=[];crops={};tracks={};nextid=1;scene=0;previous_thumb=None;last_cal=None;last_key=-99
 for index,(t,frame) in enumerate(sorted(inputs.items())):
  im=Image.open(io.BytesIO(base64.b64decode(frame['image']))).convert('RGB');thumb=np.asarray(im.resize((32,18)),float)/255
  cut=previous_thumb is not None and np.mean(abs(thumb-previous_thumb))>.25
  if cut:scene+=1;tracks={};last_cal=None;last_key=-99
  if t-last_key>=.45:
   last_cal=calibrate(infer(im,'court'));last_key=t
  cal=last_cal
  detections=infer(im,'player');ball_detections=infer(im,'ball');players=[]
  for d in detections:
   if d['class']!=4 or d['confidence']<.32:continue
   x,y,x2,y2=d['box'];w=x2-x;h=y2-y
   if not .06<h<.65 or w<.01:continue
   crop=np.asarray(im.crop((int((x+w*.25)*im.width),int((y+h*.2)*im.height),int((x+w*.75)*im.width),int((y+h*.55)*im.height))))
   if not crop.size:continue
   pixels=crop.reshape(-1,3)/255
   white=float(np.mean((pixels.min(1)>.62)&(pixels.max(1)-pixels.min(1)<.24)))
   color=np.array([white,white,white])
   q={**d,'color':color,'foot':np.array([x+w/2,y2])}
   if cal:
    pos=project(cal['imageToCourt'],[q['foot']])[0]
    if not (-1.2<pos[0]<29.2 and -1.2<pos[1]<16.2):continue
    q['court']=pos.tolist()
   players.append(q)
  active=[a for a in tracks.values() if t-a['time']<.7];cost=[]
  for a in active:
   dt=t-a['time'];pred=a['foot']+a.get('velocity',np.zeros(2))*min(dt,.3);ha=a['box'][3]-a['box'][1];row=[]
   for b in players:
    hb=b['box'][3]-b['box'][1];dist=np.linalg.norm((b['foot']-pred)*[im.width/im.height,1])/max(ha,hb);color=np.linalg.norm(a['color']-b['color'])
    row.append(float(.55*dist+.6*color+.15*(1-overlap(a['box'],b['box']))) if dist<1.5 and not (a['color'][0]>.45 and b['color'][0]<.10 or b['color'][0]>.45 and a['color'][0]<.10) and .5<hb/ha<2 else 9.)
   cost.append(row+[.9]*len(active))
  for ai,bi in assign(cost):
   if bi>=len(players) or cost[ai][bi]>=.9:continue
   a=active[ai];b=players[bi];dt=max(.01,t-a['time']);b['color']=a['color']*.6+b['color']*.4
   b.update(id=a['id'],velocity=.5*a.get('velocity',np.zeros(2))+.5*(b['foot']-a['foot'])/dt,association=round(max(.5,1-cost[ai][bi]/1.8),3))
  out=[]
  for q in players:
   if 'id' not in q:q.update(id=f'P{nextid}',velocity=np.zeros(2),association=.65);nextid+=1
   q['time']=t;tracks[q['id']]=q;x,y,x2,y2=q['box']
   p={'trackId':q['id'],'x':round(x,5),'y':round(y,5),'w':round(x2-x,5),'h':round(y2-y,5),'confidence':q['confidence'],'association':q['association'],'jerseyColor':q['color'].round(3).tolist(),'jerseyWhite':round(float(q['color'][0]),3),'ball':'unknown'}
   if 'court' in q:p['court']=q['court']
   out.append(p)
  balls=[d for d in ball_detections if d['class']==0 and d['confidence']>=.28];ball=None
  # Candidate must be near a player; competing detections remain unknown.
  candidates=[]
  for d in balls:
   x,y,x2,y2=d['box'];bx,by=(x+x2)/2,(y+y2)/2
   distances=sorted([(math.hypot(max(p['x']-bx,0,bx-p['x']-p['w'])*im.width/im.height,max(p['y']-by,0,by-p['y']-p['h']))/p['h'],p['trackId']) for p in out])
   if distances and distances[0][0]<.45:candidates.append((d['confidence']-.3*distances[0][0],{'x':bx,'y':by,'confidence':d['confidence'],'near':distances[:2]}))
  if candidates:
   candidates.sort(key=lambda x:x[0],reverse=True)
   if len(candidates)==1 or candidates[0][0]-candidates[1][0]>.12:ball=candidates[0][1]
  frames.append({'time':t,'scene':scene,'cut':bool(cut),'people':out,'ball':ball,'ballCandidates':[b for _,b in candidates],'calibration':cal,'anchor':t in anchors})
  if t in anchors:
   for p in out:
    crop=im.crop((int(p['x']*im.width),int(p['y']*im.height),int((p['x']+p['w'])*im.width),int((p['y']+p['h'])*im.height)));crop.thumbnail((130,170));crops.setdefault(p['trackId'],[]).append((t,crop))
   draw=ImageDraw.Draw(im);font=ImageFont.load_default(size=18)
   for p in out:
    x,y=p['x']*im.width,p['y']*im.height;draw.rectangle((x,y,x+p['w']*im.width,y+p['h']*im.height),outline='#ffe070',width=2);draw.rectangle((x,y-23,x+50,y),fill='#132c2b');draw.text((x+2,y-22),p['trackId'],fill='white',font=font)
   buf=io.BytesIO();im.save(buf,format='JPEG',quality=78);clock_image=Image.open(io.BytesIO(base64.b64decode(frame['image']))).convert('RGB');clock_image=clock_image.crop((0,int(clock_image.height*.76),clock_image.width,clock_image.height));cb=io.BytesIO();clock_image.save(cb,format='JPEG',quality=84)
   annotated.append({'time':t,'image':base64.b64encode(buf.getvalue()).decode(),'scoreboard':base64.b64encode(cb.getvalue()).decode()})
  previous_thumb=thumb
  if progress and index%6==0:progress(index+1,len(inputs))
 # Track-level current-game jersey clustering, robust to arms, shoes and single bad crops.
 groups={}
 for f in frames:
  for p in f['people']:groups.setdefault(p['trackId'],[]).append(p)
 colors={pid:np.median([p['jerseyColor'] for p in rows],axis=0) for pid,rows in groups.items() if len(rows)>=4}
 if colors:
  cs=np.array(list(colors.values()));centers=np.array([cs[np.argmin(cs.mean(1))],cs[np.argmax(cs.mean(1))]])
  for _ in range(12):
   labels=np.argmin(np.linalg.norm(cs[:,None]-centers[None],axis=2),axis=1)
   for j in range(2):
    if np.any(labels==j):centers[j]=np.median(cs[labels==j],axis=0)
  teams={pid:'AB'[int(np.argmin(np.linalg.norm(centers-col,axis=1)))] for pid,col in colors.items()}
 else:teams={};centers=np.zeros((2,3))
 for f in frames:
  f['people']=[dict(p,team=teams[p['trackId']]) for p in f['people'] if p['trackId'] in teams]
 # Ball control requires a unique close player over multiple observations, not proximity alone.
 for f in frames:
  b=f['ball'];f['handler']=None
  if b and b['near'][0][0]<.16 and (len(b['near'])<2 or b['near'][1][0]-b['near'][0][0]>.12):f['handler']=b['near'][0][1]
 for f in frames:
  nearby=[q['handler'] for q in frames if q['scene']==f['scene'] and abs(q['time']-f['time'])<=.35 and q['handler']]
  if nearby:
   winner=max(set(nearby),key=nearby.count)
   if nearby.count(winner)>=2 and nearby.count(winner)/len(nearby)>=.75:
    f['handler']=winner
    for p in f['people']:p['ball']='on' if p['trackId']==winner else 'off'
   else:f['handler']=None
  else:f['handler']=None
 sheets=[];items=[(pid,rows) for pid,rows in crops.items() if len(rows)>=2]
 for start in range(0,len(items),4):
  sheet=Image.new('RGB',(450,800),'#edf0e7');sd=ImageDraw.Draw(sheet);font=ImageFont.load_default(size=17)
  for row,(pid,images) in enumerate(items[start:start+4]):
   picks=[images[0],images[len(images)//2],images[-1]]
   for col,(t,imc) in enumerate(picks):
    sheet.paste(imc,(col*150+(150-imc.width)//2,row*200+25));sd.text((col*150+5,row*200+3),f'{pid} {t:.2f}s',font=font,fill='black')
  buf=io.BytesIO();sheet.save(buf,format='JPEG',quality=82);sheets.append(base64.b64encode(buf.getvalue()).decode())
 vision={'identitySheets':sheets,'model':'Basketball YOLOv5 · ball / player / referee + YOLOv8 court','tracker':'velocity + global assignment + jersey v2','coordinateSystem':'normalized-image','aspectRatio':im.width/im.height,'frames':frames,'sampleFps':6,'roster':[], 'teamColors':{k:centers[i].tolist() for i,k in enumerate('AB')},'elapsedSeconds':round(time.monotonic()-started,2),'limitations':['位置、持球和球场投影均为视觉估计','临时编号可能在遮挡或切镜后变化','分数是可解释观察指数，不是因果贡献或真实EPV']}
 return vision,annotated
