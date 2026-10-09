"""Pass-to-shot candidates from observed possession transitions and pair geometry.
A candidate is not an attribution: focused VLM review must confirm the pass,
defensive response and recipient's shot before it can enter the ranking.
"""
import math
from statistics import median


def candidates(roster, vision):
    byid = {p['id']: p for p in roster}
    frames = [f for f in vision.get('frames', []) if f.get('active', True)]
    output = []
    for i in range(2, len(frames)-2):
        left, right = frames[i-1], frames[i]
        aid, bid = left.get('handler'), right.get('handler')
        if not aid or not bid or aid == bid or aid not in byid or bid not in byid: continue
        if byid[aid]['role'] != 'offense' or byid[aid]['team'] != byid[bid]['team']: continue
        if left['scene'] != right['scene'] or right['time']-left['time'] > .4: continue
        # Multiple observations either side prevent a one-frame possession flicker.
        before = [f for f in frames[:i] if left['time']-.9 <= f['time'] and f['scene'] == left['scene']]
        after = [f for f in frames[i:] if f['time'] <= right['time']+.9 and f['scene'] == right['scene']]
        if sum(f.get('handler') == aid for f in before) < 3 or sum(f.get('handler') == bid for f in after) < 3: continue
        window = before+after
        if any(b['time']-a['time'] > .4 for a,b in zip(window,window[1:])): continue
        for defender in roster:
            did = defender['id']
            if defender['team'] == byid[aid]['team']: continue
            rows = [(f, {p['trackId']:p for p in f['people']}) for f in window]
            rows = [(f,p) for f,p in rows if all(k in p for k in [aid,bid,did])]
            if len(rows) < .85*len(window) or len(rows) < 7: continue
            court = all('court' in p[k] for _,p in rows for k in [aid,bid,did])
            unit = 1 if court else median(p[k]['h'] for _,p in rows for k in [aid,bid,did])
            aspect = vision.get('aspectRatio',16/9)
            def position(p): return p['court'] if court else [(p['x']+p['w']/2)*aspect,p['y']+p['h']]
            def distance(a,b): return math.dist(a,b)/max(unit,.01)
            series = []
            for f,p in rows:
                a,b,d = [position(p[k]) for k in [aid,bid,did]]
                enemies = [q for q in f['people'] if q['trackId'] in byid and byid[q['trackId']]['team'] != byid[aid]['team'] and (not court or 'court' in q)]
                series.append(dict(time=f['time'],a=a,b=b,d=d,handler=f.get('handler'),pathBlock=False,
                    engagement=distance(a,d),separation=distance(b,d),spread=distance(a,b),
                    openness=min((distance(b,position(q)) for q in enemies),default=0),
                    quality=min(p[k].get('confidence',0)*p[k].get('association',.65) for k in [aid,bid,did])))
            pre = [s for s in series if s['time'] < right['time']]
            post = [s for s in series if s['time'] >= right['time']]
            if len(pre)<3 or len(post)<3: continue
            quality=median(s['quality'] for s in series)
            near=min(s['engagement'] for s in pre)
            approach=pre[0]['engagement']-near
            separation=median(s['separation'] for s in post)
            openness=median(s['openness'] for s in post)
            spread=median(s['spread'] for s in series)
            threshold=2.5 if court else 1.2
            if quality < .35 or near > threshold or approach < (.15 if court else .1) or separation < (2.5 if court else 1.5) or spread < (3 if court else 1.8) or openness < (.7 if court else .4): continue
            clamp=lambda x:max(0,min(1,x))
            components=[{'key':'interaction','label':'持球牵动防守','weight':35,'points':round(35*clamp(approach/threshold),1)},
                {'key':'release','label':'接球空间','weight':30,'points':round(30*clamp(openness/(3 if court else 2)),1)},
                {'key':'transfer','label':'球权衔接','weight':20,'points':round(20*clamp(min(len(pre),len(post))/5),1)},
                {'key':'spacing','label':'出球跨度','weight':15,'points':round(15*clamp(spread/(7 if court else 4)),1)}]
            score=round(sum(c['points'] for c in components)); units='参考球场单位' if court else '人物高度'
            measurements=dict(score=score,rawScore=score,quality=round(quality,3),components=components,series=series,
                separationBefore=pre[0]['separation'],separationAfter=separation,separationGain=separation-pre[0]['separation'],
                opennessBefore=pre[0]['openness'],opennessAfter=openness,sustainedSeconds=post[-1]['time']-post[0]['time'],
                expectedPointsChange=None,units=units,courtCalibrated=court,reason='时序传球与防守响应代理指数；非因果归因。')
            observations=[]
            for row in [series[0],min(series,key=lambda r:abs(r['time']-right['time'])),series[-1]]:
                f,p=min(rows,key=lambda r:abs(r[0]['time']-row['time']))
                observations.append({'time':f['time'],'text':f"接应队友与相关防守者间距 {row['separation']:.1f} {units}",
                    'marks':[dict(p[k],role=role,label=byid[k]['label']) for k,role in [(aid,'actor'),(bid,'beneficiary'),(did,'defender')]]})
            output.append(dict(id=f'draw-kick-{aid}-{bid}-{round(right["time"]*1000)}-{did}',title='牵动后分球 · '+byid[aid]['label'],
                actor=byid[aid]['label'],beneficiary=byid[bid]['label'],actorTrackId=aid,beneficiaryTrackId=bid,defenderTrackId=did,
                start=series[0]['time'],end=series[-1]['time'],keyTime=right['time'],actionType='draw-kick',score=score,
                components=components,measurement=measurements,observations=observations,
                summary=f"{byid[aid]['label']}持球期间防守者靠近，随后球权转至{byid[bid]['label']}；待画面核验传球与最终出手。",
                caveat=measurements['reason'],origin='possession-transition-v1'))
    best={}
    for e in output:
        if e['actorTrackId'] not in best or e['score']>best[e['actorTrackId']]['score']:best[e['actorTrackId']]=e
    return list(best.values())
