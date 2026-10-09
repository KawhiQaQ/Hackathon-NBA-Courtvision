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
        out['gravity']=dict(player=player.get('name',official.get('shooter','')),scope=official.get('gravityScope','阶段汇总'),games=player.get('games'),
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
    output=[];heading=None;last_direction=-99;last_scene=None
    for i in range(math.ceil(result['video']['duration']*fps)):
        t=i/fps; people=[locate(pid,t) for pid in ids];actor=people[0]; arrow=None
        if actor['scene']!=last_scene:heading=None
        last_scene=actor['scene']
        future=locate(ids[0],min(t+.65,result['video']['duration']))
        if not actor.get('offscreen'):
            vector=None
            if not future.get('offscreen') and future['scene']==actor['scene']:
                vector=((future['x']+future['w']/2-actor['x']-actor['w']/2)*width,(future['y']+future['h']*.5-actor['y']-actor['h']*.5)*height)
            if vector and math.hypot(*vector)>8:
                angle=math.atan2(vector[1],vector[0])
                if heading is not None:angle=heading+max(-.22,min(.22,((angle-heading+math.pi)%(2*math.pi)-math.pi)*.45))
                heading=angle;last_direction=t
            if heading is not None and t-last_direction<=1.2:
                x=(actor['x']+actor['w']/2)*width;y=(actor['y']+actor['h'])*height
                arrow={'points':[[x,y],[x+math.cos(heading)*width*.075,y+math.sin(heading)*width*.075]],'mode':'observed-future' if t==last_direction else 'short-heading-hold'}
        else:heading=None
        output.append({'time':round(t,5),'people':people,'heroArrow':arrow})
    return {'schema':'hidden-impact/presentation-motion-v1','fps':fps,'width':width,'height':height,'frames':output}


def build(result,fps=24):
    valid=[e for e in result.get('events',[]) if e.get('visualVerified') and finite(e.get('score')) and e['score']>0 and len({e.get(k) for k,_,_ in ROLES})==3 and all(e.get(k) for k,_,_ in ROLES)]
    if not valid or not result.get('vision',{}).get('frames'):
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
