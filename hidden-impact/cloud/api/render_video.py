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
  if c=='\n':rows.append(row);row='';continue
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


@lru_cache(maxsize=4)
def broadcast_shell(width,height):
 """A quiet forest-black frame with warm editorial paper for the commentary."""
 scale=width/960;band=round(144*scale/2)*2
 im=Image.new('RGB',(width,height+band),'#0b1712')
 d=ImageDraw.Draw(im)
 for y in range(round(44*scale)):
  k=y/max(1,44*scale)
  d.line((0,y,width,y),fill=(round(19-8*k),round(35-12*k),round(27-9*k)))
 return im


def instrument_panel(draw,bounds):
 """Shared fine-rule enclosure for statistics and the tactical inset."""
 x,y,w,h=bounds
 draw.rounded_rectangle((x+2,y+4,x+w+2,y+h+4),radius=5,fill=(0,0,0,65))
 draw.rounded_rectangle((x,y,x+w,y+h),radius=4,fill=(10,24,18,246),outline=(202,190,153,115))
 draw.line((x+14,y+1,x+54,y+1),fill='#d9bf82',width=2)
 draw.line((x+14,y+48,x+w-14,y+48),fill='#354237',width=1)


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
  mask=Image.new('L',(w//4,h//4),30);md=ImageDraw.Draw(mask)
  for p in visible:
   x,y,bw,bh=p['x']*w/4,p['y']*h/4,p['w']*w/4,p['h']*h/4
   md.ellipse((x-8*pixel_scale,y-5*pixel_scale,x+bw+8*pixel_scale,y+bh+5*pixel_scale),fill=0)
  mask=mask.filter(ImageFilter.GaussianBlur(6*pixel_scale)).resize((w,h))
  shade=Image.new('RGB',(w,h),'#08150e');image=Image.composite(shade,image,mask)
 im=broadcast_shell(w,h).copy();im.paste(image,(0,round(44*pixel_scale)))
 w,h=960,h/pixel_scale
 draw=ScaledDraw(im,pixel_scale)
 draw.text((20,15),'TEAM 14',font=font(11),fill='#d9bf82')
 draw.text((80,1),'HI',font=font(28),fill='#e9dfc7')
 draw.line((118,13,118,31),fill='#475043',width=1)
 draw.text((130,12),'Hidden Impact',font=font(15),fill='#d2d7c8')
 draw.text((270,13),manifest['actor']['label'],font=font(14),fill='#97a792')
 from story_direction import build_direction,phase_at,draw_chapters
 direction=manifest.get('direction') or build_direction(manifest,result['video']['duration'])
 manifest['direction']=direction
 from tactical_board import build_board,draw_board
 if 'board' not in direction:direction['board']=build_board(motion,manifest)
 draw_chapters(draw,font,direction,t,result['video']['duration'])
 for key,idx in [('defenderArrow',2),('heroArrow',0)]:
  arrow=frame.get(key)
  if arrow:
   points=[(x/motion['width']*w,y/motion['height']*h+44) for x,y in arrow['points']]
   direction_ribbon(im,[(x*pixel_scale,y*pixel_scale) for x,y in points],tuple(bytes.fromhex(manifest['roles'][idx]['color'][1:])),pixel_scale)
 # The same source-linked numbers now travel with the MP4, not only the web page.
 from broadcast import card_at,actor_card
 card=card_at(manifest['insights'],t,result['video']['duration'])
 phase=phase_at(direction,t)
 if phase==0 and direction.get('focusWindow') and manifest['insights'].get('actorProfile'):
  card=actor_card(manifest['insights']['actorProfile'],t,direction['focusWindow'][0]) or card
 from panel_layout import nameplates,card_position
 card_xy=card_position(motion,manifest,card['kind'],result['video']['duration'],h,lambda text:draw.textlength(text,font=font(18))) if card and phase!=1 else None
 obstacle=None
 if card_xy:
  cx,cy=card_xy;obstacle=(cx,cy,cx+(296 if card['kind']=='shot' else 312),cy+(160 if card['kind']=='shot' else 202))
 layouts={p['trackId']:(text,x,box) for p,text,x,box in nameplates(frame['people'],colors,w,h,lambda text:draw.textlength(text,font=font(18)),obstacle)}
 for i,p in enumerate(frame['people']):
  role=colors[p['trackId']];color=tuple(bytes.fromhex(role['color'][1:]))
  # The identity rail remains in the same order throughout occlusions and cuts.
  status=' · 画外' if p.get('offscreen') else ''
  rx=18+i*w/3;ry=h+51
  draw.line((rx,ry+2,rx,ry+16),fill=(*color,255),width=2)
  draw.text((rx+10,ry-2),role['displayName']+status,font=font(13),fill='#dce1d4')
  if p.get('offscreen'):continue
  text,x,(lx,top,right,bottom)=layouts[p['trackId']];length=right-lx
  anchor=p['y']*h+44
  draw.line((x,anchor,lx+length/2,top+29),fill=(*color,210),width=1)
  draw.ellipse((x-2,anchor-2,x+2,anchor+2),fill=(*color,255))
  draw.rounded_rectangle((lx+1,top+2,lx+length+1,top+31),radius=3,fill=(0,0,0,65))
  draw.rounded_rectangle((lx,top,lx+length,top+29),radius=3,fill=(10,23,18,242),outline=(*color,110),width=1)
  draw.line((lx+1,top+6,lx+1,top+23),fill=(*color,255),width=3)
  draw.text((lx+13,top+2),text,font=font(18),fill=(*color,255))
 board_drawn=False
 if phase==1:
  # Keep the tactics board fixed on the quiet side throughout the action.
  rows=[p for i,f in enumerate(motion['frames'][::max(1,motion['fps'])]) if phase_at(direction,i)==1 for p in f['people'] if not p.get('offscreen')]
  cx=16 if sum(p['x']+p['w']/2>.5 for p in rows)>len(rows)/2 else w-328
  board_drawn=draw_board(draw,font,motion,manifest,t,(cx,56,312,202))
 if card and not board_drawn:
  compact=card['kind']=='shot'
  cw=296 if compact else 312;ch=160 if compact else 202
  # Use real body/nameplate overlap, including the start of the chapter.
  cx,cy=card_xy or card_position(motion,manifest,card['kind'],result['video']['duration'],h,lambda text:draw.textlength(text,font=font(18)))
  instrument_panel(draw,(cx,cy,cw,ch))
  draw.text((cx+16,cy+7),card['title'],font=font(19),fill='#eee8d9')
  draw.text((cx+16,cy+31),card['subject'],font=font(12),fill='#a8b3a4')
  lo,hi=card['domain'];bx=cx+91;bw=cw-173
  zero=bx+(0-lo)/(hi-lo)*bw
  for j,row in enumerate(card['rows']):
   y=cy+(55 if compact else 65)+j*(28 if compact else 34);color='#8f9e90' if row['baseline'] else ('#9bddb8' if compact else '#dcc28a')
   draw.text((cx+16,y-1),row['label'],font=font(13),fill=color)
   draw.rounded_rectangle((bx,y+6,bx+bw,y+16),radius=1,fill='#2a392e')
   end=bx+(row['value']-lo)/(hi-lo)*bw
   if abs(end-zero)>.1:
    draw.rounded_rectangle((min(zero,end),y+6,max(zero,end),y+16),radius=min(1,abs(end-zero)/2),fill=color)
    draw.line((end,y+4,end,y+18),fill=color,width=1)
   if lo<0:draw.line((zero,y+1,zero,y+21),fill='#c7d3d6',width=1)
   value=f"{row['value']:.1f}%" if card['kind'] in ('shot','actor-finishing') else f"{row['value']:+.2f}"
   draw.text((bx+bw+8,y-2),value,font=font(16),fill=color)
  value_y=108 if compact else 135;unit_y=120 if compact else 150
  value_font=23 if compact else 29
  delta=card['delta']
  if card.get('headline'):
   draw.text((cx+16,cy+value_y),card['headline'],font=font(value_font),fill='#e3c991')
   offset=draw.textlength(card['headline'],font=font(value_font))
   draw.text((cx+23+offset,cy+unit_y),card['headlineUnit'],font=font(12),fill='#f5d68e')
  elif delta is not None:
   precision=1 if card['kind']=='shot' else 2
   number=f'{delta:+.{precision}f}'
   gain=card['kind']=='shot' and delta>0.00001
   ink='#9bddb8' if gain else '#e3c991'
   start=cx+16
   if gain:
    # A compact rising arrow accompanies the percentage-point difference.
    ax=start+2;ay=cy+value_y+19
    draw.line([(ax,ay),(ax+7,ay-7),(ax+12,ay-3),(ax+22,ay-16)],fill=ink,width=3)
    draw.line([(ax+12,ay-16),(ax+22,ay-16),(ax+22,ay-6)],fill=ink,width=3)
    start+=32
   draw.text((start,cy+value_y),number,font=font(value_font),fill=ink)
   offset=draw.textlength(number,font=font(value_font))
   draw.text((start+7+offset,cy+unit_y),card['unit'],font=font(12),fill=ink)
  else:draw.text((cx+16,cy+value_y+9),'基准暂无',font=font(16),fill='#b6c8cc')
  history=card.get('history',[])
  if 1<=len(history)<=10:
   for j,shot in enumerate(history):
    x=cx+184+j*11;y=cy+157
    draw.ellipse((x-3,y-3,x+3,y+3),fill='#f4c45e' if shot['made'] else '#0b2029',outline='#f4c45e')
  if card['outcome']:
   text=card['outcome'];tw=draw.textlength(text,font=font(12))
   draw.text((cx+cw-16-tw,cy+unit_y),text,font=font(12),fill='#eef4ec')
  draw.text((cx+16,cy+(140 if compact else 180)),card['context'],font=font(11),fill='#9aaa99')
 return paint_commentary(im,result,t)


def paint_commentary(im,result,t,beat=None,progress=1):
 """Only redraw the caption strip during holds; all visual evidence stays still."""
 manifest=result['presentation'];scale=im.width/960;h=im.height/scale-144
 draw=ScaledDraw(im,scale)
 draw.rounded_rectangle((0,h+73,960,h+144),radius=0,fill='#e8e5d9')
 draw.line((0,h+73,960,h+73),fill='#c4b487',width=1)
 draw.line((78,h+85,78,h+132),fill='#c8c7b7',width=1)
 if beat is None:
  segments=manifest['insights'].get('narration',{}).get('segments',[])
  beat=next((s for s in segments if s['start']<=t<s['end']),{})
  timeline=manifest.get('playback')
  if timeline:
   previous=[b for b in timeline['beats'] if b['sourceTime']<=t]
   beat=previous[-1] if previous else {'title':manifest['actionTitle'],'text':''}
 title=beat.get('title') or manifest['actionTitle'];text=beat.get('text','')
 typed=text[:math.ceil(len(text)*max(0,min(1,progress)))]
 beats=(manifest.get('playback') or {}).get('beats',[]) or manifest['insights'].get('narration',{}).get('segments',[])
 index=max(1,sum(b.get('sourceTime',b.get('start',0))<=t for b in beats))
 draw.text((23,h+78),f'{index:02}',font=font(24),fill='#334a3a')
 draw.text((23,h+113),'解读',font=font(11),fill='#63705c')
 draw.text((94,h+76),title,font=font(17),fill='#263d2e')
 for i,line in enumerate(wrap(draw,typed+('▏' if progress<1 else ''),17,844)[:2]):
  draw.text((94,h+101+i*21),line,font=font(17),fill='#263d2e')
 return im


def render(source,result,output,story_dir=None):
 from presentation import build
 if result.get('presentation',{}).get('mode')!='analysis':build(result)
 if result['presentation'].get('status')!='ready':return None
 manifest=result['presentation'];start=0;end=result['video']['duration']
 width,height,band,original=output_dimensions(source);fps=result['presentationMotion']['fps']
 from story_playback import plan,audio_filter
 timeline=plan(manifest,end,fps);manifest['playback']=timeline
 holds={b['sourceFrame']:b for b in timeline['beats']}
 manifest.update(width=width,height=height+band,pictureWidth=width,pictureHeight=height,sourceWidth=original[0],sourceHeight=original[1],renderStyle='editorial-forest-hd-v14',encoding={'codec':'h264','crf':17,'preset':'fast'})
 target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
 story_dir=Path(story_dir) if story_dir else target.parent;story_dir.mkdir(parents=True,exist_ok=True)
 decode=subprocess.Popen([ffmpeg(),'-v','error','-i',str(source),'-t',str(end),'-vf',f'fps={fps},scale={width}:{height}:flags=lanczos','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 # Detect the optional audio stream without requiring ffprobe in Lambda.
 has_audio=subprocess.run([ffmpeg(),'-v','error','-i',str(source),'-map','0:a:0','-t','0.01','-f','null','-'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
 cmd=[ffmpeg(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height+band}','-r',str(fps),'-i','pipe:0','-i',str(source)]
 if has_audio:cmd+=['-filter_complex',audio_filter(timeline),'-map','0:v','-map','[storyaudio]','-c:a','aac']
 else:cmd+=['-map','0:v','-an']
 cmd+=['-t',str(timeline['duration']),'-c:v','libx264','-pix_fmt','yuv420p','-preset','fast','-crf','17','-movflags','+faststart',str(output)]
 encode=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
 index=0;written=0;saved=set()

 try:
  while True:
   raw=decode.stdout.read(width*height*3)
   if len(raw)!=width*height*3:break
   t=index/fps;im=composite(Image.frombytes('RGB',(width,height),raw),result,t)
   for j,f in enumerate(manifest['evidence']):
    if j not in saved and index>=round(f['time']*fps):
     paint_commentary(im.copy(),result,t,{'title':f.get('label',''),'text':f.get('text','')}).save(story_dir/f['image'],quality=95,subsampling=0);saved.add(j)
   beat=holds.get(index)
   if beat:
    for hold_index in range(beat['holdFrames']):
     progress=min(1,hold_index/fps/beat['typingDuration'])
     frozen=paint_commentary(im.copy(),result,t,beat,progress)
     encode.stdin.write(frozen.tobytes());written+=1
   encode.stdin.write(im.tobytes());written+=1;index+=1
  encode.stdin.close();errors=encode.stderr.read();code=encode.wait(timeout=60);decode.wait(timeout=10)
  if code:raise RuntimeError(errors.decode()[-500:])
  if index<max(1,int(end*fps*.95)) or len(saved)!=len(manifest['evidence']):raise RuntimeError('Incomplete replay or evidence frames')
 finally:
  for process in [decode,encode]:
   if process.poll() is None:process.kill();process.wait()
   for stream in [process.stdin,process.stdout,process.stderr]:
    if stream and not stream.closed:stream.close()
 return {'start':0,'end':timeline['duration'],'sourceEnd':end,'fps':fps,'frameCount':written,'sourceFrameCount':index,'focusPlayerId':manifest['actor']['id'],'eventId':manifest['eventId'],'renderer':manifest['renderStyle'],'width':width,'height':height+band,'pictureWidth':width,'pictureHeight':height}
