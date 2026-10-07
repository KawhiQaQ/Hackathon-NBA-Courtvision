"""Research-informed, uncalibrated image-space opportunity-creation index.
NOT EPV, official Gravity, causal attribution, or court-space measurement.
"""
import math,statistics

def clamp(x):return max(0.,min(1.,x))
def point(p,aspect):return ((p['x']+p['w']/2)*aspect,p['y']+p['h'])
def distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
def segment_distance(p,a,b):
 d=((b[0]-a[0])**2+(b[1]-a[1])**2)
 t=clamp(((p[0]-a[0])*(b[0]-a[0])+(p[1]-a[1])*(b[1]-a[1]))/d) if d else 0
 return distance(p,(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))

def score_event(event,vision,companion=None):
 result={'version':'spatial-v2','score':None,'rawScore':None,'quality':0,'components':[], 'series':[],
         'unit':'画面中的人物高度倍数','status':'insufficient','reason':'需同镜头中三个不同角色的连续定位证据。','expectedPointsChange':None}
 ids=[event.get(k) for k in ['actorTrackId','beneficiaryTrackId','defenderTrackId']]
 if not all(isinstance(x,str) for x in ids) or len(set(ids))!=3:return result
 window=[f for f in vision.get('frames',[]) if event['start']<=f['time']<=event['end']]
 if len(window)<3 or len({f['scene'] for f in window})!=1:
  result['reason']='同镜头连续画面不足。';result['rejection']='window';return result
 rows=[];aspect=vision.get('aspectRatio',16/9)
 for f in window:
  people={p['trackId']:p for p in f['people']}
  if not all(x in people for x in ids):continue
  a,b,d=[people[x] for x in ids];height=statistics.mean([a['h'],b['h'],d['h']]);pa,pb,pd=[point(p,aspect) for p in [a,b,d]]
  if height<=0:continue
  rows.append({'time':f['time'],'separation':distance(pb,pd)/height,'engagement':distance(pa,pd)/height,'alignment':segment_distance(pa,pd,pb)/height,
               'confidence':min(p['confidence'] for p in [a,b,d]),'association':min(p.get('association',0) for p in [a,b,d]),'height':height})
 coverage=len(rows)/len(window)
 if len(rows)<3 or coverage<.75:
  result.update(reason='三位相关球员同时可见的覆盖不足。',rejection='coverage',coverage=round(coverage,3));return result
 # Large gaps/scale jumps cause abstention; no extrapolation through cuts or occlusion.
 if any(not 0<b['time']-a['time']<=1.3 or not .7<b['height']/a['height']<1.43 for a,b in zip(rows,rows[1:])):
  result.update(reason='轨迹间断或人物尺度突变。',rejection='continuity');return result
 quality=coverage*statistics.mean(x['confidence'] for x in rows)*statistics.mean(x['association'] for x in rows[1:])
 result['quality']=round(quality,3)
 if quality<.3:
  result['reason']='角色轨迹关联较弱，保留观察但不评分。';result['rejection']='quality';return result
 edge=min(.5,(rows[-1]['time']-rows[0]['time'])/3)
 before=statistics.median(r['separation'] for r in rows if r['time']<=rows[0]['time']+edge);after=statistics.median(r['separation'] for r in rows if r['time']>=rows[-1]['time']-edge);gain=after-before
 release=clamp(gain/1.5)
 # Geometry supports a candidate interaction, not a basketball screen foul/contact decision.
 interaction=max(clamp(1-r['engagement']/1.5)*clamp(1-r['alignment']/.65) for r in rows[:-1])
 if event.get('actionType')=='decoy':
  interaction=statistics.mean(clamp(1-r['engagement']/1.5) for r in rows)*release
 elif event.get('actionType')!='screen':interaction=0
 sustained=sum((b['time']-a['time']) for a,b in zip(rows,rows[1:]) if a['separation']>before+.25 and b['separation']>before+.25)
 persistence=clamp(sustained/max(.001,rows[-1]['time']-rows[0]['time']))
 # A nearby actor or long static spacing earns no contribution without a positive advantage change.
 interaction*=release; persistence*=release
 result['components']=[{'key':k,'label':label,'weight':w,'points':round(v*w,1)} for k,label,w,v in [('release','受益者摆脱',40,release),('interaction','掩护／牵制几何',35,interaction),('persistence','优势保持',25,persistence)]]
 raw=sum(c['points'] for c in result['components']);result.update(rawScore=round(raw,1),score=round(raw*quality),status='candidate',reason='连续定位支持的候选指数；战术角色仍由VLM推断，需回放核验。',
  separationBefore=round(before,3),separationAfter=round(after,3),separationGain=round(gain,3),sustainedSeconds=round(sustained,2),coverage=round(coverage,3),
  series=[{k:round(r[k],3) for k in ['time','separation','engagement']} for r in rows])
 # Optional externally supplied time series stays separate from attribution score.
 samples=(companion or {}).get('opportunity',[])
 if len(samples)>=2:
  start=min(samples,key=lambda s:abs(s['time']-rows[0]['time']));end=min(samples,key=lambda s:abs(s['time']-rows[-1]['time']))
  if start['time']<end['time'] and abs(start['time']-rows[0]['time'])<=1 and abs(end['time']-rows[-1]['time'])<=1:
   result['expectedPointsChange']=round(end['expectedPoints']-start['expectedPoints'],3)
 return result
