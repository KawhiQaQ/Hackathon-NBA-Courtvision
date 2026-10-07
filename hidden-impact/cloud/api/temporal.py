"""Temporal, multi-mechanism off-ball evidence, with provenance and synchronized render data.
Engineering index, not trained EPV, counterfactual attribution or player ability.
"""
import math,statistics,collections,copy
VERSION='temporal-impact-v5'
def clamp(x,a=0,b=1):return max(a,min(b,x))
def med(a):return statistics.median(a) if a else 0
def dist(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
def pos(p,aspect,court):return p['court'] if court else [(p['x']+p['w']/2)*aspect,p['y']+p['h']]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def minus(a,b):return [a[0]-b[0],a[1]-b[1]]

def ground(vision,context,companion=None):
 v=copy.deepcopy(vision);v.pop('identitySheets',None);verified={p['id']:p for p in context.get('identities',[]) if isinstance(p,dict) and isinstance(p.get('id'),str) and (p.get('samples') or p.get('kind')=='player' and p.get('team') in ['light','dark'])};anchors=context.get('frames',[]);identity={};mapping={p['trackId']:p for p in (companion or {}).get('players',[])}
 end=context.get('attackEnd')
 if not isinstance(end,(int,float)) or isinstance(end,bool) or not 0<end<=v['frames'][-1]['time']+.1:end=v['frames'][-1]['time']
 attack=context.get('offenseTeam') if context.get('offenseTeam') in ['light','dark'] else None
 for f in v['frames']:
  a=min(anchors,key=lambda a:abs(a.get('time',-999)-f['time'])) if anchors else {}
  if abs(a.get('time',-999)-f['time'])>.5:a={}
  people=[]
  for p in f['people']:
   pid=p['trackId']
   if pid not in verified:continue
   team='light' if pid in a.get('light',[]) else 'dark' if pid in a.get('dark',[]) else None
   record=verified[pid];samples=record.get('samples',[])
   if samples:
    nearest=min(samples,key=lambda q:abs(q.get('time',-999)-f['time']));team=nearest.get('team') if nearest.get('kind')=='player' else None
    other=[q for q in samples if q.get('team')!=team and q.get('kind')=='player']
    if other and abs(nearest.get('time',-999)-f['time'])>.5:team=None
   else:team=record.get('team')
   if team not in ['light','dark']:continue
   p['team']=team;p['ball']='unknown';people.append(p);identity.setdefault(pid,[]).append(team)
  f['people']=people;f['active']=f['time']<=end;f['handler']=None
  # Anchor video interpretation supplements ball detector, without fabricating trajectories.
  detected=f.get('ball');near=detected.get('near',[]) if detected else [];candidate=near[0][1] if near and near[0][0]<.13 and (len(near)==1 or near[1][0]-near[0][0]>.12) else None
  handler=candidate if candidate in [p['trackId'] for p in people if p['team']==attack] else a.get('handler')
  if handler and handler in [p['trackId'] for p in people] and f['active']:
   f['handler']=handler;f['possessionSource']='vlm-visual-anchor'
  elif f.get('ball') and f['active']:
   near=f['ball']['near'];valid=[p['trackId'] for p in people]
   if near and near[0][0]<.1 and near[0][1] in valid and (len(near)==1 or near[1][0]-near[0][0]>.16):f['handler']=near[0][1];f['possessionSource']='ball-detector'
  external=(companion or {}).get('frames',[])
  if external:
   q=min(external,key=lambda x:abs(x['time']-f['time']))
   if abs(q['time']-f['time'])<=.12:
    ext={p['playerId']:p for p in q.get('players',[])}
    for p in people:
     link=mapping.get(p['trackId'],{});d=ext.get(link.get('sourcePlayerId'))
     if d:
      # External court locations can drive scores but never replace detected image boxes.
      p['court']=[d['x']*28,d['y']*15];p['positionSource']='supplied-tracking';p['positionConfidence']=d.get('confidence',1)
    holder=q.get('ballHandlerId');h=next((pid for pid,m in mapping.items() if m['sourcePlayerId']==holder),None)
    if h in [p['trackId'] for p in people]:f['handler']=h;f['possessionSource']='supplied-tracking'
  if f['handler']:
   for p in people:p['ball']='on' if p['trackId']==f['handler'] else 'off'
  for p in people:
   possible=any(any(pid==p['trackId'] and distance<.1 for distance,pid in b.get('near',[])) for b in f.get('ballCandidates',[]))
   if possible and p['ball']=='off':p['ball']='unknown'
   p['possibleBall']=possible
 # Never silently merge tracks whose jersey assignment contradicts across anchors.
 roster=[]
 for pid,teams in identity.items():
  team=max(set(teams),key=teams.count);consistent=teams.count(team)/len(teams)
  for f in v['frames']:f['people']=[p for p in f['people'] if p['trackId']!=pid or p['team']==team]
  rows=[(f,p) for f in v['frames'] for p in f['people'] if p['trackId']==pid and p['team']==team]
  if len([f for f,p in rows if f['active']])<4:continue
  label=('浅色球衣 ' if team=='light' else '深色球衣 ')+pid
  if mapping.get(pid,{}).get('label'):label=mapping[pid]['label']
  roster.append({'id':pid,'label':label,'team':team,'role':'offense' if team==attack else 'defense' if attack else 'unknown','summary':'','observations':[{'time':f['time'],'trackId':pid,'scene':f['scene'],'ball':p['ball'],'text':'连续视频观察'} for f,p in rows if f.get('anchor')]})
 valid={p['id'] for p in roster}
 for f in v['frames']:f['people']=[p for p in f['people'] if p['trackId'] in valid]
 v['roster']=roster;v['attackEnd']=end;v['semanticContext']=context
 return roster,v

def reports(roster,vision,companion=None):
 frames=vision['frames'];aspect=vision['aspectRatio'];byid={p['id']:p for p in roster};events=[];reports=[]
 for player in roster:
  pid=player['id'];seen=[f for f in frames if any(p['trackId']==pid for p in f['people'])];active=[f for f in seen if f.get('active',True)];events_for=[];tested=0;usable=0
  p={**player,'score':None,'components':[],'status':'insufficient','reason':'连续可见的攻防关系不足。','evidence':[],'eventIds':[],'scoringVersion':VERSION,'series':[],'visibleSeconds':round(sum(b['time']-a['time'] for a,b in zip(seen,seen[1:]) if a['scene']==b['scene'] and b['time']-a['time']<.4),2),'observationCount':len(seen)}
  if player['role']=='defense':p.update(status='defense',reason='防守观察，不混入无球贡献榜。')
  for f in seen:
   persons={q['trackId']:q for q in f['people']};a=persons[pid];opp=[q for q in f['people'] if byid[q['trackId']]['team']!=player['team']];court='court' in a and all('court' in q for q in opp);unit=1 if court else max(a['h'],.03)
   separation=min((dist(pos(a,aspect,court),pos(q,aspect,court))/unit for q in opp),default=None);p['series'].append({'time':f['time'],'separation':separation})
  if player['role']=='offense':
   # Enumerate 1.5–3 second sequences; every candidate has the same before/after protocol.
   starts=[f['time'] for f in active if f['time']% .5<.18]
   for start in starts:
    win=[f for f in active if start<=f['time']<=start+2.5]
    if len(win)<7 or win[-1]['time']-win[0]['time']<1.2 or len({f['scene'] for f in win})!=1:continue
    allpeople=[{q['trackId']:q for q in f['people']} for f in win];aa=[ps[pid] for ps in allpeople]
    if any(a['ball']=='on' and f.get('possessionSource') in ['focused-candidate-vlm-check','supplied-tracking'] for f,a in zip(win,aa)):continue
    teammates=[q['id'] for q in roster if q['team']==player['team'] and q['id']!=pid];opponents=[q['id'] for q in roster if q['team']!=player['team']]
    for bid in teammates:
     for did in opponents:
      tested+=1;rows=[(f,ps[pid],ps[bid],ps[did]) for f,ps in zip(win,allpeople) if bid in ps and did in ps]
      if len(rows)<len(win)*.75 or any(b[0]['time']-a[0]['time']>.4 for a,b in zip(rows,rows[1:])):continue
      court=all('court' in x for row in rows for x in row[1:]);unit=1 if court else med([q['h'] for row in rows for q in row[1:]])
      series=[]
      for f,a,b,d in rows:
       ap,bp,dp=[pos(q,aspect,court) for q in (a,b,d)];sep=dist(bp,dp)/unit;eng=dist(ap,dp)/unit;spread=dist(ap,bp)/unit
       enemies=[q for q in f['people'] if byid[q['trackId']]['team']!=player['team'] and (not court or 'court' in q)]
       openness=min((dist(bp,pos(q,aspect,court))/unit for q in enemies),default=sep)
       line=minus(bp,dp);rel=minus(ap,dp);alpha=dot(rel,line)/max(.001,dot(line,line));cross=dist(ap,[dp[k]+clamp(alpha)*line[k] for k in range(2)])/unit
       series.append({'time':f['time'],'pathBlock':0.05<alpha<1.05 and cross<(0.9 if court else .4),'openness':openness,'separation':sep,'engagement':eng,'spread':spread,'a':ap,'b':bp,'d':dp,'handler':f.get('handler'),'quality':min(q['confidence']*q.get('association',.65) for q in [a,b,d])})
      quality=med([r['quality'] for r in series]);span=series[-1]['time']-series[0]['time']
      if quality<.24:continue
      usable+=1;n=max(2,len(series)//4);before=med([r['separation'] for r in series[:n]]);after=med([r['separation'] for r in series[-n:]]);gain=after-before;eng=min(r['engagement'] for r in series);threshold=1.5 if court else .75;release=.45 if court else .28
      open_before=med([r['openness'] for r in series[:n]]);open_after=med([r['openness'] for r in series[-n:]]);open_gain=open_after-open_before
      # Robust endpoint motions; court projection removes pan. Image fallback only uses pair distances.
      vec=lambda key:[med([r[key][k] for r in series[-n:]])-med([r[key][k] for r in series[:n]]) for k in range(2)]
      va,vd=vec('a'),vec('d');movement=math.hypot(*va);dm=math.hypot(*vd);following=dot(va,vd)/max(.01,movement*dm)
      maintained=sum(r['separation']>before+release for r in series)/len(series);kind=None;strength=0
      # A screen candidate must engage the defender BEFORE teammate separation improves.
      touch=next((i for i,r in enumerate(series) if r['engagement']<threshold),None)
      if court and before<3.0 and gain>release and open_gain>.3 and touch is not None and sum(r['pathBlock'] for r in series[:max(2,len(series)//2)])>=2 and touch<len(series)*.65 and series[-1]['engagement']>=eng+.15:
       kind='screen';strength=clamp(1-eng/threshold)*.5+.5*clamp((series[-1]['engagement']-eng)/threshold)
      if court and movement>.8 and dm>.65 and following>.65 and gain>release and open_gain>.3 and med([r['engagement'] for r in series])<3 and med([r['engagement'] for r in series[-n:]])<3:
       kind='decoy';strength=clamp(movement/2)*clamp(following)
      support=[r for r in series if r['engagement']<threshold and r['spread']>(4 if court else 2.5) and r['separation']>(4 if court else 2)]
      if not kind and len(support)>=len(series)*.7:kind='spacing';strength=med([clamp(1-r['engagement']/(threshold*1.5))*clamp(r['separation']/(6 if court else 4)) for r in support])
      if not kind:continue
      components=[{'key':'release','label':'队友空间改善','weight':35,'points':round(35*clamp(gain/(2.5 if court else 1.5)),1) if kind!='spacing' else 0}, {'key':'interaction','label':'防守响应','weight':25,'points':round(25*strength,1) if kind!='spacing' else 0}, {'key':'persistence','label':'优势保持','weight':20,'points':round(20*maintained,1) if kind!='spacing' else 0}, {'key':'spacing','label':'持续空间支撑','weight':20,'points':round(20*strength*clamp(span/2),1) if kind=='spacing' else 0}]
      # Time-aligned attention share is supporting evidence, never inferred from season Gravity.
      aligned=[g for g in (companion or {}).get('gravity',[]) if g.get('trackId')==pid and start<=g['time']<=series[-1]['time']]
      external={'gravitySamples':len(aligned),'source':(companion or {}).get('source'),'opportunityChange':None}
      opp=[o for o in (companion or {}).get('opportunity',[]) if start<=o['time']<=series[-1]['time']]
      if len(opp)>1:external['opportunityChange']=round(opp[-1]['expectedPoints']-opp[0]['expectedPoints'],3)
      if len(aligned)>1:external['attentionShareChange']=round(aligned[-1]['attentionShare']-aligned[0]['attentionShare'],3)
      score=round(sum(c['points'] for c in components))
      if score<4:continue
      # Quality is separate from magnitude; no silent multiplication turning every result into zero.
      eid=f'{kind}-{pid}-{round(start*1000)}';key=min(series[max(1,len(series)//5):max(2,len(series)*4//5)],key=lambda r:r['engagement']);label={'screen':'掩护协同','decoy':'跑位带动防守','spacing':'拉开空间'}[kind];unitlabel='参考球场单位' if court else '人物高度'
      ev=[]
      for row in [series[0],key,series[-1]]:
       f=min(win,key=lambda f:abs(f['time']-row['time']));ps={q['trackId']:q for q in f['people']};marks=[dict(ps[x],role=role,label=byid[x]['label']) for x,role in [(pid,'actor'),(bid,'beneficiary'),(did,'defender')] if x in ps]
       ev.append({'time':row['time'],'text':f"队友与相关防守人间距 {row['separation']:.2f} {unitlabel}",'marks':marks})
      if len({r['time'] for r in ev})<3:ev[1]=dict(ev[1],time=series[len(series)//2]['time'])
      m={'score':score,'rawScore':score,'quality':round(quality,3),'components':components,'series':series,'separationBefore':round(before,3),'separationAfter':round(after,3),'separationGain':round(gain,3),'opennessBefore':round(open_before,3),'opennessAfter':round(open_after,3),'sustainedSeconds':round(span if kind=='spacing' else span*maintained,2),'expectedPointsChange':external['opportunityChange'],'units':unitlabel,'courtCalibrated':court,'externalEvidence':external,'reason':'时序空间代理指数；证据质量单列，非因果归因。'}
      summary=f"{player['label']}在 {start:.2f}–{series[-1]['time']:.2f} 秒出现{label}线索；相关防守人与队友的间距从 {before:.1f} 变为 {after:.1f} {unitlabel}。"
      events_for.append({'id':eid,'title':label+' · '+player['label'],'actor':player['label'],'actorTrackId':pid,'beneficiaryTrackId':bid,'defenderTrackId':did,'beneficiary':byid[bid]['label'],'start':series[0]['time'],'end':series[-1]['time'],'keyTime':key['time'],'score':score,'actionType':kind,'components':components,'measurement':m,'observations':ev,'summary':summary,'caveat':m['reason'],'origin':'temporal-geometry-v5'})
   events_for.sort(key=lambda e:(e['score'],e['measurement']['quality']),reverse=True)
   if events_for:
    best=events_for[0];events.append(best);p.update(score=best['score'],status='candidate',components=best['components'],evidence=best['observations'],eventIds=[best['id']],summary=best['summary'],reason=best['caveat'],measurement=best['measurement'])
   elif usable>=3:p.update(score=0,status='observed',reason='已测量连续无球窗口，未出现足够的空间改善或持续空间支撑。')
  if not p['evidence'] and seen:
   for f in [seen[0],seen[len(seen)//2],seen[-1]]:
    q=next(q for q in f['people'] if q['trackId']==pid);p['evidence'].append({'time':f['time'],'text':'球员位置观察','marks':[dict(q,role='actor',label=player['label'])]})
  p['diagnostics']={'evaluatedWindows':tested,'acceptedInteractionWindows':usable,'offBallFrames':sum(next(q for q in f['people'] if q['trackId']==pid)['ball']=='off' for f in active),'knownHandlerFrames':sum(bool(f.get('handler')) for f in active),'rejections':{}}
  reports.append(p)
 reports.sort(key=lambda p:(p['role']=='offense',p['score'] is not None,p['score'] or 0),reverse=True);events.sort(key=lambda e:e['score'],reverse=True)
 return reports,events
