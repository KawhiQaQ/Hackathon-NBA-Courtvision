"""Versioned opportunity-weighted observation scores and deduplicated game totals.
These are descriptive indices; shot quality differences are not causal player EPV.
"""
import math,re
from statistics import mean

VERSION='hidden-impact/game-impact-v1'
def finite(x):return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)
def clamp(x,lo=0,hi=1):return max(lo,min(hi,x))


def round_score(action,shot):
    if not finite(action) or not 0<action<=100:return {'version':VERSION,'score':None,'components':[],'coverage':0}
    shot=shot or {};prob=shot.get('probability');baseline=shot.get('baseline')
    rows=[{'key':'action','label':'配合与防守响应','weight':65,'value':action/100,'detail':'连续画面中的动作证据'}]
    if finite(prob) and 0<=prob<=1:
        rows.append({'key':'opportunity','label':'本次机会质量','weight':20,'value':prob,'detail':f'预期命中率 {prob*100:.1f}%'})
        if finite(baseline) and 0<=baseline<=1:
            relative=clamp(.5+(prob-baseline)/.4)
            rows.append({'key':'relative','label':'相对同场表现','weight':15,'value':relative,'detail':f'相对同球员同类出手 {(prob-baseline)*100:+.1f} 个百分点'})
    available=sum(r['weight'] for r in rows)
    for r in rows:r['points']=round(100*r['weight']/available*r['value'],2)
    score=round(sum(r['points'] for r in rows),1)
    return {'version':VERSION,'score':score,'actionScore':action,'components':rows,'coverage':available/100,
        'label':'回合贡献指数','interpretation':'动作证据结合机会质量的观察指数，非个人因果贡献。',
        'formula':'动作65% + 机会20% + 相对表现15%；相对项以同场均值为中点，±20个百分点为两端；缺项按可用权重归一化。'}


def identity(team,jersey):
    if not isinstance(team,str) or not team.strip() or len(team)>40:raise ValueError('需要球队标识。')
    if not isinstance(jersey,str) or not re.fullmatch(r'[0-9]{1,2}',jersey):raise ValueError('球衣号码必须是0–99或00；不要填跟踪P编号。')
    return {'team':team.strip(),'jersey':jersey,'key':team.strip()+':'+jersey,'label':team.strip()+' '+jersey+'号'}


def aggregate(rounds,game_id,team):
    if not isinstance(game_id,str) or not game_id.strip():raise ValueError('需要同场比赛标识。')
    identity(team,'0')
    if not isinstance(rounds,list) or not 1<=len(rounds)<=30:raise ValueError('一次汇总1–30段视频。')
    seen=set();used=[];excluded=[];players={}
    for r in rounds:
        if not isinstance(r,dict):raise ValueError('回合必须是对象。')
        if r.get('gameId')!=game_id:raise ValueError('不能合并不同场比赛。')
        if r.get('team')!=team:raise ValueError('不能合并不同球队的进攻。')
        key=str(r.get('roundKey') or r.get('videoId') or '')
        if not key:raise ValueError('回合缺少唯一标识。')
        if key in seen:excluded.append({'roundKey':key,'reason':'duplicate'});continue
        seen.add(key);used.append(r)
        who=r.get('identity') or {};impact=r.get('impact') or {}
        if not isinstance(who,dict) or not isinstance(impact,dict):raise ValueError('身份和贡献分格式无效。')
        score=impact.get('score')
        if not who.get('confirmed') or not finite(score) or not 0<score<=100:
            excluded.append({'roundKey':key,'reason':'identity-or-score-unconfirmed'});continue
        # Never merge detection-local IDs such as P1 across separate videos.
        person=identity(team,who.get('jersey'));entry=players.setdefault(person['key'],{**person,'scores':[],'rounds':[],'coverage':[]})
        entry['scores'].append(score);entry['rounds'].append(key);entry['coverage'].append(impact.get('coverage',0))
    credited=sum(len(p['scores']) for p in players.values());total=sum(sum(p['scores']) for p in players.values())
    ranking=[]
    for p in players.values():
        count=len(p['scores']);summed=sum(p['scores']);average=mean(p['scores'])
        parts={'total':60*summed/total if total else 0,'average':25*average/100,'wins':15*count/max(1,credited)}
        ranking.append({**p,'wins':count,'total':round(summed,1),'average':round(average,1),'gameScore':round(sum(parts.values()),2),
            'components':{k:round(v,2) for k,v in parts.items()},'dataCoverage':round(mean(p['coverage']),2)})
    ranking.sort(key=lambda p:(-p['gameScore'],-p['total'],-p['average'],p['key']))
    for i,p in enumerate(ranking):p['rank']=i+1
    leaders=[p for p in ranking if p['gameScore']==ranking[0]['gameScore']] if ranking else []
    return {'schema':'hidden-impact/game-showcase-v1','version':VERSION,'gameId':game_id,'team':team,'rounds':used,'ranking':ranking,
        'winner':ranking[0] if len(leaders)==1 else None,'leaders':leaders,'roundCount':len(used),'creditedRounds':credited,'excluded':excluded,
        'scope':'已上传的同场进攻回合','formula':'总贡献占比60% + 平均回合分25% + 回合MVP次数占比15%',
        'tie':len(leaders)>1}


def measured_action(series):
    """Fallback descriptive geometry score in body-height units for reviewed inputs.
    No shot outcome or jersey-specific constants influence the action score.
    Production temporal events normally supply their own calibrated action score.
    """
    rows=[s for s in series if all(finite(s.get(k)) for k in ['time','engagement','separation'])]
    if len(rows)<3:return None
    n=max(1,len(rows)//4);before=mean(r['separation'] for r in rows[:n]);after=mean(r['separation'] for r in rows[-n:])
    close=min(r['engagement'] for r in rows);span=rows[-1]['time']-rows[0]['time']
    parts={'interaction':30*clamp(1-close/3),'release':35*clamp((after-before)/2),
           'support':20*clamp(after/4),'continuity':15*clamp(span/3)}
    return round(sum(parts.values()),1)
