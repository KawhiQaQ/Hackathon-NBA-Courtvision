"""YOLOX-S person detection + conservative appearance/IoU short-track association.
Image-plane estimates only. Track IDs are NOT player identities. No learned tracking claim.
"""
import base64,io,math,os,time,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import onnxruntime as ort
_SESSION=None

def sample_video(path,duration):
 """Six observations per second; original VLM frames are inserted separately as exact anchors."""
 ffmpeg=os.environ.get('VISION_FFMPEG','/opt/bin/ffmpeg')
 if not Path(ffmpeg).exists():
  import imageio_ffmpeg
  ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
 raw=subprocess.run([ffmpeg,'-nostdin','-v','error','-i',str(path),'-t',str(min(float(duration),40)),'-vf','fps=6,scale=960:-2','-f','image2pipe','-vcodec','mjpeg','-q:v','5','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90,check=True).stdout
 frames=[];offset=0
 while True:
  start=raw.find(b'\xff\xd8',offset)
  if start<0:break
  end=raw.find(b'\xff\xd9',start+2)
  if end<0:break
  frames.append({'time':round(len(frames)/6,3),'image':base64.b64encode(raw[start:end+2]).decode()});offset=end+2
 return frames

def session():
 global _SESSION
 if _SESSION is None:
  p=Path(os.environ.get('VISION_MODEL','/opt/models/yolox_s.onnx'))
  if not p.exists():p=Path(__file__).resolve().parents[1]/'vision-layer/models/yolox_s.onnx'
  options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
  _SESSION=ort.InferenceSession(str(p),sess_options=options,providers=['CPUExecutionProvider'])
 return _SESSION

def iou(a,b):
 x=max(a[0],b[0]);y=max(a[1],b[1]);xx=min(a[2],b[2]);yy=min(a[3],b[3]);inter=max(0,xx-x)*max(0,yy-y)
 return inter/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)

def detect(image):
 w,h=image.size;size=640;r=min(size/w,size/h);arr=np.full((size,size,3),114,dtype=np.uint8)
 arr[:int(h*r),:int(w*r)]=np.asarray(image.resize((int(w*r),int(h*r)),Image.Resampling.BILINEAR))[:,:,::-1]
 raw=session().run(None,{session().get_inputs()[0].name:np.ascontiguousarray(arr.transpose(2,0,1)[None],dtype=np.float32)})[0][0]
 grids=[];strides=[]
 for stride in [8,16,32]:
  yy,xx=np.meshgrid(np.arange(size//stride),np.arange(size//stride),indexing='ij');grids.append(np.stack((xx,yy),-1).reshape(-1,2));strides.extend([stride]*(size//stride)**2)
 strides=np.array(strides)[:,None];xy=(raw[:,:2]+np.concatenate(grids))*strides;wh=np.exp(np.clip(raw[:,2:4],-15,15))*strides
 boxes=np.concatenate((xy-wh/2,xy+wh/2),axis=1)/r;scores=raw[:,4]*raw[:,5] # COCO person only
 candidates=[]
 for j in np.argsort(scores)[::-1]:
  if scores[j]<.36:break
  b=boxes[j].copy();b[[0,2]]=np.clip(b[[0,2]],0,w);b[[1,3]]=np.clip(b[[1,3]],0,h)
  b=b/np.array([w,h,w,h]);height=b[3]-b[1];width=b[2]-b[0]
  if not .085<height<.72 or not .015<width<.32 or b[3]<.31 or b[1]>.88:continue
  if any(iou(b,c['box'])>.5 for c in candidates):continue
  # Torso color assists association; it is not a team or jersey classifier.
  x1,y1,x2,y2=b;crop=image.crop((int((x1+.2*width)*w),int((y1+.22*height)*h),int((x2-.2*width)*w),int((y1+.62*height)*h)))
  color=np.median(np.asarray(crop).reshape(-1,3),axis=0)/255 if crop.width and crop.height else np.zeros(3)
  candidates.append({'box':b.tolist(),'confidence':round(float(scores[j]),3),'color':color.tolist()})
  if len(candidates)==18:break
 return candidates

def associate(previous,current,dt):
 """One-to-one matching; ambiguous crossings start new tracks instead of claiming continuity."""
 edges=[]
 for i,a in enumerate(previous):
  for j,b in enumerate(current):
   ba,bb=a['box'],b['box'];ha=ba[3]-ba[1];hb=bb[3]-bb[1]
   if not .55<hb/ha<1.8:continue
   distance=math.hypot((ba[0]+ba[2]-bb[0]-bb[2])/2,(ba[1]+ba[3]-bb[1]-bb[3])/2)/max(ha,hb)
   color=float(np.linalg.norm(np.array(a['color'])-np.array(b['color'])))
   if distance>1.8 or color>.65:continue
   cost=.5*min(distance/1.8,1)+.3*color+.2*(1-iou(ba,bb))
   edges.append((cost,i,j))
 used_a=set();used_b=set()
 for cost,i,j in sorted(edges):
  if i in used_a or j in used_b or cost>.67:continue
  alternatives=[c for c,ii,jj in edges if (ii==i and jj!=j or jj==j and ii!=i)]
  margin=min(alternatives,default=cost+.3)-cost
  if margin<.045:continue
  current[j].update(trackId=previous[i]['trackId'],association=round(max(0,1-cost/.85),3));used_a.add(i);used_b.add(j)
 return current

def build_legacy_vision(payload,progress=None):
 started=time.monotonic();previous=[];previous_thumb=None;frames=[];annotated=[];next_id=1;scene=0;last_time=None
 anchors={round(f['time'],3):f for f in payload['frames']}
 combined={round(f['time'],3):f for f in payload.get('_denseFrames',[])};combined.update(anchors)
 inputs=[combined[t] for t in sorted(combined)]
 for index,frame in enumerate(inputs):
  im=Image.open(io.BytesIO(base64.b64decode(frame['image']))).convert('RGB');thumb=np.asarray(im.resize((32,18)),dtype=np.float32)/255
  cut=previous_thumb is not None and float(np.mean(abs(thumb-previous_thumb)))>.28
  if cut:scene+=1;previous=[]
  current=detect(im)
  if previous and last_time is not None and frame['time']-last_time<=1.3:associate(previous,current,frame['time']-last_time)
  for p in current:
   if 'trackId' not in p:p.update(trackId=f'T{next_id}',association=0.0);next_id+=1
  out=[];draw=ImageDraw.Draw(im);font=ImageFont.load_default(size=17)
  for p in current:
   x1,y1,x2,y2=p['box'];label=p['trackId'];coords=(x1*im.width,y1*im.height,x2*im.width,y2*im.height)
   draw.rectangle(coords,outline='#9fffbe',width=2);tx,ty=coords[0],max(0,coords[1]-22);draw.rectangle((tx,ty,tx+45,ty+21),fill='#102c23');draw.text((tx+2,ty),label,font=font,fill='white')
   out.append({'trackId':label,'x':round(x1,5),'y':round(y1,5),'w':round(x2-x1,5),'h':round(y2-y1,5),'confidence':p['confidence'],'association':p['association'],'jerseyColor':[round(float(c),3) for c in p['color']]})
  anchor=round(frame['time'],3) in anchors
  crop_image=None
  if anchor:
   original=Image.open(io.BytesIO(base64.b64decode(frame['image']))).convert('RGB')
   sheet=Image.new('RGB',(960,math.ceil(max(1,len(out))/8)*190),'#e7ebec');sd=ImageDraw.Draw(sheet)
   for j,p in enumerate(out):
    crop=original.crop((int(p['x']*original.width),int(p['y']*original.height),int((p['x']+p['w'])*original.width),int((p['y']+p['h'])*original.height)));crop.thumbnail((112,160));cx=(j%8)*120+(120-crop.width)//2;cy=(j//8)*190+25;sheet.paste(crop,(cx,cy));sd.text(((j%8)*120+8,(j//8)*190+3),p['trackId'],fill='black',font=font)
   sb=io.BytesIO();sheet.save(sb,format='JPEG',quality=85);crop_image=base64.b64encode(sb.getvalue()).decode()
  frames.append({'time':frame['time'],'scene':scene,'cut':cut,'people':out,'anchor':anchor})
  if anchor:
   buffer=io.BytesIO();im.save(buffer,format='JPEG',quality=82)
   annotated.append({'time':frame['time'],'image':base64.b64encode(buffer.getvalue()).decode(),'crops':crop_image})
  previous=current;previous_thumb=thumb;last_time=frame['time']
  if progress and index%12==0:progress(index+1,len(inputs))
 counts={}
 for f in frames:
  for p in f['people']:counts[p['trackId']]=counts.get(p['trackId'],0)+1
 return {'model':'YOLOX-S · COCO pretrained','tracker':'appearance + IoU association v1','coordinateSystem':'normalized-image','aspectRatio':im.width/im.height,
         'frames':frames,'sampleFps':6 if payload.get('_denseFrames') else None,'anchorFrameCount':len(anchors),'trackCount':len(counts),'stableTrackCount':sum(n>=3 for n in counts.values()),'elapsedSeconds':round(time.monotonic()-started,2),
         'limitations':['人物检测可能包含裁判或场边人员','临时轨迹编号不等于球员身份','6fps采样估计，遮挡和切镜可断轨','画面距离不等于球场米数']},annotated


def build_vision(payload,progress=None):
 from court_vision import build
 return build(payload,progress)
