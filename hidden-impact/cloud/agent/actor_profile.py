"""Player-bound background evidence, independent of per-possession contribution."""
from statistics import mean
import math

def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)


def build_profile(result, player_id):
    deep=result.get('deepData') or {};official=deep.get('official') or {}
    if not player_id or deep.get('videoId')!=result['video']['id']:return None
    profile=next((p for p in deep.get('playerProfiles',[]) if str(p.get('playerId'))==str(player_id) and p.get('gameId')==official.get('gameId')),None)
    if not profile:return None
    leverage=profile.get('leverage') or {};shots=profile.get('shots') or {}
    valid_leverage=str(leverage.get('PLAYERID'))==str(player_id)
    out=dict(playerId=str(player_id),name=profile.get('name','幕后MVP'),scope=profile.get('scope','阶段汇总'),sources=profile.get('sources',[]),finishing=None)
    for dest,key in [('creation','CREATION_LVG'),('scoring','SHOT_LVG')]:
        value=leverage.get(key);out[dest]=value if valid_leverage and finite(value) else None
    out['games']=leverage.get('GP') if valid_leverage else None
    # Compare only completed earlier events from this game and this player.
    # Never let later made shots leak into the actor's pre-possession profile.
    event=official.get('eventId')
    if str(shots.get('playerId'))==str(player_id) and shots.get('gameId')==official.get('gameId') and finite(event):
        seen=set();prior=[]
        for s in shots.get('shotList',[]):
            if (str(s.get('playerId'))!=str(player_id) or s.get('gameId')!=official.get('gameId')
                or not finite(s.get('eventId')) or s['eventId']>=event or s['eventId'] in seen
                or isinstance(s.get('success'),bool) or s.get('success') not in [0,1]):continue
            seen.add(s['eventId']);prior.append(s)
        out['shooting']={}
        for key,kind in [('two','2分投篮'),('three','3分投篮')]:
            rows=[s for s in prior if s.get('shotType')==kind]
            if not rows:continue
            expected=[s['value'] for s in rows if finite(s.get('value')) and 0<=s['value']<=1]
            out['shooting'][key]=dict(sampleCount=len(rows),made=sum(s['success'] for s in rows),actual=mean(s['success'] for s in rows),
                expected=mean(expected) if len(expected)==len(rows) else None,shotType=kind,
                beforeEventId=event,eventIds=[s['eventId'] for s in rows],history=[{'eventId':s['eventId'],'made':bool(s['success'])} for s in sorted(rows,key=lambda s:s['eventId'])])
        out['finishing']=out['shooting'].get('two') or out['shooting'].get('three')
    return out if out['creation'] is not None or out['finishing'] else None


def mapped_profile(result):
    """Resolve only a verified event's explicit companion identity, never a name guess."""
    lock=result.get('visualRoleLock') or {};deep=result.get('deepData') or {}
    if lock.get('status')=='locked':
        actor=lock['roles'][0];roster=deep.get('roster') or []
        matches=[p for p in roster if str(p.get('jersey'))==actor.get('jersey') and p.get('team')==actor.get('team')]
        if len(matches)==1:
            profile=build_profile(result,matches[0]['playerId'])
            if profile:return {**profile,'trackId':actor['id'],'identitySource':'vlm-roster-review'}
        if not lock.get("sourceRolesConfirmed"):return None
    events=[e for e in result.get('events',[]) if e.get('visualVerified') and finite(e.get('score')) and e['score']>0]
    if not events:return None
    event=max(events,key=lambda e:e['score']);track=event['actorTrackId']
    mapping=next((p for p in ((result.get('deepData') or {}).get('companion') or {}).get('players',[]) if p.get('trackId')==track),{})
    profile=build_profile(result,mapping.get('sourcePlayerId'))
    return {**profile,'trackId':track} if profile else None
