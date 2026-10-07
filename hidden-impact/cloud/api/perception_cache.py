"""Content-addressed perception cache; scoring and VLM output are never cached here."""
import hashlib,json,base64,io
from PIL import Image,ImageDraw,ImageFont

def cache_key(video_key,etag,frames):
 material={'version':'basketball-cv-v3','video':video_key,'etag':etag,'anchors':[(f['time'],hashlib.sha256(f['image'].encode()).hexdigest()) for f in frames]}
 return 'perception/'+hashlib.sha256(json.dumps(material,sort_keys=True).encode()).hexdigest()+'.json'

def annotate(vision,originals):
 frames=[]
 for original in originals:
  f=min(vision['frames'],key=lambda f:abs(f['time']-original['time']))
  if abs(f['time']-original['time'])>.03:raise ValueError('Cache anchors do not match')
  raw=Image.open(io.BytesIO(base64.b64decode(original['image']))).convert('RGB');im=raw.copy();draw=ImageDraw.Draw(im);font=ImageFont.load_default(size=18)
  for p in f['people']:
   x,y=p['x']*im.width,p['y']*im.height;draw.rectangle((x,y,x+p['w']*im.width,y+p['h']*im.height),outline='#ffe070',width=2);draw.rectangle((x,y-23,x+50,y),fill='#132c2b');draw.text((x+2,y-22),p['trackId'],fill='white',font=font)
  buf=io.BytesIO();im.save(buf,format='JPEG',quality=78);clock=raw.crop((0,int(raw.height*.76),raw.width,raw.height));cb=io.BytesIO();clock.save(cb,format='JPEG',quality=84)
  frames.append({'time':original['time'],'image':base64.b64encode(buf.getvalue()).decode(),'scoreboard':base64.b64encode(cb.getvalue()).decode()})
 return frames
