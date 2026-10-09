"""Broadcast-style compositor for the offline presentation, in source-video time.
Graphics illustrate saved observations, not new inference or measured influence areas.
"""
import math,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from render_video import people_at,projection

W,H,TOP,BOTTOM=1280,720,64,116
TOTAL=TOP+H+BOTTOM
GOLD=(246,202,108);BLUE=(111,219,235);CORAL=(248,145,127)
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
def arrow(d,a,b,color):
 if math.dist(a,b)<8:return
 angle=math.atan2(b[1]-a[1],b[0]-a[0]);d.polygon([b,(b[0]-12*math.cos(angle-.42),b[1]-12*math.sin(angle-.42)),(b[0]-12*math.cos(angle+.42),b[1]-12*math.sin(angle+.42))],fill=color)

class BroadcastRenderer:
 def __init__(self,result):
  self.frames=result['vision']['frames'];self.event=result['events'][0];e=self.event
  self.roles=[(e['actorTrackId'],'主角','OFF-BALL',GOLD),(e['beneficiaryTrackId'],'收益队友','TEAMMATE',BLUE),(e['defenderTrackId'],'防守者','DEFENDER',CORAL)]
 def render(self,raw,t):
  e=self.event;im=Image.frombytes('RGB',(W,H),raw).convert('RGBA');people={p['trackId']:p for p in people_at(self.frames,t)}
  current=min(self.frames,key=lambda f:abs(f['time']-t));matrix=(current.get('calibration') or {}).get('courtToImage')
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
  ink=Image.new('RGBA',(W,H));d=ImageDraw.Draw(ink);glow=Image.new('RGBA',(W,H));gd=ImageDraw.Draw(glow)
  # Only the protagonist gets a running trail. Reproject past court points to today's camera.
  actor=people.get(e['actorTrackId'])
  if actor and matrix:
   prev=None
   for f in self.frames:
    if f['scene']!=current['scene'] or not max(5.5,t-1.65)<=f['time']<=t:continue
    p=next((p for p in f['people'] if p['trackId']==e['actorTrackId']),None)
    pt=projection(matrix,p['court']) if p and p.get('court') else None
    if pt:
     xy=(pt[0]*W,pt[1]*H);alpha=int(210*(1-(t-f['time'])/1.8))
     if prev and f['time']-prev[1]<.4 and math.dist(prev[0],xy)<150:
      d.line([prev[0],xy],fill=(*GOLD,alpha),width=4);gd.line([prev[0],xy],fill=(*GOLD,alpha//2),width=11)
     prev=(xy,f['time'])
    else:prev=None
   if prev and math.dist(prev[0],foot(actor))<150:arrow(d,prev[0],foot(actor),(*GOLD,210))
  # A dotted relationship and bracket describe separation, not a predicted pass or force.
  defender=people.get(e['defenderTrackId']);mate=people.get(e['beneficiaryTrackId'])
  if defender and mate and e['start']<=t<=e['end']:
   a,b=foot(defender),foot(mate);dashed(d,a,b,(*BLUE,140));dx,dy=b[0]-a[0],b[1]-a[1];length=max(1,math.hypot(dx,dy));nx,ny=-dy/length*7,dx/length*7
   for x,y in [a,b]:d.line((x-nx,y-ny,x+nx,y+ny),fill=(*BLUE,220),width=2)
   m=min(e['measurement']['series'],key=lambda row:abs(row['time']-t));text=f"投影间距 {m['separation']:.1f}";tw=d.textlength(text,font=FONTS[14]);mx=(a[0]+b[0])/2;my=(a[1]+b[1])/2+17
   d.rounded_rectangle((mx-tw/2-12,my-3,mx+tw/2+12,my+23),7,fill=(5,24,30,220));d.text((mx-tw/2,my+2),text,font=FONTS[14],fill=(*BLUE,255))
  for pid,label,english,color in self.roles:
   p=people.get(pid)
   if not p:continue
   x,y=foot(p);rx=max(17,p['w']*W*.46);ry=max(5,rx*.26);pulse=1.15+.1*math.sin(t*3)
   if not occluded(p,people):
    gd.ellipse((x-rx-5,y-ry-4,x+rx+5,y+ry+4),outline=(*color,125),width=7)
    d.ellipse((x-rx,y-ry,x+rx,y+ry),fill=(*color,25),outline=(*color,235),width=2)
    d.arc((x-rx*pulse-7,y-ry*pulse-4,x+rx*pulse+7,y+ry*pulse+4),int(t*65)%360,int(t*65)%360+235,fill=(*color,150),width=2)
   else:
    # An estimated foot behind a foreground player must not look like their highlight.
    hx=(p['x']+p['w']/2)*W;hy=p['y']*H-4
    gd.ellipse((hx-8,hy-8,hx+8,hy+8),fill=(*color,140))
   # Compact detached nameplates keep text out of player silhouettes.
   px=(p['x']+p['w']/2)*W;py=p['y']*H;title=f'{label}  {pid}';tw=d.textlength(title,font=FONTS[16]);lx=max(12,min(W-tw-36,px-tw/2-14));ly=max(12,py-45)
   d.line((px,ly+30,px,py-5),fill=(*color,180),width=1);d.ellipse((px-2,py-7,px+2,py-3),fill=(*color,255))
   d.rounded_rectangle((lx,ly,lx+tw+28,ly+30),7,fill=(8,25,32,230),outline=(*color,105),width=1)
   d.rounded_rectangle((lx,ly+5,lx+3,ly+25),2,fill=(*color,255));d.text((lx+13,ly+7),title,font=FONTS[16],fill=(*color,255))
  im=Image.alpha_composite(im,glow.filter(ImageFilter.GaussianBlur(5)));im=Image.alpha_composite(im,ink)
  output=Image.new('RGB',(W,TOTAL),'#081a21');output.paste(im.convert('RGB'),(0,TOP));hud=ImageDraw.Draw(output,'RGBA')
  # Persistent broadcast header; every exported frame retains the demo provenance.
  hud.rectangle((0,0,5,TOP),fill=GOLD);hud.text((26,19),'HIDDEN IMPACT',font=FONTS[24],fill='#f1f4ed');hud.text((246,25),'幕后主角 · 战术回放',font=FONTS[16],fill='#9aaeb3')
  hud.rounded_rectangle((W-315,16,W-26,47),9,fill='#16303a',outline='#31474f');hud.text((W-299,24),'TEAM 14  /  演示预设 · 未经核验',font=FONTS[14],fill='#b9cbd0')
  by=TOP+H;hud.line((0,by,W,by),fill='#34494f',width=1)
  phase=0 if t<9 else 1 if t<10 else 2
  captions=['沿无球跑位，寻找机会的起点','观察防守响应与队友的空间','回看机会变化，核验幕后贡献']
  hud.text((28,by+20),captions[phase],font=FONTS[20],fill='#e6eeeb');hud.text((28,by+54),'历史轨迹演示 · 投影距离为参考单位，非因果测量',font=FONTS[12],fill='#819ba4')
  labels=['无球移动','防守响应','空间变化'];starts=[e['start'],9,10]
  for i,label in enumerate(labels):
   xx=660+i*180;active=i==phase;color=GOLD if active else (95,120,130)
   hud.ellipse((xx,by+20,xx+24,by+44),fill=(*color,35),outline=(*color,200),width=1);hud.text((xx+7,by+24),str(i+1),font=FONTS[14],fill=(*color,255));hud.text((xx+36,by+24),label,font=FONTS[16],fill=(*color,255))
   hud.text((xx+36,by+52),f'{starts[i]:.2f}s',font=FONTS[12],fill='#79909a')
   if i<2:hud.line((xx+133,by+32,xx+163,by+32),fill='#3b5159',width=1)
  hud.rectangle((28,by+93,W-28,by+95),fill='#253d45');hud.rectangle((28,by+93,28+(W-56)*min(1,t/13.49),by+95),fill=GOLD)
  return output
