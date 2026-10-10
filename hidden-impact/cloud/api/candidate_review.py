"""Focused visual check feeds possession corrections back into temporal scoring."""
import base64,io,copy,math
from PIL import Image,ImageDraw,ImageFont
from temporal import reports

def release_suspects(vision):
 """A visual contradiction veto, not proof of shot identity or made baskets.
 Two confident ball detections rise from the same player's upper-body region.
 This catches a later release even when the VLM incorrectly calls the player off-ball.
 """
 hits={};suspects={}
 for f in vision.get('frames',[]):
  for p in f['people']:
   if p.get('association',0)<.7:continue
   balls=[b for b in f.get('ballCandidates',[]) if b.get('confidence',0)>=.5 and p['x']-.2*p['w']<=b['x']<=p['x']+1.2*p['w'] and p['y']-.3*p['h']<=b['y']<=p['y']+.25*p['h']]
   if not balls:continue
   b=max(balls,key=lambda b:b['confidence']);previous=hits.get(p['trackId'])
   if previous and previous['scene']==f['scene'] and .08<f['time']-previous['time']<.5 and previous['y']-b['y']>.13*min(p['h'],previous['h']):
    suspects[p['trackId']]={'start':previous['time'],'end':f['time'],'source':'ball-rise-near-upper-body','status':'possible-release'}
   hits[p['trackId']]={'scene':f['scene'],'time':f['time'],'y':b['y'],'h':p['h']}
 return suspects

def prepare(result,original_frames,events):
 candidates=[]
 for e in events:
  frames=[]
  action_times=[e['start'],(e['start']+e['end'])/2,e['end']]
  shot_time=((result.get('deepData') or {}).get('alignment') or {}).get('shotVideoTime')
  later=[f['time'] for f in original_frames if f['time']>e['end']+.05]
  if isinstance(shot_time,(int,float)):
   later=[f['time'] for f in original_frames if shot_time-1.5<=f['time']<=shot_time+2.5]
  if len(later)>8:later=[later[round(i*(len(later)-1)/7)] for i in range(8)]
  for t,phase in [(t,'action') for t in action_times]+[(t,'outcome') for t in later]:
   original=min(original_frames,key=lambda f:abs(f['time']-t));f=min(result['vision']['frames'],key=lambda f:abs(f['time']-original['time']));a=next((p for p in f['people'] if p['trackId']==e['actorTrackId']),None)
   if not a and phase=='action':continue
   im=Image.open(io.BytesIO(base64.b64decode(original['image']))).convert('RGB');draw=ImageDraw.Draw(im)
   if a:
    x,y,w,h=a['x']*im.width,a['y']*im.height,a['w']*im.width,a['h']*im.height
    draw.rectangle((x,y,x+w,y+h),outline='#ffdc44',width=4);draw.text((x,max(0,y-22)),'A',fill='#ffdc44',font=ImageFont.load_default(size=22))
   beneficiary=next((p for p in f['people'] if p['trackId']==e['beneficiaryTrackId']),None)
   if beneficiary:
    x,y,w,h=beneficiary['x']*im.width,beneficiary['y']*im.height,beneficiary['w']*im.width,beneficiary['h']*im.height;draw.rectangle((x,y,x+w,y+h),outline='#45e4ff',width=4);draw.text((x,max(0,y-22)),'B',fill='#45e4ff',font=ImageFont.load_default(size=22))
   defender=next((p for p in f['people'] if p['trackId']==e['defenderTrackId']),None)
   if defender:
    x,y,w,h=defender['x']*im.width,defender['y']*im.height,defender['w']*im.width,defender['h']*im.height
    draw.rectangle((x,y,x+w,y+h),outline='#ff927f',width=4);draw.text((x,max(0,y-22)),'D',fill='#ff927f',font=ImageFont.load_default(size=22))
   buf=io.BytesIO();im.save(buf,format='JPEG',quality=87)
   frames.append({'time':original['time'],'phase':phase,'image':base64.b64encode(buf.getvalue()).decode()})
  if len({f['time'] for f in frames if f['phase']=='action'})>=3:candidates.append({'id':e['id'],'actionType':e['actionType'],'shotVideoTime':shot_time,'frames':frames})
 return {'mode':'verify-temporal-candidates','candidates':candidates}

def apply(result,checks):
 result=copy.deepcopy(result);events={e['id']:e for e in result['events']};reviewed=result.setdefault('candidateChecks',[]);changed=False
 for check in checks:
  e=events.get(check.get('id'))
  if not e:continue
  receipt={**check,'actorTrackId':e['actorTrackId'],'beneficiaryTrackId':e['beneficiaryTrackId'],'defenderTrackId':e['defenderTrackId'],'start':e['start'],'end':e['end']};reviewed.append(receipt)
  if e['actionType']!='draw-kick' and check.get('onBall') is True and (check.get('samePlayer') is True or check.get('samePlayer') is None and e['measurement']['quality']>=.65):
   changed=True
   for f in result['vision']['frames']:
    if not e['start']<=f['time']<=e['end']:continue
    if not any(p['trackId']==e['actorTrackId'] for p in f['people']):continue
    f['handler']=e['actorTrackId'];f['possessionSource']='focused-candidate-vlm-check'
    for p in f['people']:p['ball']='on' if p['trackId']==e['actorTrackId'] else 'off'
 if changed:
  result['players'],result['events']=reports(result['vision']['roster'],result['vision'],(result.get('deepData') or {}).get('companion'))
 # Passing a check of one time window cannot certify another action by the same track.
 passed=[]
 result['releaseSuspects']=release_suspects(result.get('vision',{}))
 shooters=set(result['releaseSuspects'])| {c['actorTrackId'] for c in reviewed if c.get('isShooter') is True}
 for e in result['events']:
  ok=any(c.get('onBall') is False and c.get('isShooter') is False and (c.get('samePlayer') is True or c.get('samePlayer') is None and e['measurement']['quality']>=.65) and c['actorTrackId']==e['actorTrackId'] and c['beneficiaryTrackId']==e['beneficiaryTrackId'] and c.get('defenderTrackId')==e['defenderTrackId'] and c['start']<=e['start']+.02 and c['end']>=e['end']-.02 for c in reviewed)
  if e['actionType']=='draw-kick':
   ok=any(c.get('onBall') is True and c.get('isShooter') is False and c.get('samePlayer') is True and c.get('passObserved') is True and c.get('beneficiaryIsShooter') is True and c.get('defenderResponds') is True and c['actorTrackId']==e['actorTrackId'] and c['beneficiaryTrackId']==e['beneficiaryTrackId'] and c.get('defenderTrackId')==e['defenderTrackId'] and c['start']<=e['start']+.02 and c['end']>=e['end']-.02 for c in reviewed)
  if e['actionType']=='spacing':ok=ok and any(c.get('beneficiaryOnBall') is True and c['actorTrackId']==e['actorTrackId'] and c['beneficiaryTrackId']==e['beneficiaryTrackId'] and c.get('defenderTrackId')==e['defenderTrackId'] and c['start']<=e['start']+.02 and c['end']>=e['end']-.02 for c in reviewed)
  matching=[c for c in reviewed if c['actorTrackId']==e['actorTrackId'] and c['beneficiaryTrackId']==e['beneficiaryTrackId'] and c.get('defenderTrackId')==e['defenderTrackId'] and c['start']<=e['start']+.02 and c['end']>=e['end']-.02]
  # An explicit visual contradiction overrides a geometric correlation.
  if any(c.get('defenderResponds') is False or c.get('beneficiaryIsShooter') is False for c in matching):ok=False
  shot_time=((result.get('deepData') or {}).get('alignment') or {}).get('shotVideoTime')
  if isinstance(shot_time,(int,float)):
   ok=ok and any(c.get('defenderResponds') is True and c.get('beneficiaryIsShooter') is True and isinstance(c.get('observedShotTime'),(int,float)) and not isinstance(c['observedShotTime'],bool) and math.isfinite(c['observedShotTime']) and abs(c['observedShotTime']-shot_time)<=1.5 for c in matching)
  # An explicit pass-to-shot check disambiguates the generic ball-rise veto;
  # an explicit shooter verdict still excludes the actor in every branch.
  veto={c['actorTrackId'] for c in reviewed if c.get('isShooter') is True} if e['actionType']=='draw-kick' else shooters
  ok=ok and e['actorTrackId'] not in veto
  e['visualVerified']=ok
  e['identityVerification']='visual-confirmed' if any(c.get('samePlayer') is True and c['actorTrackId']==e['actorTrackId'] for c in reviewed) else 'continuous-track-and-jersey'
  if ok:passed.append(e['id'])
 return result

def finalize(result):
 shooters={c['actorTrackId'] for c in result.get('candidateChecks',[]) if c.get('isShooter') is True}
 valid=[e for e in result['events'] if e.get('visualVerified') and e['actorTrackId'] not in shooters and (e['actionType']=='draw-kick' or e['actorTrackId'] not in result.get('releaseSuspects',{}))];ids={e['id'] for e in valid}
 for p in result['players']:
  d=p.get('diagnostics',{})
  if p.get('score')==0 and (d.get('knownHandlerFrames',0)<3 or d.get('knownHandlerFrames',0)/max(1,p.get('observationCount',0))<.25):p.update(score=None,status='insufficient',reason='持球覆盖不足，未将缺失证据记为零贡献。')
  if p['status']=='candidate' and not any(eid in ids for eid in p['eventIds']):
   p.update(status='insufficient',score=None,reason='几何线索尚未通过候选持球与身份核验，不进入幕后 MVP 排名。',eventIds=[],components=[]);p.pop('measurement',None)
 result['events']=valid;result['scoringVersion']='temporal-impact-v5';result['verificationVersion']='focused-outcome-v2'
 shooters={c['actorTrackId'] for c in result.get('candidateChecks',[]) if c.get('isShooter') is True}
 for p in result['players']:
  if p['id'] in shooters:p.update(status='shooter',score=None,reason='核验为本回合最终出手者，不参与幕后 MVP 排名。')
  elif p['id'] in result.get('releaseSuspects',{}) and not any(e['actorTrackId']==p['id'] and e['actionType']=='draw-kick' for e in valid):p.update(status='release-review',score=None,reason='画面检测到后续举球释放动作，与纯无球归因冲突；出手身份待核验，不进入幕后 MVP 排名。')
 for p in result['players']:
  accepted=[e for e in valid if e['actorTrackId']==p['id']]
  if accepted:
   best=max(accepted,key=lambda e:e['score'])
   p.update(score=best['score'],status='candidate',eventIds=[e['id'] for e in accepted],components=best['components'],measurement=best['measurement'],summary=best['summary'],evidence=best['observations'])
 result['players'].sort(key=lambda p:(p['role']=='offense',p['score'] is not None,p['score'] or 0),reverse=True)
 return result
