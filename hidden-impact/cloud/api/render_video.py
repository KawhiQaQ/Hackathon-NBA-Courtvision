"""Render a focused, time-synchronized tactical replay; no static screenshot montage."""
import subprocess,os,math,io
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter

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

@lru_cache(maxsize=32)
def font(size):
 path=Path(__file__).parent/'fonts/NotoSansSC.ttf'
 if not path.exists():raise RuntimeError('Missing bundled CJK font')
 face=ImageFont.truetype(str(path),size)
 # Bundled Noto variable font defaults to Thin (100), too faint over footage.
 face.set_variation_by_axes([500 if size<24 else 600])
 return face


def wrap(draw,text,size,width):
 rows=[];row=''
 for c in text:
  if draw.textlength(row+c,font=font(size))>width and row:rows.append(row);row=''
  row+=c
 if row:rows.append(row)
 return rows


class ScaledDraw:
 """Render layout units as native-resolution geometry and font glyphs."""
 def __init__(self,image,scale):self.draw=ImageDraw.Draw(image,'RGBA');self.scale=scale
 def coords(self,xy):
  return tuple(self.coords(v) if isinstance(v,(tuple,list)) else v*self.scale for v in xy)
 def text(self,xy,text,font,**kwargs):
  self.draw.text(self.coords(xy),text,font=globals()['font'](max(1,round(font.size*self.scale))),**kwargs)
 def textlength(self,text,font):
  return self.draw.textlength(text,font=globals()['font'](max(1,round(font.size*self.scale))))/self.scale
 def ellipse(self,xy,**kwargs):self.draw.ellipse(self.coords(xy),**kwargs)
 def line(self,xy,width=1,**kwargs):self.draw.line(self.coords(xy),width=max(1,round(width*self.scale)),**kwargs)
 def rounded_rectangle(self,xy,radius=0,width=1,**kwargs):
  self.draw.rounded_rectangle(self.coords(xy),radius=radius*self.scale,width=max(1,round(width*self.scale)),**kwargs)


def source_dimensions(source):
 """Decode one frame to respect display rotation and real media dimensions.
 No dependency on untrusted client aspect-ratio metadata or a separate ffprobe.
 """
 raw=subprocess.run([ffmpeg(),'-nostdin','-v','error','-i',str(source),'-frames:v','1','-f','image2pipe','-vcodec','png','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,check=True).stdout
 with Image.open(io.BytesIO(raw)) as frame:return frame.size


def output_dimensions(source):
 sw,sh=source_dimensions(source);ratio=min(1,1920/sw,1080/sh)
 width=max(2,int(sw*ratio/2)*2);height=max(2,int(sh*ratio/2)*2)
 return width,height,round(144*width/960/2)*2,(sw,sh)


def direction_ribbon(image,points,color,pixel_scale=1):
 """Antialiased tapered route ribbon, with a clear head and restrained shadow."""
 if len(points)<2:return
 pad=math.ceil(18*pixel_scale);left=math.floor(min(p[0] for p in points))-pad;top=math.floor(min(p[1] for p in points))-pad
 width=math.ceil(max(p[0] for p in points))-left+pad;height=math.ceil(max(p[1] for p in points))-top+pad
 scale=3;layer=Image.new('RGBA',(width*scale,height*scale));d=ImageDraw.Draw(layer)
 local=[((x-left)*scale,(y-top)*scale) for x,y in points]
 # Reserve the final 15 pixels for the arrowhead, preventing a blunt shaft tip.
 end=local[-1];a=local[-2];angle=math.atan2(end[1]-a[1],end[0]-a[0]);u=(math.cos(angle),math.sin(angle));n=(-u[1],u[0])
 head=15*scale*pixel_scale;base=(end[0]-u[0]*head,end[1]-u[1]*head)
 shaft=[p for p in local[:-1] if math.dist(p,end)>head]+[base]
 edges=[[],[]]
 for i,p in enumerate(shaft):
  before=shaft[max(0,i-1)];after=shaft[min(len(shaft)-1,i+1)];ang=math.atan2(after[1]-before[1],after[0]-before[0]);half=(1.6+1.6*i/max(1,len(shaft)-1))*scale*pixel_scale
  for side,sign in enumerate((1,-1)):edges[side].append((p[0]-sign*math.sin(ang)*half,p[1]+sign*math.cos(ang)*half))
 polygon=edges[0]+[(base[0]+n[0]*7*scale*pixel_scale,base[1]+n[1]*7*scale*pixel_scale),end,(base[0]-n[0]*7*scale*pixel_scale,base[1]-n[1]*7*scale*pixel_scale)]+list(reversed(edges[1]))
 d.polygon(polygon,fill=(*color,245));d.line(polygon+[polygon[0]],fill=(14,28,35,220),width=max(1,round(scale*pixel_scale)),joint='curve')
 # A fine inner highlight makes the two colors legible over wood and uniforms.
 if len(shaft)>1:d.line(shaft,fill=tuple(round(c*.4+255*.6) for c in color)+(210,),width=max(1,round(scale*pixel_scale)),joint='curve')
 layer=layer.resize((width,height),Image.Resampling.LANCZOS)
 shadow=Image.new('RGBA',layer.size,(0,0,0,0));shadow.putalpha(layer.getchannel('A').filter(ImageFilter.GaussianBlur(2*pixel_scale)).point(lambda v:round(v*.35)))
 image.paste(shadow,(left,top+round(2*pixel_scale)),shadow);image.paste(layer,(left,top),layer)


def composite(image,result,t):
 """Single compositor for the replay and story frames, driven by measured data."""
 manifest=result['presentation'];motion=result['presentationMotion'];w,h=image.size;pixel_scale=w/960
 frame=motion['frames'][min(len(motion['frames'])-1,max(0,round(t*motion['fps'])))];colors={r['id']:r for r in manifest['roles']}
 # One broadcast language for every clip: fixed identities, soft focus, nameplates
 # and two measured direction cues. No foot effects when grounding is uncertain.
 visible=[p for p in frame['people'] if not p.get('offscreen')]
 if visible:
  mask=Image.new('L',(w//4,h//4),48);md=ImageDraw.Draw(mask)
  for p in visible:
   x,y,bw,bh=p['x']*w/4,p['y']*h/4,p['w']*w/4,p['h']*h/4
   md.ellipse((x-8*pixel_scale,y-5*pixel_scale,x+bw+8*pixel_scale,y+bh+5*pixel_scale),fill=0)
  mask=mask.filter(ImageFilter.GaussianBlur(6*pixel_scale)).resize((w,h))
  shade=Image.new('RGB',(w,h),'#061823');image=Image.composite(shade,image,mask)
 im=Image.new('RGB',(w,h+round(144*pixel_scale/2)*2),'#0b2029');im.paste(image,(0,round(44*pixel_scale)))
 w,h=960,h/pixel_scale
 draw=ScaledDraw(im,pixel_scale)
 draw.text((20,10),'HIDDEN IMPACT  /  '+manifest['actor']['label'],font=font(19),fill='#f5d68e')
 draw.text((w-130,11),'TEAM 14',font=font(17),fill='#aac1b3')
 for key,idx in [('defenderArrow',2),('heroArrow',0)]:
  arrow=frame.get(key)
  if arrow:
   points=[(x/motion['width']*w,y/motion['height']*h+44) for x,y in arrow['points']]
   direction_ribbon(im,[(x*pixel_scale,y*pixel_scale) for x,y in points],tuple(bytes.fromhex(manifest['roles'][idx]['color'][1:])),pixel_scale)
 occupied=[]
 for i,p in enumerate(frame['people']):
  role=colors[p['trackId']];color=tuple(bytes.fromhex(role['color'][1:]))
  # The identity rail remains in the same order throughout occlusions and cuts.
  status=' · 画外' if p.get('offscreen') else ''
  rx=18+i*w/3;ry=h+51
  draw.ellipse((rx,ry+4,rx+6,ry+10),fill=(*color,255))
  draw.text((rx+13,ry-2),role['displayName']+status,font=font(13),fill=(*color,255))
  if p.get('offscreen'):continue
  x=(p['x']+p['w']/2)*w
  top=max(48,p['y']*h+44-35);text=role['displayName'].replace('尼克斯 ','').replace('马刺 ','');length=draw.textlength(text,font=font(18))+28
  lx=max(8,min(w-length-8,x-length/2))
  # Prefer stacked labels above the action, with a leader to the observed body.
  while any(lx<rr+8 and lx+length>ll-8 and top<bb+7 and top+29>tt-7 for ll,tt,rr,bb in occupied) and top>83:top-=35
  occupied.append((lx,top,lx+length,top+29))
  draw.line((x,p['y']*h+44,lx+length/2,top+29),fill=(*color,180),width=1)
  draw.rounded_rectangle((lx,top,lx+length,top+29),radius=7,fill=(9,30,30,235),outline=(*color,110),width=1)
  draw.ellipse((lx+8,top+12,lx+12,top+16),fill=(*color,255))
  draw.text((lx+18,top+2),text,font=font(18),fill=(*color,255))
 # The same source-linked numbers now travel with the MP4, not only the web page.
 from broadcast import card_at
 card=card_at(manifest['insights'],t,result['video']['duration'])
 if card:
  cw=272;ch=104+len(card['lines'])*19
  # Choose the side with less tracked action; stable within each one-second beat.
  sample=motion['frames'][min(len(motion['frames'])-1,int(t)*motion['fps'])]
  crowded=sum(p['x']+p['w']/2>.5 for p in sample['people'] if not p.get('offscreen'))
  cx=16 if crowded>len(visible)/2 else w-cw-16;cy=56
  draw.rounded_rectangle((cx,cy,cx+cw,cy+ch),radius=10,fill=(6,24,33,232),outline=(119,207,228,140))
  draw.text((cx+13,cy+10),card['title'],font=font(14),fill='#b6d4d7')
  draw.text((cx+13,cy+31),card['value'],font=font(32),fill='#77cfe4')
  if card['fraction'] is not None:
   draw.rounded_rectangle((cx+112,cy+49,cx+cw-14,cy+55),radius=3,fill='#314852')
   draw.rounded_rectangle((cx+112,cy+49,cx+112+(cw-126)*card['fraction'],cy+55),radius=3,fill='#77cfe4')
  for j,line in enumerate(card['lines']):
   draw.text((cx+13,cy+75+j*19),wrap(draw,line,12,cw-26)[0],font=font(12),fill='#eef4ec')
  draw.text((cx+13,cy+ch-21),card['source'],font=font(10),fill='#9db5b8')
 segments=manifest['insights'].get('narration',{}).get('segments',[])
 seg=next((s for s in segments if s['start']<=t<s['end']),None)
 if seg:title,text=seg['title'],seg['text']
 else:title,text=manifest['actionTitle'],''
 ai=manifest['insights'].get('narration',{}).get('modelInvoked')
 draw.text((20,h+76),('AI 解说 · ' if ai else '')+title,font=font(17),fill='white')
 for i,line in enumerate(wrap(draw,text,14,w-40)[:2]):draw.text((20,h+101+i*20),line,font=font(14),fill='#d7e2d9')
 return im


def render(source,result,output,story_dir=None):
 from presentation import build
 if result.get('presentation',{}).get('mode')!='analysis':build(result)
 if result['presentation'].get('status')!='ready':return None
 manifest=result['presentation'];start=0;end=result['video']['duration']
 width,height,band,original=output_dimensions(source);fps=result['presentationMotion']['fps']
 manifest.update(width=width,height=height+band,pictureWidth=width,pictureHeight=height,sourceWidth=original[0],sourceHeight=original[1],renderStyle='data-broadcast-hd-v5',encoding={'codec':'h264','crf':17,'preset':'fast'})
 target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
 story_dir=Path(story_dir) if story_dir else target.parent;story_dir.mkdir(parents=True,exist_ok=True)
 decode=subprocess.Popen([ffmpeg(),'-v','error','-i',str(source),'-t',str(end),'-vf',f'fps={fps},scale={width}:{height}:flags=lanczos','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 encode=subprocess.Popen([ffmpeg(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height+band}','-r',str(fps),'-i','pipe:0','-i',str(source),'-map','0:v','-map','1:a?','-t',str(end),'-c:v','libx264','-pix_fmt','yuv420p','-preset','fast','-crf','17','-c:a','aac','-movflags','+faststart',str(output)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
 index=0;saved=set()
 try:
  while True:
   raw=decode.stdout.read(width*height*3)
   if len(raw)!=width*height*3:break
   t=index/fps;im=composite(Image.frombytes('RGB',(width,height),raw),result,t)
   for j,f in enumerate(manifest['evidence']):
    if j not in saved and index>=round(f['time']*fps):
     im.save(story_dir/f['image'],quality=95,subsampling=0);saved.add(j)
   encode.stdin.write(im.tobytes());index+=1
  encode.stdin.close();errors=encode.stderr.read();code=encode.wait(timeout=60);decode.wait(timeout=10)
  if code:raise RuntimeError(errors.decode()[-500:])
  if index<max(1,int(end*fps*.95)) or len(saved)!=len(manifest['evidence']):raise RuntimeError('Incomplete replay or evidence frames')
 finally:
  for process in [decode,encode]:
   if process.poll() is None:process.kill();process.wait()
   for stream in [process.stdin,process.stdout,process.stderr]:
    if stream and not stream.closed:stream.close()
 return {'start':0,'end':end,'fps':fps,'frameCount':index,'focusPlayerId':manifest['actor']['id'],'eventId':manifest['eventId'],'renderer':'data-broadcast-hd-v5','width':width,'height':height+band,'pictureWidth':width,'pictureHeight':height}
