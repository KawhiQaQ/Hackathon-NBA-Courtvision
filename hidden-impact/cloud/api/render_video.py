"""Render a focused, time-synchronized tactical replay; no static screenshot montage."""
import subprocess,os,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

def ffmpeg():
 p=os.environ.get('VISION_FFMPEG','/opt/bin/ffmpeg')
 if Path(p).exists():return p
 import imageio_ffmpeg
 return imageio_ffmpeg.get_ffmpeg_exe()

def projection(h,p):
 x,y=p;d=h[2][0]*x+h[2][1]*y+h[2][2]
 return ((h[0][0]*x+h[0][1]*y+h[0][2])/d,(h[1][0]*x+h[1][1]*y+h[1][2])/d) if abs(d)>.0001 else None

def people_at(frames,t):
 before=next((f for f in reversed(frames) if f['time']<=t),None);after=next((f for f in frames if f['time']>=t),None)
 if not before or not after or before['scene']!=after['scene'] or after['time']-before['time']>.4:return []
 a={p['trackId']:p for p in after['people']};k=(t-before['time'])/max(.001,after['time']-before['time']);out=[]
 for p in before['people']:
  q=a.get(p['trackId'])
  if not q:continue
  o={**p,**{n:p[n]+k*(q[n]-p[n]) for n in ['x','y','w','h']}}
  if 'court' in p and 'court' in q:o['court']=[p['court'][i]+k*(q['court'][i]-p['court'][i]) for i in range(2)]
  out.append(o)
 return out

from functools import lru_cache

@lru_cache(maxsize=8)
def font(size):
 path=Path(__file__).parent/'fonts/NotoSansSC.ttf'
 if not path.exists():raise RuntimeError('Missing bundled CJK font')
 return ImageFont.truetype(str(path),size)


def wrap(draw,text,size,width):
 rows=[];row=''
 for c in text:
  if draw.textlength(row+c,font=font(size))>width and row:rows.append(row);row=''
  row+=c
 if row:rows.append(row)
 return rows


def composite(image,result,t):
 """Single compositor for the replay and story frames, driven by measured data."""
 manifest=result['presentation'];motion=result['presentationMotion'];w,h=image.size
 im=Image.new('RGB',(w,h+144),'#102b29');im.paste(image,(0,44))
 draw=ImageDraw.Draw(im,'RGBA')
 draw.text((20,10),'HIDDEN IMPACT  /  '+manifest['actor']['label'],font=font(19),fill='#f5d68e')
 draw.text((w-140,11),f"{manifest['score']} / 100",font=font(17),fill='white')
 frame=motion['frames'][min(len(motion['frames'])-1,max(0,round(t*motion['fps'])))];colors={r['id']:r for r in manifest['roles']}
 for i,p in enumerate(frame['people']):
  role=colors[p['trackId']];color=tuple(bytes.fromhex(role['color'][1:]))
  if p.get('offscreen'):
   # Identity stays visible in a status strip; no fictitious person location.
   x=18+i*w/3;y=h+50
   draw.text((x,y),role['displayName']+' · 定位中',font=font(13),fill=(*color,255));continue
  x=(p['x']+p['w']/2)*w;y=(p['y']+p['h'])*h+44;radius=max(15,p['w']*w*.7)
  draw.ellipse((x-radius-8,y-10,x+radius+8,y+10),fill=(*color,45))
  draw.ellipse((x-radius,y-5,x+radius,y+5),outline=(*color,255),width=3)
  top=max(48,p['y']*h+44-25-i*3);text=role['displayName'];length=draw.textlength(text,font=font(14))+14
  lx=max(4,min(w-length-4,x-length/2))
  draw.rounded_rectangle((lx,top,lx+length,top+23),radius=6,fill=(14,38,36,225))
  draw.text((lx+7,top+2),text,font=font(14),fill=(*color,255))
 arrow=frame.get('heroArrow')
 if arrow:
  points=[(x/motion['width']*w,y/motion['height']*h+44) for x,y in arrow['points']]
  draw.line(points,fill=(255,216,112,255),width=5)
  a,b=points[-2:];ang=math.atan2(b[1]-a[1],b[0]-a[0]);length=15
  draw.polygon([b,(b[0]-length*math.cos(ang-.45),b[1]-length*math.sin(ang-.45)),(b[0]-length*math.cos(ang+.45),b[1]-length*math.sin(ang+.45))],fill=(255,216,112,255))
 segments=manifest['insights'].get('narration',{}).get('segments',[])
 seg=next((s for s in segments if s['start']<=t<s['end']),None)
 if seg:title,text=seg['title'],seg['text']
 else:title,text=manifest['actionTitle'],''
 draw.text((20,h+76),title,font=font(17),fill='white')
 for i,line in enumerate(wrap(draw,text,14,w-40)[:2]):draw.text((20,h+101+i*20),line,font=font(14),fill='#d7e2d9')
 return im


def render(source,result,output,story_dir=None):
 from presentation import build
 if result.get('presentation',{}).get('mode')!='analysis':build(result)
 if result['presentation'].get('status')!='ready':return None
 manifest=result['presentation'];start=0;end=result['video']['duration'];width=960
 height=round(width/result['vision'].get('aspectRatio',16/9)/2)*2;fps=result['presentationMotion']['fps']
 target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
 story_dir=Path(story_dir) if story_dir else target.parent;story_dir.mkdir(parents=True,exist_ok=True)
 decode=subprocess.Popen([ffmpeg(),'-v','error','-i',str(source),'-t',str(end),'-vf',f'fps={fps},scale={width}:{height}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 encode=subprocess.Popen([ffmpeg(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height+144}','-r',str(fps),'-i','pipe:0','-i',str(source),'-map','0:v','-map','1:a?','-t',str(end),'-c:v','libx264','-pix_fmt','yuv420p','-preset','veryfast','-crf','21','-c:a','aac','-movflags','+faststart',str(output)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
 index=0;saved=set()
 try:
  while True:
   raw=decode.stdout.read(width*height*3)
   if len(raw)!=width*height*3:break
   t=index/fps;im=composite(Image.frombytes('RGB',(width,height),raw),result,t)
   for j,f in enumerate(manifest['evidence']):
    if j not in saved and index>=round(f['time']*fps):
     im.save(story_dir/f['image'],quality=90);saved.add(j)
   encode.stdin.write(im.tobytes());index+=1
  encode.stdin.close();errors=encode.stderr.read();code=encode.wait(timeout=60);decode.wait(timeout=10)
  if code:raise RuntimeError(errors.decode()[-500:])
  if index<max(1,int(end*fps*.95)) or len(saved)!=len(manifest['evidence']):raise RuntimeError('Incomplete replay or evidence frames')
 finally:
  for process in [decode,encode]:
   if process.poll() is None:process.kill();process.wait()
   for stream in [process.stdin,process.stdout,process.stderr]:
    if stream and not stream.closed:stream.close()
 return {'start':0,'end':end,'fps':fps,'frameCount':index,'focusPlayerId':manifest['actor']['id'],'eventId':manifest['eventId'],'renderer':'presentation-v1'}
