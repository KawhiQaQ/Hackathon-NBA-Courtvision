"""Static, editorial evidence frames. Each annotation explains one visible action."""
import math
from PIL import Image,ImageDraw
from showcase_motion import W,H,font,GOLD,BLUE,CORAL,LILAC,draw_future_arrow
from render_video import people_at

STORY=[
 {'time':7.5,'label':'44号，进入接应位置','chapter':'接应','text':'44号在弧顶外侧准备接球，左侧的阿努诺比开始向外线移动。','kind':'setup'},
 {'time':8.25,'label':'44号推进，防守靠近','chapter':'牵动防守','text':'44号接球后向左前方推进，标出的防守者向持球区域靠近。左侧的阿努诺比留在外线，准备接球。','kind':'pressure'},
 {'time':8.75,'label':'把球送出夹击区域','chapter':'分球','text':'防守靠近时，44号将球分向左侧的阿努诺比。球转移到防线外侧，收益队友获得接球出手的窗口。','kind':'pass'},
 {'time':9.5,'label':'接球起跳，完成出手','chapter':'出手','text':'阿努诺比接球后起跳投篮，44号已经完成分球。球转移到持球区域之外，衔接成一次左侧外线出手。','kind':'shot'},
 {'time':11.1,'label':'三分命中，完成这次配合','chapter':'终结','text':'球穿过篮网，这次进攻以阿努诺比的三分命中结束。回看整段，44号的价值在接应、吸引防守和及时分球。','kind':'made'},
]

def story_frame(raw,result,entry):
 im=Image.frombytes('RGB',(W,H),raw).convert('RGBA');ink=Image.new('RGBA',(W,H));d=ImageDraw.Draw(ink)
 motion=result['presentationMotion'];frame=motion['frames'][min(len(motion['frames'])-1,round(entry['time']*motion['fps']))]
 people={p['trackId']:p for p in frame['people']};e=result['events'][0]
 hero=people[e['actorTrackId']];mate=people[e['beneficiaryTrackId']];defender=people[e['defenderTrackId']]
 def point(p):return ((p['x']+p['w']/2)*W,(p['y']+p['h']*.4)*H)
 # Three identities in every panel. Only the protagonist receives a direction arrow.
 draw_future_arrow(d,frame['heroArrow']['points'],GOLD,7)
 occupied=[]
 for p,text,color in [(hero,'44号 · 主角',GOLD),(mate,'收益队友',BLUE),(defender,'防守者',CORAL)]:
  x=(p['x']+p['w']/2)*W;y=p['y']*H;f=font(25)
  if p.get('offscreen'):text+=' · 出画'
  tw=d.textlength(text,font=f);left=max(12,min(W-tw-30,x-tw/2-14));top=max(15,y-50)
  while any(left<r+6 and left+tw+28>l-6 and top<b+6 and top+38>a-6 for l,a,r,b in occupied) and top>55:top-=44
  occupied.append((left,top,left+tw+28,top+38))
  d.line((x,top+38,x,y),fill=(*color,230),width=2);d.rounded_rectangle((left,top,left+tw+28,top+38),8,fill=(8,25,32,240),outline=(*color,220),width=2);d.text((left+14,top+7),text,font=f,fill=(*color,255))
 if entry['kind']=='made':
  d.ellipse((453,151,532,224),outline=(*BLUE,245),width=4)
  d.rounded_rectangle((542,156,711,200),9,fill=(8,25,32,240),outline=(*BLUE,200),width=2);d.text((558,165),'三分命中 +3',font=font(25),fill=(*BLUE,255))
 return Image.alpha_composite(im,ink).convert('RGB')
