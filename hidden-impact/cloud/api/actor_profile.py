"""Player-bound background evidence, independent of per-possession contribution."""
from statistics import mean
from presentation import finite


def build_profile(result, player_id):
    deep=result.get('deepData') or {};official=deep.get('official') or {}
    if not player_id or deep.get('videoId')!=result['video']['id']:return None
    profile=next((p for p in deep.get('playerProfiles',[]) if str(p.get('playerId'))==str(player_id) and p.get('gameId')==official.get('gameId')),None)
    if not profile:return None
    leverage=profile.get('leverage') or {};shots=profile.get('shots') or {}
    valid_leverage=str(leverage.get('PLAYERID'))==str(player_id)
    out=dict(playerId=str(player_id),name=profile.get('name','主角'),scope=profile.get('scope','阶段汇总'),sources=profile.get('sources',[]),finishing=None)
    for dest,key in [('creation','CREATION_LVG'),('scoring','SHOT_LVG')]:
        value=leverage.get(key);out[dest]=value if valid_leverage and finite(value) else None
    out['games']=leverage.get('GP') if valid_leverage else None
    # Compare only completed earlier events from this game and this player.
    # Never let later made shots leak into the actor's pre-possession profile.
    event=official.get('eventId')
    if str(shots.get('playerId'))==str(player_id) and shots.get('gameId')==official.get('gameId') and finite(event):
        prior=[s for s in shots.get('shotList',[]) if str(s.get('playerId'))==str(player_id) and s.get('gameId')==official.get('gameId') and finite(s.get('eventId')) and s['eventId']<event and s.get('shotType')=='2分投篮' and s.get('success') in [0,1] and finite(s.get('value')) and 0<=s['value']<=1]
        if prior:
            out['finishing']=dict(sampleCount=len(prior),made=sum(s['success'] for s in prior),actual=mean(s['success'] for s in prior),expected=mean(s['value'] for s in prior),beforeEventId=event,eventIds=[s['eventId'] for s in prior])
    return out if out['creation'] is not None or out['finishing'] else None
