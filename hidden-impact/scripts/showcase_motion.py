"""Broadcast-style compositor for the offline presentation, in source-video time.
Graphics illustrate saved observations, not new inference or measured influence areas.
"""
import math,sys
import numpy as np
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from render_video import people_at,projection

W,H,TOP,BOTTOM=1280,720,64,116
TOTAL=TOP+H+BOTTOM
GOLD=(246,202,108);BLUE=(111,219,235);CORAL=(248,145,127);LILAC=(176,164,244)
FONT=Path('/System/Library/Fonts/STHeiti Light.ttc')
def font(size):return ImageFont.truetype(str(FONT),size) if FONT.exists() else ImageFont.load_default(size=size)
FONTS={s:font(s) for s in [12,14,16,18,20,24,28]}
def ease(x):x=max(0,min(1,x));return x*x*(3-2*x)
def occluded(p,people):
 x=p['x']+p['w']/2;y=p['y']+p['h']
 return any(q['trackId']!=p['trackId'] and q['x']<x<q['x']+q['w'] and q['y']<y<q['y']+q['h']-.025 for q in people.values())
def foot(p):return ((p['x']+p['w']/2)*W,(p['y']+p['h'])*H)
def dashed(d,a,b,color,width=2):
 length=math.dist(a,b)
 if length<1:return
 for n in range(0,int(length),14):
  q=min(n+7,length);d.line([(a[0]+(b[0]-a[0])*n/length,a[1]+(b[1]-a[1])*n/length),(a[0]+(b[0]-a[0])*q/length,a[1]+(b[1]-a[1])*q/length)],fill=color,width=width)
def future_path(frames,current,actor,matrix,t,horizon=1.6):
 """A smoothed guide to *observed future* positions; never extrapolate across cuts/gaps."""
 if not actor or not actor.get('court') or not matrix:return None
 samples=[(t,actor['court'])]
 for f in frames:
  if f['time']<=t:continue
  if f['time']>t+horizon:break
  if f['scene']!=current['scene']:break
  p=next((p for p in f['people'] if p['trackId']==actor['trackId']),None)
  if not p or not p.get('court') or p.get('association',0)<.65:continue
  dt=f['time']-samples[-1][0]
  if dt>.4 or math.dist(p['court'],samples[-1][1])>max(1.2,dt*9):break
  samples.append((f['time'],p['court']))
 span=samples[-1][0]-t
 if len(samples)<3 or span<.4:return None
 # Fit only within the observed window, to suppress foot-location and calibration jitter.
 times=np.array([s[0]-t for s in samples]);points=np.array([s[1] for s in samples])
 degree=2 if len(samples)>=5 else 1
 design=np.vander(times,degree+1,increasing=True);fit=np.linalg.lstsq(design,points,rcond=None)[0]
 fitpoints=np.vander(np.linspace(0,span,24),degree+1,increasing=True)@fit
 projected=[projection(matrix,point) for point in fitpoints]
 if any(pt is None for pt in projected):return None
 origin=foot(actor);first=projected[0]
 path=[(origin[0]+(pt[0]-first[0])*W,origin[1]+(pt[1]-first[1])*H) for pt in projected]
 if math.dist(path[0],path[-1])<12:return None
 # Keep a direction cue visible when its destination reaches the edge of the broadcast.
 path=[(max(18,min(W-18,x)),max(18,min(H-18,y))) for x,y in path]
 return path,span

def draw_future_arrow(d,path,color=GOLD,width=7):
 # Each role keeps its color and a clear arrowhead, with a lighter hierarchy for support.
 head=26 if width>=7 else 18;half=12 if width>=7 else 8
 tip=path[-1];back=next((p for p in reversed(path[:-1]) if math.dist(p,tip)>=head),path[0])
 angle=math.atan2(tip[1]-back[1],tip[0]-back[0]);ux,uy=math.cos(angle),math.sin(angle)
 base=(tip[0]-head*ux,tip[1]-head*uy);left=(base[0]-half*uy,base[1]+half*ux);right=(base[0]+half*uy,base[1]-half*ux)
 shaft=[p for p in path if math.dist(p,tip)>head]+[base]
 if len(shaft)>1:
  d.line(shaft,fill=(10,24,29,190),width=width+4,joint='curve');d.line(shaft,fill=(*color,235),width=width,joint='curve')
 d.polygon([tip,left,right],fill=(*color,250))
 d.ellipse((path[0][0]-3,path[0][1]-3,path[0][0]+3,path[0][1]+3),fill=(*color,240))

class BroadcastRenderer:
 def __init__(self,result):
  self.names=result.get('displayNames',{});self.frames=result['vision']['frames'];self.event=result['events'][0];e=self.event
  self.roles=[(e['actorTrackId'],'主角','OFF-BALL',GOLD),*[(pid,'协同队友','SUPPORT',LILAC) for pid in e.get('supportTrackIds',[])],(e['beneficiaryTrackId'],'收益队友','TEAMMATE',BLUE),*[(pid,'内侧防守' if i==0 else '外侧防守','DEFENDER',CORAL) for i,pid in enumerate(e.get('defenderTrackIds',[e['defenderTrackId']]))]]
 def render(self,raw,t):
  e=self.event;im=Image.frombytes('RGB',(W,H),raw).convert('RGBA');people={p['trackId']:p for p in people_at(self.frames,t)}
  current=min(self.frames,key=lambda f:abs(f['time']-t));matrix=(current.get('calibration') or {}).get('courtToImage')
  if matrix is None:
   nearby=[f for f in self.frames if f['scene']==current['scene'] and abs(f['time']-t)<=.2 and f.get('calibration')]
   if nearby:matrix=min(nearby,key=lambda f:abs(f['time']-t))['calibration'].get('courtToImage')
  focus=ease((t-6.4)/.7)*(1-ease((t-10.1)/.6))
  if focus and any(pid in people for pid,*_ in self.roles):
   # Dim surroundings softly. The transparent windows follow each observed player.
   mask=Image.new('L',(W//4,H//4),int(86*focus));md=ImageDraw.Draw(mask)
   for pid,_,_,_ in self.roles:
    p=people.get(pid)
    if p:
     x,y,w,h=[p[k]*scale for k,scale in [('x',W/4),('y',H/4),('w',W/4),('h',H/4)]]
     md.ellipse((x-10,y-6,x+w+10,y+h+8),fill=0)
   mask=mask.filter(ImageFilter.GaussianBlur(10)).resize((W,H));shade=Image.new('RGBA',(W,H),(4,18,24));shade.putalpha(mask);im=Image.alpha_composite(im,shade)
  ink=Image.new('RGBA',(W,H));d=ImageDraw.Draw(ink)
  for pid,label,english,color in self.roles:
   if english=='TEAMMATE':continue
   person=people.get(pid);guide=future_path(self.frames,current,person,matrix,t)
   if guide:
    path,span=guide;lift=person['h']*H*.60
    path=[(x,y-lift) for x,y in path]
    draw_future_arrow(d,path,color,7 if english=='OFF-BALL' else 3)
  # Resolve overlapping labels before drawing; leader lines retain identity in a crowd.
  occupied=[]
  for pid,label,english,color in self.roles:
   p=people.get(pid)
   if not p:continue
   # A quiet baseline identifies visible feet; rotating rings and glow trails are removed.
   x,y=foot(p)
   if not occluded(p,people) and pid!=e['actorTrackId']:
    d.line((x-12,y,x+12,y),fill=(*color,200),width=3)
   # Compact detached nameplates keep text out of player silhouettes.
   px=(p['x']+p['w']/2)*W;py=p['y']*H;title=self.names.get(pid,label);tw=d.textlength(title,font=FONTS[16]);lx=max(12,min(W-tw-36,px-tw/2-14));ly=max(12,py-45)
   while any(lx<right+6 and lx+tw+28>left-6 and ly<bottom+6 and ly+30>top-6 for left,top,right,bottom in occupied) and ly>48:ly-=38
   occupied.append((lx,ly,lx+tw+28,ly+30))
   d.line((px,ly+30,px,py-5),fill=(*color,180),width=1);d.ellipse((px-2,py-7,px+2,py-3),fill=(*color,255))
   d.rounded_rectangle((lx,ly,lx+tw+28,ly+30),7,fill=(8,25,32,230),outline=(*color,105),width=1)
   d.rounded_rectangle((lx,ly+5,lx+3,ly+25),2,fill=(*color,255));d.text((lx+13,ly+7),title,font=FONTS[16],fill=(*color,255))
  im=Image.alpha_composite(im,ink)
  output=Image.new('RGB',(W,TOTAL),'#081a21');output.paste(im.convert('RGB'),(0,TOP));hud=ImageDraw.Draw(output,'RGBA')
  # Persistent broadcast header.
  hud.rectangle((0,0,5,TOP),fill=GOLD);hud.text((26,19),'HIDDEN IMPACT',font=FONTS[24],fill='#f1f4ed');hud.text((246,25),'幕后主角 · 战术回放',font=FONTS[16],fill='#9aaeb3')
  hud.rounded_rectangle((W-315,16,W-26,47),9,fill='#16303a',outline='#31474f');hud.text((W-299,24),'TEAM 14  /  NYK vs SAS',font=FONTS[14],fill='#b9cbd0')
  by=TOP+H;hud.line((0,by,W,by),fill='#34494f',width=1)
  phase=0 if t<e['keyTime'] else 1 if t<e['end'] else 2
  captions=['主角与协同队友分路跑位','跟随两名防守者，看防守移动','左侧收益队友接球出手']
  hud.text((28,by+20),captions[phase],font=FONTS[20],fill='#e6eeeb');hud.text((28,by+54),'金色 · 主角    紫色 · 协同    珊瑚色 · 防守方向',font=FONTS[12],fill='#819ba4')
  labels=['双人牵制','防守移动','接球出手'];starts=[e['start'],e['keyTime'],e['end']]
  for i,label in enumerate(labels):
   xx=660+i*180;active=i==phase;color=GOLD if active else (95,120,130)
   hud.ellipse((xx,by+20,xx+24,by+44),fill=(*color,35),outline=(*color,200),width=1);hud.text((xx+7,by+24),str(i+1),font=FONTS[14],fill=(*color,255));hud.text((xx+36,by+24),label,font=FONTS[16],fill=(*color,255))
   hud.text((xx+36,by+52),f'{starts[i]:.2f}s',font=FONTS[12],fill='#79909a')
   if i<2:hud.line((xx+133,by+32,xx+163,by+32),fill='#3b5159',width=1)
  hud.rectangle((28,by+93,W-28,by+95),fill='#253d45');hud.rectangle((28,by+93,28+(W-56)*min(1,t/13.49),by+95),fill=GOLD)
  return output
