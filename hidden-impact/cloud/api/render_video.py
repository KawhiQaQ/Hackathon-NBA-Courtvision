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

def render(source,result,output):
 events=result.get('events',[])
 if not events:return None
 e=events[0];frames=result['vision']['frames'];start=max(0,e['start']-.5);end=min(result['video']['duration'],e['end']+.5);width=960;height=round(width/result['vision']['aspectRatio']/2)*2;fps=24
 decode=subprocess.Popen([ffmpeg(),'-v','error','-ss',str(start),'-i',str(source),'-t',str(end-start),'-vf',f'fps={fps},scale={width}:{height}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 encode=subprocess.Popen([ffmpeg(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height+120}','-r',str(fps),'-i','pipe:0','-ss',str(start),'-i',str(source),'-map','0:v','-map','1:a?','-t',str(end-start),'-c:v','libx264','-pix_fmt','yuv420p','-preset','veryfast','-crf','21','-c:a','aac','-movflags','+faststart',str(output)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
 colors={e['actorTrackId']:(255,222,125),e['defenderTrackId']:(255,148,125),e['beneficiaryTrackId']:(130,219,255)};font=ImageFont.load_default(size=19);small=ImageFont.load_default(size=13);index=0
 try:
  while True:
   raw=decode.stdout.read(width*height*3)
   if len(raw)!=width*height*3:break
   t=start+index/fps;index+=1;im=Image.new('RGB',(width,height+120),'#142c2a');im.paste(Image.frombytes('RGB',(width,height),raw));draw=ImageDraw.Draw(im,'RGBA');f=min(frames,key=lambda f:abs(f['time']-t));h=(f.get('calibration') or {}).get('courtToImage');persons=people_at(frames,t)
   active=e['start']<=t<=e['end']
   for pid,color in colors.items():
    p=next((p for p in persons if p['trackId']==pid),None)
    if not p or not active:continue
    past=[q for q in frames if q['scene']==f['scene'] and max(e['start'],t-2.3)<=q['time']<=t];prev=None
    for q in past:
     person=next((p for p in q['people'] if p['trackId']==pid),None)
     pt=projection(h,person['court']) if person and h and 'court' in person else ((person['x']+person['w']/2,person['y']+person['h']) if person else None)
     if pt:
      xy=(pt[0]*width,pt[1]*height)
      if prev and q['time']-prev[1]<.4:draw.line([prev[0],xy],fill=(*color,int(40+150*(1-(t-q['time'])/2.3))),width=6 if pid==e['actorTrackId'] else 3)
      prev=(xy,q['time'])
     else:prev=None
    x=(p['x']+p['w']/2)*width;y=(p['y']+p['h'])*height;draw.ellipse((x-20,y-6,x+20,y+6),fill=(*color,55),outline=(*color,240),width=3)
    label=pid+('  FOCUS' if pid==e['actorTrackId'] else '  DEFENDER' if pid==e['defenderTrackId'] else '  TEAMMATE');ly=max(10,p['y']*height-(52 if pid==e['actorTrackId'] else 25));draw.rounded_rectangle((x-40,ly,x+100,ly+22),radius=5,fill=(15,39,37,230));draw.text((x-35,ly+3),label,fill=(*color,255),font=small)
   # Lower strip is outside the footage, leaving the actual play readable.
   draw.text((22,height+12),f"HIDDEN IMPACT  /  {e['actorTrackId']}  /  {e['actionType'].upper()}",fill='white',font=font)
   phase='BEFORE' if t<e['start'] else 'AFTER' if t>e['end'] else 'MOVEMENT' if t<e.get('keyTime',e['start']+1) else 'DEFENSIVE RESPONSE'
   draw.text((22,height+43),f"{t:05.2f}s   {phase}    Index {e['score']}/100",fill='#b5c8b5',font=small)
   series=e['measurement']['series'];maximum=max(1,max(r['separation'] for r in series));points=[(450+(r['time']-e['start'])/(e['end']-e['start'])*300,height+85-r['separation']/maximum*65) for r in series];draw.line(points,fill='#ffe18d',width=3);x=450+max(0,min(1,(t-e['start'])/(e['end']-e['start'])))*300;draw.line((x,height+10,x,height+90),fill='#9cdfef',width=2);draw.text((450,height+97),'Teammate - defender separation',fill='#b5c8b5',font=small)
   draw.rectangle((780,height+8,947,height+97),outline='#759183',width=1);draw.line((863,height+8,863,height+97),fill='#759183')
   for p in persons:
    if p['trackId'] in colors and p.get('court') and f.get('calibration'):
     x=780+p['court'][0]/28*167;y=height+8+p['court'][1]/15*89
     if 780<=x<=947 and height+8<=y<=height+97:draw.ellipse((x-3,y-3,x+3,y+3),fill=colors[p['trackId']])
   draw.text((780,height+101),'Estimated court',fill='#b5c8b5',font=small);encode.stdin.write(im.tobytes())
  encode.stdin.close();errors=encode.stderr.read();code=encode.wait(timeout=60);decode.wait(timeout=10)
  if code:raise RuntimeError(errors.decode()[-500:])
  if index<max(1,int((end-start)*fps*.8)):raise RuntimeError('Insufficient decoded video frames')
 finally:
  if decode.poll() is None:decode.kill()
  if encode.poll() is None:encode.kill()
 return {'start':start,'end':end,'fps':fps,'frameCount':index,'focusPlayerId':e['actorTrackId'],'eventId':e['id']}
