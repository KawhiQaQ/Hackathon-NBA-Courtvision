"""Source-bound, formatted statistics for the commentator, with explicit scope."""
import math
from statistics import mean


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


def facts_for(payload):
    deep=payload.get('deepData') or {};video=payload.get('video') or {}
    if deep.get('videoId')!=video.get('id'):return []
    actor=(payload.get('narrationContext') or {}).get('actorEvidence') or {}
    facts=[]
    def add(id,scope,text,**values):
        facts.append(dict(id=id,scope=scope,text=text,values=values))
    creation=actor.get('creation');scoring=actor.get('scoring')
    if finite(creation):
        text=f'幕后MVP的创造机会影响力为{creation:+.2f}'
        if finite(scoring):text+=f'，其投篮得分影响力为{scoring:+.2f}'
        add('actor-creation',actor.get('scope','赛季阶段汇总'),text+'。两项为不同贡献维度，非本回合前后增益。',creation=creation,scoring=scoring)
    f=actor.get('finishing') or {};n=f.get('sampleCount');made=f.get('made')
    if isinstance(n,int) and not isinstance(n,bool) and n>0 and finite(made) and 0<=made<=n:
        actual=made/n;expected=f.get('expected');kind='三分' if f.get('shotType')=='3分投篮' else '两分'
        text=f'幕后MVP本回合前本场{kind}{n}投{made:g}中，实际命中率{actual*100:.1f}%'
        delta=None
        if finite(expected) and 0<=expected<=1:
            delta=(actual-expected)*100
            text+=f'，同批出手的官方预期为{expected*100:.1f}%，实际比预期'+('高' if delta>=0 else '低')+f'{abs(delta):.1f}个百分点'
        add('actor-prior-finishing','本场、本回合之前的同一批出手',text+'。这是此前终结表现，不是本回合贡献值。',made=made,attempts=n,actual=actual,expected=expected,deltaPercentagePoints=delta)
    window=payload.get('narrationWindow');time=(deep.get('alignment') or {}).get('shotVideoTime')
    if window and (not finite(time) or window['end']<time):return facts
    official=deep.get('official') or {};shot=official.get('shot') or {};p=shot.get('value')
    if not finite(p) or not 0<=p<=1:return facts
    peer=deep.get('playerShots') or official.get('playerShots') or {};samples=[]
    if official.get('playerId') is not None and peer.get('gameId')==official.get('gameId') and str(peer.get('playerId'))==str(official['playerId']):
        samples=[s['value'] for s in peer.get('shotList',[]) if s.get('shotType')==shot.get('shotType') and finite(s.get('value')) and 0<=s['value']<=1
                 and ('playerId' not in s or str(s['playerId'])==str(official['playerId']))
                 and ('gameId' not in s or s['gameId']==official.get('gameId'))]
    baseline=mean(samples) if samples else None
    text=f'本次出手预期命中率{p*100:.1f}%'
    if baseline is not None:
        delta=(p-baseline)*100
        text+=f'，出手者同场同类出手的预期均值为{baseline*100:.1f}%，本次'+('高' if delta>=0 else '低')+f'{abs(delta):.1f}个百分点'
    add('shot-opportunity','本次出手与出手者同场同类出手对照',text+'。对照描述机会质量，不是幕后MVP独自提升的因果效应。',probability=p,baseline=baseline,sampleCount=len(samples),playerId=official.get('playerId'))
    return facts
