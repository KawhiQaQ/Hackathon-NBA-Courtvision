"""Build the same viewer contract for any verified analysis, without demo assets."""
import bisect
import copy
import math
from statistics import median, mean

ROLES=[('actorTrackId','主角','#f4c45e'),('beneficiaryTrackId','收益队友','#77cfe4'),('defenderTrackId','防守者','#ee927f')]
FIELDS=[('OVERALL_GRAV','总体引力'),('ON_BALL_PERIM_GRAV','持球 · 外线'),('ON_BALL_INTERIOR_GRAV','持球 · 内线'),('OFF_BALL_PERIM_GRAV','无球 · 外线'),('OFF_BALL_INTERIOR_GRAV','无球 · 内线')]

def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)


def insights(result):
    deep=result.get('deepData') or {}; official=deep.get('official') or {}
    out={'schema':'hidden-impact/evidence-insights-v1','shot':None,'gravity':None,
         'cues':[], 'narration':copy.deepcopy(result.get('narration') or {'segments':[]})}
    # Ignore data from a different clip, even if structurally valid.
    if deep.get('videoId') != result['video']['id']: return out
    out['probabilitySource']='配套数据预期命中率' if deep.get('opportunitySource') else '官方预期命中率'
    for key in ['gameId','eventId','shooter','sourceUrl']:out[key]=official.get('url' if key=='sourceUrl' else key)
    shot=official.get('shot') or {}; p=shot.get('value'); points={'3分投篮':3,'2分投篮':2}.get(shot.get('shotType'))
    out.update(period=shot.get('period'),gameClock=shot.get('gameClock'))
    alignment=deep.get('alignment') or {}
    if finite(alignment.get('shotVideoTime')) and 0<=alignment['shotVideoTime']<=result['video']['duration']:
        out['shotVideoTime']=alignment['shotVideoTime']
    if finite(p) and 0<=p<=1 and points:
        peer=deep.get('playerShots') or official.get('playerShots') or {}
        samples=[]
        if str(peer.get('playerId'))==str(official.get('playerId')) and peer.get('gameId')==official.get('gameId'):
            samples=[s for s in peer.get('shotList',[]) if s.get('shotType')==shot.get('shotType') and finite(s.get('value')) and 0<=s['value']<=1]
        baseline=mean(s['value'] for s in samples) if samples else None
        out['shot']={'probability':p,'points':points,'made':shot['success']==1 if shot.get('success') in [0,1] else None,
            'expectedPoints':p*points,'baseline':baseline,'sampleCount':len(samples),
            'deltaPercentagePoints':(p-baseline)*100 if baseline is not None else None}
    roster=official.get('rosterGravity') or []
    player=next((p for p in roster if str(p.get('id'))==str(official.get('playerId'))),None)
    if player:
        axes=[]
        for key,label in FIELDS:
            values=[p['gravity'][key] for p in roster if finite(p.get('gravity',{}).get(key))]
            teammates=[p['gravity'][key] for p in roster if p.get('team')==player.get('team') and finite(p.get('gravity',{}).get(key))]
            value=player.get('gravity',{}).get(key)
            axes.append(dict(key=key,label=label,value=value if finite(value) else None,teamMedian=median(teammates) if teammates else None,
                percentile=100*sum(v<=value for v in values)/len(values) if finite(value) and values else None,sampleCount=len(values)))
        out['gravity']=dict(playerId=str(player['id']),player=player.get('name',official.get('shooter','')),scope=official.get('gravityScope','阶段汇总'),games=player.get('games'),
            axes=axes,comparison=(player.get('team') or '队内')+'样本中位数',note='阶段汇总引力用于解释球员特点；不代表这一回合的实时牵制。')
    return out


def motion(result,event,fps=24,width=1280,height=720):
    """Bracket only short gaps in the same shot; missing tracks keep a HUD identity.
    The arrow previews measured later movement, not a model's prediction. Long
    gaps and camera cuts invalidate its heading rather than inventing a route.
    """
    source=sorted(result['vision']['frames'],key=lambda f:f['time'])
    ids=[event[k] for k,_,_ in ROLES]; observations={pid:[] for pid in ids}
    for f in source:
        for p in f['people']:
            if p['trackId'] in observations:observations[p['trackId']].append((f['time'],f.get('scene'),p))
    timeline=[f['time'] for f in source]
    times={pid:[r[0] for r in rows] for pid,rows in observations.items()}
    def scene(t):
        if not timeline:return None
        return source[max(0,bisect.bisect_right(timeline,t)-1)].get('scene')
    def locate(pid,t):
        rows=observations[pid]; j=bisect.bisect_left(times[pid],t)
        if j<len(rows) and abs(rows[j][0]-t)<.0001:return {**rows[j][2],'positionSource':'observed','scene':rows[j][1]}
        if 0<j<len(rows):
            a,b=rows[j-1],rows[j]
            if a[1]==b[1]==scene(t) and b[0]-a[0]<=.55:
                k=(t-a[0])/(b[0]-a[0]);p={**a[2],**{n:a[2][n]+k*(b[2][n]-a[2][n]) for n in ['x','y','w','h']}}
                return {**p,'positionSource':'bracketed-interpolation','scene':a[1]}
        return {'trackId':pid,'offscreen':True,'positionSource':'unlocalized','x':.03+ids.index(pid)*.31,'y':.90,'w':.1,'h':.05,'scene':scene(t)}
    def camera(t):
        j=min(len(source)-1,bisect.bisect_left(timeline,t));a=source[max(0,j-1)];b=source[j]
        if 'cameraOffset' not in a or 'cameraOffset' not in b or a.get('scene')!=b.get('scene'):return (0,0)
        k=max(0,min(1,(t-a['time'])/max(.001,b['time']-a['time'])))
        return [a['cameraOffset'][i]+k*(b['cameraOffset'][i]-a['cameraOffset'][i]) for i in range(2)]
    # Each identity owns its own heading state; a defender can never inherit the
    # protagonist's direction. Preview only measured positions in the same shot.
    output=[];states={idx:dict(heading=None,last=-99,scene=None,length=width*.06,bend=0) for idx in (0,2)}
    for i in range(math.ceil(result['video']['duration']*fps)):
        t=i/fps;people=[locate(pid,t) for pid in ids];arrows={}
        for idx,key in [(0,'heroArrow'),(2,'defenderArrow')]:
            p=people[idx];state=states[idx];arrow=None
            if p['scene']!=state['scene'] or p.get('offscreen'):
                state.update(heading=None,last=-99,bend=0)
            state['scene']=p['scene']
            if not p.get('offscreen'):
                def vector_at(dt):
                    ft=min(t+dt,result['video']['duration']);q=locate(ids[idx],ft)
                    if q.get('offscreen') or q['scene']!=p['scene']:return None
                    pan=camera(ft);now=camera(t)
                    # Feet displacements avoid vertical false motion from a changing box height.
                    return ((q['x']+q['w']/2-p['x']-p['w']/2-(pan[0]-now[0]))*width,
                            (q['y']+q['h']-p['y']-p['h']-(pan[1]-now[1]))*height)
                vector=vector_at(.8);half=vector_at(.4)
                if vector and math.hypot(*vector)>8:
                    angle=math.atan2(vector[1],vector[0]);heading=state['heading']
                    if heading is not None:
                        # Frame-rate independent damping; cap sudden reversals.
                        angle=heading+max(-5/fps,min(5/fps,((angle-heading+math.pi)%(2*math.pi)-math.pi)*min(1,10/fps)))
                    length=max(width*.045,min(width*.095,math.hypot(*vector)))
                    state.update(heading=angle,last=t,length=state['length']*.8+length*.2)
                    bend=0 if half is None else (-math.sin(angle)*half[0]+math.cos(angle)*half[1])
                    state['bend']=state['bend']*.8+max(-width*.015,min(width*.015,bend))*.2
                if state['heading'] is not None and t-state['last']<=1.2:
                    angle=state['heading'];u=(math.cos(angle),math.sin(angle));n=(-u[1],u[0])
                    # Start just outside the body; the cue no longer crosses the jersey.
                    center=((p['x']+p['w']/2)*width,(p['y']+p['h']*.64)*height)
                    gap=max(width*.009,min(width*.025,p['w']*width*.52))
                    a=[center[k]+u[k]*gap for k in (0,1)]
                    b=[a[k]+u[k]*state['length'] for k in (0,1)]
                    c=[(a[k]+b[k])/2+n[k]*state['bend'] for k in (0,1)]
                    points=[[(1-v)**2*a[k]+2*(1-v)*v*c[k]+v*v*b[k] for k in (0,1)] for v in [j/16 for j in range(17)]]
                    arrow={'trackId':ids[idx],'points':points,'mode':'observed-future' if t==state['last'] else 'short-heading-hold'}
            arrows[key]=arrow
        output.append({'time':round(t,5),'people':people,**arrows})
    return {'schema':'hidden-impact/presentation-motion-v2','fps':fps,'width':width,'height':height,'frames':output}



def build(result,fps=24):
    valid=[e for e in result.get('events',[]) if e.get('visualVerified') and finite(e.get('score')) and e['score']>0 and len({e.get(k) for k,_,_ in ROLES})==3 and all(e.get(k) for k,_,_ in ROLES)]
    if not valid or not result.get('vision',{}).get('frames'):
        factual=build_factual(result,fps)
        if factual:return factual
        result['presentation']={'status':'insufficient','reason':'尚无通过核验的三人配合事件。'}
        result.pop('presentationMotion',None)
        return result['presentation']
    e=max(valid,key=lambda e:e['score']); players={p['id']:p for p in result['players']}
    roles=[]
    for key,label,color in ROLES:
        pid=e[key];name=result.get('confirmedNames',{}).get(pid) or players.get(pid,{}).get('label',pid)
        roles.append({'id':pid,'label':label,'displayName':name+' · '+label,'name':name,'color':color})
    info=insights(result); segments=info['narration'].get('segments',[])
    evidence=[]
    for seg in segments:
        refs=[t for t in seg.get('frameTimes',[]) if finite(t) and seg['start']-.5<=t<=seg['end']+.5 and 0<=t<result['video']['duration']]
        if not refs:continue
        t=min(refs,key=lambda t:abs(t-(seg['start']+seg['end'])/2))
        evidence.append({'time':t,'label':seg['title'],'text':seg['text'],'chapter':seg['title'],'kind':'analysis',
            'fact':{'label':'画面证据','value':f'{t:.2f}s'},'source':'timed-narration'})
        info['cues'].append({**seg,'seek':t,'phase':seg['title'],'evidence':f'画面 · {t:.2f}s'})
    if not evidence:
        # Geometry can supply facts when narration fails, but never fake a VLM response.
        for row in e.get('observations',[]):
            if not 0<=row['time']<result['video']['duration']:continue
            evidence.append({'time':row['time'],'label':'配合观察','chapter':'空间变化','text':row['text'],'kind':'analysis',
                'fact':{'label':'位置测量','value':f"{row['time']:.2f}s"},'source':'measured-observation'})
    if not evidence:
        result['presentation']={'status':'insufficient','reason':'缺少可定位的关键帧证据。'}
        return result['presentation']
    # Keep a long response legible; include both beginning and outcome.
    if len(evidence)>8:evidence=[evidence[round(i*(len(evidence)-1)/7)] for i in range(8)]
    evidence=sorted({round(f['time'],3):f for f in evidence}.values(),key=lambda f:f['time'])
    for i,f in enumerate(evidence):f['image']=f'frame-{i+1}.jpg'
    official=(result.get('deepData') or {}).get('official') or {}
    manifest={'schema':'hidden-impact/showcase-v1','mode':'analysis','status':'ready','eventId':e['id'],
        'video':'replay.mp4','original':'original.mp4','actor':{'id':roles[0]['id'],'label':roles[0]['name']},
        'score':e['score'],'components':e.get('components',[]),'roles':roles,'evidence':evidence,'insights':info,
        'matchup':official.get('matchup',result['video'].get('title','回合分析')),'actionTitle':e['title'],
        'summary':e.get('commentary') or e.get('summary',''),'storyTitle':'从配合起点，看到进攻机会。',
        'generation':{'analysisModel':result.get('model'),'modelInvoked':result.get('modelInvoked',False),
                      'narration':{k:info['narration'].get(k) for k in ['status','source','model','modelInvoked']}}}
    from game_summary import round_score
    manifest['impact']=round_score(e['score'],info.get('shot'))
    manifest.update(gameId=official.get('gameId'),team=official.get('team'),videoId=result['video']['id'],
                    roundKey=str(official.get('gameId',''))+':'+str(official['eventId']) if official.get('eventId') is not None else result['video']['id'])
    mapping=next((p for p in ((result.get('deepData') or {}).get('companion') or {}).get('players',[]) if p.get('trackId')==e['actorTrackId']),{})
    if mapping.get('jersey') is not None:
        manifest['identity']={'jersey':str(mapping['jersey']),'confirmed':True,'source':'supplied-companion'}
    result['presentation']=manifest
    result['presentationMotion']=motion(result,e,fps=fps)
    result['focusPlayerId']=e['actorTrackId']
    return manifest


def build_factual(result,fps=24):
    """Keep a data broadcast usable when evidence cannot establish a hidden MVP.

    No substitute winner, score, person positions or causal arrows are fabricated.
    This branch requires a matched real shot and actual time-grounded narration.
    """
    info=insights(result)
    if not info.get('shot') or not result.get('vision',{}).get('frames'):return None
    evidence=[]
    for seg in info['narration'].get('segments',[]):
        times=[t for t in seg.get('frameTimes',[]) if finite(t) and 0<=t<result['video']['duration'] and seg['start']-.5<=t<=seg['end']+.5]
        if not times:continue
        t=min(times,key=lambda t:abs(t-(seg['start']+seg['end'])/2))
        evidence.append(dict(time=t,label=seg['title'],text=seg['text'],chapter=seg['title'],kind='analysis',source='timed-narration',image=f'frame-{len(evidence)+1}.jpg'))
        info['cues'].append({**seg,'seek':t,'phase':seg['title'],'evidence':f'画面 · {t:.2f}s'})
    if not evidence:return None
    official=result['deepData']['official']
    p=dict(schema='hidden-impact/showcase-v1',mode='analysis',status='ready',analysisStatus='unconfirmed-mvp',
        eventId=str(official.get('eventId','')),video='replay.mp4',original='original.mp4',videoId=result['video']['id'],
        gameId=official.get('gameId'),team=official.get('team'),actor=dict(id=None,label='本回合数据解读'),score=None,components=[],roles=[],
        evidence=evidence,insights=info,matchup=official.get('matchup','回合分析'),actionTitle='从进攻过程，看出手机会',
        summary='本回合尚无足够证据确定幕后 MVP。',storyTitle='跟随关键画面，理解出手选择。',
        generation=dict(analysisModel=result.get('model'),modelInvoked=result.get('modelInvoked',False),narration={k:info['narration'].get(k) for k in ['status','source','model','modelInvoked']}))
    result['presentation']=p
    result['presentationMotion']=dict(schema='hidden-impact/presentation-motion-v2',fps=fps,width=1280,height=720,
        frames=[dict(time=i/fps,people=[],heroArrow=None,defenderArrow=None) for i in range(math.ceil(result['video']['duration']*fps))])
    return p
