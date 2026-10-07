"""Basketball roster grounding and per-player, image-space contribution reports.
VLM classifies roles/identity; detector owns positions. No causal or metric-court claim.
"""
import collections,math,statistics
from impact_score import score_event,point,distance,clamp

def text(v,n=350):return v[:n] if isinstance(v,str) else ''
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

SCORING_VERSION='evidence-gated-v4'

def ground_roster(raw,vision):
 anchors=[f for f in vision['frames'] if f.get('anchor',True)];roster=[];refs=collections.defaultdict(list);occupied=set()
 for item in raw.get('players',[])[:12]:
  if not isinstance(item,dict):continue
  pid=item.get('id')
  if not isinstance(pid,str) or not pid.startswith('P') or any(p['id']==pid for p in roster):continue
  observations=[]
  for o in item.get('observations',[])[:20]:
   if not isinstance(o,dict) or not finite(o.get('time')):continue
   f=min(anchors,key=lambda f:abs(f['time']-o['time']))
   if abs(f['time']-o['time'])>.04:continue
   p=next((p for p in f['people'] if p['trackId']==o.get('trackId')),None)
   if p is None or (f['time'],p['trackId']) in occupied:continue
   occupied.add((f['time'],p['trackId']));obs={'time':f['time'],'trackId':p['trackId'],'scene':f['scene'],'ball':o.get('ball') if o.get('ball') in ['on','off'] else 'unknown','text':text(o.get('note'))}
   observations.append(obs);refs[(f['scene'],p['trackId'])].append((f['time'],pid,obs['ball']))
  if not observations:continue
  roster.append({'id':pid,'label':text(item.get('label'),80) or pid,'team':item.get('team') if item.get('team') in ['A','B'] else 'unknown',
                 'role':item.get('role') if item.get('role') in ['offense','defense'] else 'unknown','observations':sorted(observations,key=lambda x:x['time']),
                 'summary':text(item.get('summary')),'actions':item.get('actions',[]) if isinstance(item.get('actions',[]),list) else []})
 # Learn two current-game jersey prototypes from crop-verified player references.
 # Do not hard-code franchise colors: away and alternate uniforms differ.
 color_samples=collections.defaultdict(list)
 for player in roster:
  for o in player['observations']:
   f=min(anchors,key=lambda f:abs(f['time']-o['time']));p=next((p for p in f['people'] if p['trackId']==o['trackId']),None)
   if p and len(p.get('jerseyColor',[]))==3:color_samples[player['team']].append(p['jerseyColor'])
 prototypes={team:[statistics.median(c[k] for c in colors) for k in range(3)] for team,colors in color_samples.items() if team in ['A','B'] and len(colors)>=3}
 color_distance=lambda a,b:math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
 color_ready=len(prototypes)==2 and color_distance(prototypes['A'],prototypes['B'])>.35
 player_map={p['id']:p for p in roster}
 for player in roster:
  prototype=prototypes.get(player['team'])
  if prototype:
   luminance=sum(prototype)/3;name='浅色球衣' if luminance>.62 else '深色球衣' if luminance<.36 else player['team']+'组球衣'
   player['label']=name+' '+player['id'];player['jerseyColor']=prototype
 frames=[];retained=0;total=0;color_rejected=0
 for f in vision['frames']:
  candidates=[];total+=len(f['people'])
  for p in f['people']:
   options=refs.get((f['scene'],p['trackId']),[])
   if not options:continue
   nearest=min(options,key=lambda x:abs(x[0]-f['time']))
   # Never extend an identity indefinitely beyond its semantically checked anchor.
   if abs(nearest[0]-f['time'])>.8:continue
   # A track with conflicting identity references is allowed only at the exact anchor.
   if len({x[1] for x in options})>1 and abs(nearest[0]-f['time'])>.04:continue
   if color_ready and p.get('jerseyColor'):
    team=player_map[nearest[1]]['team'];other='B' if team=='A' else 'A'
    if team in prototypes:
     own=color_distance(p['jerseyColor'],prototypes[team]);different=color_distance(p['jerseyColor'],prototypes[other])
     if own>.38 and different+.15<own:color_rejected+=1;continue
   candidates.append((abs(nearest[0]-f['time']),dict(p,detectorTrackId=p['trackId'],trackId=nearest[1],ball=nearest[2],identitySource='vlm-anchor')))
  people=[];seen=set()
  for _,p in sorted(candidates,key=lambda x:x[0]):
   if p['trackId'] in seen:continue
   seen.add(p['trackId']);people.append(p)
  retained+=len(people);frames.append(dict(f,people=people))
 result=dict(vision,frames=frames,roster=roster,teamColors=prototypes,jerseyCalibration={'active':color_ready,'source':'current-video verified-player torso medians'},filter={'rawDetections':total,'playerDetections':retained,'excludedDetections':total-retained,'method':'crop-role whitelist + two-team jersey consistency + detector references','jerseyRejected':color_rejected},
             limitations=['仅显示VLM识别为上场球员且有检测框支持的人物','球衣与跨帧身份仍可能误判，未识别者不强行合并','画面相对距离不是米数，空间指数不证明因果贡献'])
 return roster,result

def player_reports(roster,vision,companion=None):
 frames=vision['frames'];aspect=vision.get('aspectRatio',16/9);byid={p['id']:p for p in roster};reports=[];events=[]
 def frame_people(f):return {p['trackId']:p for p in f['people']}
 for player in roster:
  pid=player['id'];rows=[]
  for f in frames:
   people=frame_people(f);p=people.get(pid)
   if not p:continue
   opponents=[q for q in f['people'] if byid[q['trackId']]['team']!=player['team'] and byid[q['trackId']]['team']!='unknown' and player['team']!='unknown']
   nearest=min(opponents,key=lambda q:distance(point(p,aspect),point(q,aspect))/max(.01,(p['h']+q['h'])/2),default=None)
   rows.append({'time':f['time'],'scene':f['scene'],'person':p,'separation':distance(point(p,aspect),point(nearest,aspect))/max(.01,(p['h']+nearest['h'])/2) if nearest else None,'defenderId':nearest['trackId'] if nearest else None})
  duration=sum(b['time']-a['time'] for a,b in zip(rows,rows[1:]) if a['scene']==b['scene'] and b['time']-a['time']<=.4)
  report={k:player[k] for k in ['id','label','team','role','summary']};report.update(score=None,components=[],evidence=[],status='insufficient',reason='可见时间或身份证据不足。',visibleSeconds=round(duration,2),observationCount=len(rows),eventIds=[],series=[{'time':r['time'],'separation':round(r['separation'],3) if r['separation'] is not None else None} for r in rows])
  # Candidate geometry is evaluated for every visible off-ball offensive player.
  # It is not contingent on the language model producing a rare three-frame event.
  best=None;diagnostics=collections.Counter();valid_windows=0;valid_offball_windows=0
  if player['role']=='offense' and len(rows)>=3:
   teammates=[p['id'] for p in roster if p['team']==player['team'] and p['id']!=pid]
   opponents=[p['id'] for p in roster if p['team']!=player['team'] and p['team']!='unknown']
   for anchor in player['observations']:
    if anchor['ball']!='off':continue
    start=max(0,anchor['time']-.5);end=anchor['time']+1.5
    win=[f for f in frames if start<=f['time']<=end and f['scene']==anchor['scene']]
    if len(win)<4:continue
    for beneficiary in teammates:
     for defender in opponents:
      e=dict(actorTrackId=pid,beneficiaryTrackId=beneficiary,defenderTrackId=defender,start=win[0]['time'],end=win[-1]['time'],actionType='screen')
      measurement=score_event(e,dict(vision,frames=win),companion)
      if measurement['score'] is None:
       diagnostics[measurement.get('rejection','incomplete')]+=1;continue
      valid_windows+=1
      # An already distant or unrelated defender cannot be called a released matchup.
      if measurement.get('separationBefore',99)>1.8:diagnostics['unrelated_matchup']+=1;continue
      series=measurement['series'];engaged=min(x['engagement'] for x in series)<1.5
      interaction=next(c['points'] for c in measurement['components'] if c['key']=='interaction')
      # Mere teammate spacing gain does not credit an unrelated nearby player.
      if not engaged or interaction<1 or measurement.get('separationGain',0)<.25:diagnostics['no_screen_signal']+=1;continue
      visible=[r for r in rows if e['start']<=r['time']<=e['end']]
      if any(r['person'].get('ball')=='on' for r in visible):diagnostics['on_ball']+=1;continue
      if sum(r['person'].get('ball')=='off' for r in visible)<max(3,len(visible)*.75):diagnostics['uncertain_possession']+=1;continue
      valid_offball_windows+=1
      if not best or measurement['score']>best['measurement']['score']:best={**e,'measurement':measurement}
   if duration>=.5 and valid_windows>=2 and sum(o['ball']=='off' for o in player['observations'])>=2:
    report.update(score=0,status='observed',reason='已检查可见的无球时间窗，未测得同时满足贴近防守路径和队友空间改善的贡献信号；0不是实际比赛贡献为零。')
  elif player['role']=='defense':report.update(status='defense',reason='防守方：展示对位距离与移动观察，不混入进攻无形贡献榜。')
  elif player['role']=='unknown':report['reason']='暂未确认攻防角色，保留逐人观察。'
  if player['role']=='offense' and player['observations'] and all(o['ball']=='on' for o in player['observations']):
   report.update(status='ballhandler',reason='可见观察主要为持球阶段，不将其自身推进或出手算作无球贡献。')
  if best:
   m=best['measurement'];bid=best['beneficiaryTrackId'];did=best['defenderTrackId'];start,end=m['series'][0]['time'],m['series'][-1]['time'];best.update(start=start,end=end);mid=min(m['series'],key=lambda r:r['engagement'])['time']
   evidence=[]
   for t,label in [(start,'动作前'),(mid,'防守路径接近'),(end,'空间变化后')]:
    f=min((f for f in frames if f['scene']==next(r['scene'] for r in rows if start<=r['time']<=end)),key=lambda f:abs(f['time']-t))
    people=frame_people(f)
    marks=[{**people[x],'role':role,'label':byid[x]['label']} for x,role in [(pid,'actor'),(bid,'beneficiary'),(did,'defender')] if x in people]
    measured=min(m['series'],key=lambda row:abs(row['time']-f['time']))
    caption=f"{label}：与相关防守人间距 {measured['engagement']:.2f}，队友对位间距 {measured['separation']:.2f}（画面人物高度倍数）。"
    evidence.append({'time':f['time'],'text':caption,'marks':marks})
   eid='player-'+pid;summary=f"{player['label']} 接近相关防守路径时，{byid[bid]['label']} 与 {byid[did]['label']} 的画面间距从 {m['separationBefore']:.2f} 增至 {m['separationAfter']:.2f} 个人物高度。空间优势持续 {m['sustainedSeconds']:.1f} 秒。这是可回看的空间协同候选，尚不能证明因果牵制。"
   event={**best,'id':eid,'title':'空间协同 · '+player['label'],'actor':player['label'],'beneficiary':byid[bid]['label'],'score':m['score'],'components':m['components'],'observations':evidence,'summary':summary,'caveat':m['reason'],'confidence':'medium','origin':'measured-geometry'}
   events.append(event);report.update(score=m['score'],components=m['components'],evidence=evidence,status='candidate',reason=m['reason'],eventIds=[eid],summary=summary,measurement=m)
  else:
   # Every identified person has clickable, detector-grounded observations, even without positive score.
   obs=player['observations'];indices=sorted({0,len(obs)//2,len(obs)-1})
   for i in indices:
    o=obs[i];f=min(frames,key=lambda f:abs(f['time']-o['time']));p=frame_people(f).get(pid)
    if p:report['evidence'].append({'time':o['time'],'text':o['text'] or ('持球观察' if o['ball']=='on' else '无球位置观察' if o['ball']=='off' else '可见位置'),'marks':[dict(p,role='actor',label=player['label'])]})
  # Static spacing can support an offense without a visible screen: a nearby opponent
  # remains separated from the ball handler. This is a descriptive structure, NOT gravity.
  support=[];known_handler_frames=0;offball_frames=0
  if player['role']=='offense':
   for f in frames:
    people=frame_people(f);a=people.get(pid)
    if not a or a.get('ball')!='off':continue
    offball_frames+=1
    handlers=[q for q in f['people'] if byid[q['trackId']]['team']==player['team'] and q.get('ball')=='on' and q['trackId']!=pid]
    if len(handlers)!=1:continue
    known_handler_frames+=1
    b=handlers[0];defenders=[q for q in f['people'] if byid[q['trackId']]['team']!=player['team'] and byid[q['trackId']]['team']!='unknown']
    if not defenders:continue
    d=min(defenders,key=lambda q:distance(point(a,aspect),point(q,aspect)));height=statistics.mean([a['h'],b['h'],d['h']]);ad=distance(point(a,aspect),point(d,aspect))/height;ab=distance(point(a,aspect),point(b,aspect))/height;bd=distance(point(b,aspect),point(d,aspect))/height
    if ad>1.5 or ab<2.5 or bd<2:continue
    quality=min(q['confidence'] for q in [a,b,d])*min(q.get('association',0) for q in [a,b,d])
    support.append({'time':f['time'],'scene':f['scene'],'b':b['trackId'],'d':d['trackId'],'separation':bd,'engagement':ad,'quality':quality,'strength':clamp((ab-2)/2)*clamp(1-ad/2)})
  runs=[];run=[]
  for row in support:
   if run and (row['scene']!=run[-1]['scene'] or row['b']!=run[-1]['b'] or row['d']!=run[-1]['d'] or row['time']-run[-1]['time']>.4):
    runs.append(run);run=[]
   run.append(row)
  if run:runs.append(run)
  runs=[run for run in runs if len(run)>=3 and run[-1]['time']-run[0]['time']>=.5]
  if runs:
   run=max(runs,key=lambda run:statistics.mean(x['quality']*x['strength'] for x in run)*min(1,(run[-1]['time']-run[0]['time'])/1.5));quality=statistics.mean(x['quality'] for x in run);support_points=20*statistics.mean(x['strength'] for x in run)*min(1,(run[-1]['time']-run[0]['time'])/1.5);earned=round(support_points*quality)
   if quality>=.3 and earned>0:
    report['spacingSupport']={'points':earned,'quality':round(quality,3),'seconds':round(run[-1]['time']-run[0]['time'],2),'defenderId':run[0]['d'],'ballHandlerId':run[0]['b']}
    if best:
     # Dynamic geometry carries 80%, observed spacing support carries 20%.
     m=report['measurement'];m['components']=[dict(c,weight=round(c['weight']*.8),points=round(c['points']*.8,1)) for c in m['components']]
     m['components'].append({'key':'spacing','label':'空间支撑','weight':20,'points':round(support_points,1)})
     report['score']=min(100,round(best['measurement']['score']*.8)+earned);m['score']=report['score'];report['components']=m['components']
     for ev in events:
      if ev['actorTrackId']==pid:ev.update(score=report['score'],components=m['components'])
    else:
     bid,did=run[0]['b'],run[0]['d'];seconds=run[-1]['time']-run[0]['time'];evidence=[]
     for row,label in [(run[0],'空间结构形成'),(run[len(run)//2],'防守人保持邻近'),(run[-1],'空间结构保持')]:
      f=min(frames,key=lambda f:abs(f['time']-row['time']));people=frame_people(f)
      marks=[dict(people[x],role=role,label=byid[x]['label']) for x,role in [(pid,'actor'),(bid,'beneficiary'),(did,'defender')] if x in people]
      caption=f"{label}：该防守人距无球队员 {row['engagement']:.2f}、距持球者 {row['separation']:.2f}（画面人物高度倍数）。"
      evidence.append({'time':row['time'],'text':caption,'marks':marks})
     reason='持续位置关系支持的空间支撑指数；未证明防守者被吸引，也不代表因果得分贡献。'
     components=[{'key':'spacing','label':'空间支撑','weight':20,'points':round(support_points,1)}]
     m={'score':earned,'rawScore':round(support_points,1),'quality':round(quality,3),'components':components,'series':[{k:x[k] for k in ['time','separation','engagement']} for x in run], 'separationBefore':run[0]['separation'],'separationAfter':run[-1]['separation'],'sustainedSeconds':round(seconds,2),'expectedPointsChange':None,'reason':reason}
     summary=f"{player['label']} 处于无球状态，其附近的 {byid[did]['label']} 与持球者 {byid[bid]['label']} 保持较远的画面间距，这一结构持续 {seconds:.1f} 秒。计入空间支撑；仅凭画面不能证明防守者因该球员而被牵制。"
     eid='spacing-'+pid;events.append({'id':eid,'title':'空间支撑 · '+player['label'],'actor':player['label'],'actorTrackId':pid,'beneficiaryTrackId':bid,'defenderTrackId':did,'start':run[0]['time'],'end':run[-1]['time'],'score':earned,'components':components,'measurement':m,'observations':evidence,'summary':summary,'caveat':reason,'actionType':'spacing','origin':'measured-geometry'})
     report.update(score=earned,components=components,evidence=evidence,status='candidate',reason=reason,eventIds=[eid],summary=summary,measurement=m)
  # No dynamic-only score can exceed its 80 point budget.
  if best and not report.get('spacingSupport'):
   m=report['measurement'];m['components']=[dict(c,weight=round(c['weight']*.8),points=round(c['points']*.8,1)) for c in m['components']];report['score']=round(report['score']*.8);m['score']=report['score'];report['components']=m['components']
   for ev in events:
    if ev['actorTrackId']==pid:ev.update(score=report['score'],components=m['components'])
  report['scoringVersion']=SCORING_VERSION
  report['diagnostics']={'evaluatedWindows':valid_windows,'acceptedInteractionWindows':valid_offball_windows,'offBallFrames':offball_frames,'knownHandlerFrames':known_handler_frames,'rejections':dict(diagnostics)}
  if player['role']=='offense' and report['status']!='candidate':
   if offball_frames<3 or known_handler_frames<3 or known_handler_frames/max(1,offball_frames)<.25:
    report.update(score=None,status='insufficient',reason='持球者或无球状态的有效覆盖不足，无法比较贡献；不是零贡献。')
    if player['observations'] and all(o['ball']=='on' for o in player['observations']):report.update(status='ballhandler',reason='可见观察为持球阶段，不参与无球贡献比较。')
   elif valid_windows<2:
    report.update(score=None,status='insufficient',reason='相关球员同时可见的连续轨迹不足，无法完成贡献计算。')
  reports.append(report)
 reports.sort(key=lambda p:(p['role']=='offense',p['score'] is not None,p['score'] or 0),reverse=True);events.sort(key=lambda e:e['score'],reverse=True)
 return reports,events
