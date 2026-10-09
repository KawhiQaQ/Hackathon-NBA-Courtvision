"""Static, editorial evidence frames. Each annotation explains one visible action."""
import math
from PIL import Image,ImageDraw
from showcase_motion import W,H,font,GOLD,BLUE,CORAL,LILAC,draw_future_arrow
from render_video import people_at

STORY=[
 {'time':7.5,'label':'44号，进入接应位置','chapter':'接应','text':'44号在弧顶外侧准备接球，右侧协同队友保持宽度；左侧的阿努诺比开始向外线移动。','kind':'setup'},
 {'time':8.25,'label':'向内推进，两人靠近','chapter':'牵动防守','text':'44号接球后向左前方推进。一名防守者迎上来，另一名从侧后方靠近，两人的注意力集中到持球区域。','kind':'pressure'},
 {'time':8.75,'label':'把球送出夹击区域','chapter':'分球','text':'两名防守者靠近时，44号将球分向左侧的阿努诺比。球转移到防线外侧，收益队友获得接球出手的窗口。','kind':'pass'},
 {'time':9.5,'label':'球已出手，追防晚一步','chapter':'出手','text':'阿努诺比接球后起跳投篮，追防者正在向他回扑。44号的分球衔接成一次左侧外线出手。','kind':'shot'},
 {'time':11.1,'label':'三分命中，完成这次配合','chapter':'终结','text':'球穿过篮网，这次进攻以阿努诺比的三分命中结束。回看整段，44号的价值在接应、吸引防守和及时分球。','kind':'made'},
]

def story_frame(raw,result,entry):
 im=Image.frombytes('RGB',(W,H),raw).convert('RGBA');ink=Image.new('RGBA',(W,H));d=ImageDraw.Draw(ink)
 people={p['trackId']:p for p in people_at(result['vision']['frames'],entry['time'])};e=result['events'][0];kind=entry['kind']
 hero=people.get(e['actorTrackId']);mate=people.get(e['beneficiaryTrackId']);support=people.get(e['supportTrackIds'][0]);defs=[people.get(pid) for pid in e['defenderTrackIds']]
 def point(p):return ((p['x']+p['w']/2)*W,(p['y']+p['h']*.48)*H)
 def route(a,b,color,width=6,bend=0):
  mid=((a[0]+b[0])/2,(a[1]+b[1])/2+bend)
  path=[((1-u)**2*a[0]+2*(1-u)*u*mid[0]+u*u*b[0],(1-u)**2*a[1]+2*(1-u)*u*mid[1]+u*u*b[1]) for u in [i/30 for i in range(31)]]
  if math.dist(a,b)>25:draw_future_arrow(d,path,color,width)
 def badge(p,text,color,offset=0):
  if not p:return
  x=(p['x']+p['w']/2)*W;y=p['y']*H;f=font(25);tw=d.textlength(text,font=f);left=max(12,min(W-tw-30,x-tw/2-14));top=max(15,y-50+offset)
  d.line((x,top+38,x,y),fill=(*color,230),width=2);d.rounded_rectangle((left,top,left+tw+28,top+38),8,fill=(8,25,32,240),outline=(*color,220),width=2);d.text((left+14,top+7),text,font=f,fill=(*color,255))
 if kind=='setup':
  if hero:route(point(hero),(point(hero)[0]-100,point(hero)[1]+12),GOLD)
  badge(hero,'44号 · 接应',GOLD);badge(support,'保持宽度',LILAC);badge(mate,'向外线移动',BLUE)
 elif kind=='pressure':
  if hero:
   center=point(hero)
   for p in defs:
    if p:
     a=point(p);b=(center[0]*.8+a[0]*.2,center[1]*.8+a[1]*.2);route(a,b,CORAL,4,bend=-16)
   d.ellipse((center[0]-68,center[1]-48,center[0]+68,center[1]+57),outline=(*GOLD,220),width=3)
  badge(hero,'44号 · 持球推进',GOLD,offset=125);badge(defs[0],'迎上',CORAL,offset=-60);badge(defs[1],'靠近',CORAL,offset=-12);badge(mate,'左侧接球点',BLUE)
 elif kind=='pass':
  if hero and mate:route(point(hero),point(mate),GOLD,7,bend=48)
  badge(hero,'44号 · 分球',GOLD,offset=100);badge(mate,'接球窗口',BLUE)
  for p in defs:
   if p:
    x,y=point(p);d.ellipse((x-9,y-9,x+9,y+9),outline=(*CORAL,240),width=3)
 elif kind=='shot':
  if mate:route((point(mate)[0],mate['y']*H),(350,169),BLUE,6,bend=-135)
  if defs[0] and mate:route(point(defs[0]),(point(mate)[0]+35,point(mate)[1]+20),CORAL,3)
  badge(mate,'接球出手',BLUE,offset=-15);badge(hero,'44号 · 完成分球',GOLD)
 else:
  # The ball is visible immediately below the rim at 11.10 s in this source clip.
  d.ellipse((453,151,532,224),outline=(*BLUE,245),width=4)
  d.rounded_rectangle((542,156,711,200),9,fill=(8,25,32,240),outline=(*BLUE,200),width=2);d.text((558,165),'三分命中 +3',font=font(25),fill=(*BLUE,255))
  badge(mate,'阿努诺比',BLUE)
 return Image.alpha_composite(im,ink).convert('RGB')
