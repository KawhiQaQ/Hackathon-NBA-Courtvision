"""Versioned, clip-relative data; source coordinates never silently replace screen coordinates."""
import math

def validate_companion(data,duration):
 def number(x,lo,hi):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and lo<=x<=hi
 if not isinstance(data,dict) or data.get('schema') not in ['hidden-impact/companion-v1','hidden-impact/companion-v2']:raise ValueError('请选择companion-v1或companion-v2配套数据。')
 if not isinstance(data.get('source'),str) or not 1<=len(data['source'])<=200:raise ValueError('配套数据需要注明source。')
 out={'schema':data['schema'],'source':data['source'],'notes':str(data.get('notes',''))[:1000]}
 rows=data.get('opportunity',[])
 if not isinstance(rows,list) or len(rows)>500:raise ValueError('opportunity最多500个时间点。')
 previous=-1;out['opportunity']=[]
 for r in rows:
  if not isinstance(r,dict) or not number(r.get('time'),0,duration) or r['time']<=previous or not number(r.get('expectedPoints'),0,4):raise ValueError('机会记录需递增、在视频内；expectedPoints范围0–4。')
  previous=r['time'];out['opportunity'].append({'time':r['time'],'expectedPoints':r['expectedPoints']})
 if data.get('shotContext') is not None:out['shotContext']=validate_shot_context(data['shotContext'])
 if data['schema'].endswith('v1'):return out
 players=data.get('players',[])
 if not isinstance(players,list) or len(players)>30:raise ValueError('players最多30个身份映射。')
 out['players']=[];ids=set();tracks=set()
 for p in players:
  if not isinstance(p,dict) or any(not isinstance(p.get(k),str) or not 1<=len(p[k])<=80 for k in ['trackId','sourcePlayerId']):raise ValueError('身份映射需trackId和sourcePlayerId。')
  if p['trackId'] in tracks or p['sourcePlayerId'] in ids:raise ValueError('身份映射不可重复。')
  ids.add(p['sourcePlayerId']);tracks.add(p['trackId']);out['players'].append({k:p[k] for k in ['trackId','sourcePlayerId']}|{'label':str(p.get('label',''))[:80]})
 for original,clean in zip(players,out['players']):
  if original.get('jersey') is not None:
   from game_summary import identity
   clean.update(jersey=identity('team',str(original['jersey']))['jersey'])
 rows=data.get('frames',[])
 if not isinstance(rows,list) or len(rows)>1200:raise ValueError('frames最多1200帧。')
 out['frames']=[];previous=-1
 for f in rows:
  if not isinstance(f,dict) or not number(f.get('time'),0,duration) or f['time']<=previous:raise ValueError('tracking时间需递增且位于视频内。')
  previous=f['time'];ps=f.get('players',[])
  if not isinstance(ps,list) or len(ps)>12:raise ValueError('每帧最多12人。')
  clean=[];seen=set()
  for p in ps:
   if not isinstance(p,dict) or p.get('playerId') not in ids or p['playerId'] in seen or any(not number(p.get(k),0,1) for k in ['x','y']) or not number(p.get('confidence',1),0,1):raise ValueError('位置必须为已映射球员的0–1球场坐标。')
   seen.add(p['playerId']);clean.append({k:p[k] for k in ['playerId','x','y']}|{'confidence':p.get('confidence',1)})
  handler=f.get('ballHandlerId')
  if handler is not None and handler not in seen:raise ValueError('持球者必须在对应帧中。')
  out['frames'].append({'time':f['time'],'players':clean,'ballHandlerId':handler})
 rows=data.get('gravity',[])
 if not isinstance(rows,list) or len(rows)>1200:raise ValueError('gravity最多1200条。')
 out['gravity']=[];seen=set()
 for g in rows:
  if not isinstance(g,dict) or g.get('trackId') not in tracks or not number(g.get('time'),0,duration) or not number(g.get('attentionShare'),0,1) or (g['time'],g['trackId']) in seen:raise ValueError('引力记录需已映射球员、视频内时间和0–1 attentionShare。')
  seen.add((g['time'],g['trackId']));out['gravity'].append({k:g[k] for k in ['time','trackId','attentionShare']})
 out['gravity'].sort(key=lambda g:g['time']);return out


def validate_shot_context(ctx):
 """Optional clip-linked opportunity context, independent of tracking availability."""
 from game_summary import finite,identity
 if not isinstance(ctx,dict):raise ValueError('shotContext应为对象。')
 identity(ctx.get('team'),'0')
 if not isinstance(ctx.get('gameId'),str) or not 1<=len(ctx['gameId'])<=80:raise ValueError('shotContext需要gameId。')
 if not isinstance(ctx.get('playerId'),str) or not 1<=len(ctx['playerId'])<=80:raise ValueError('需要出手球员playerId。')
 def shot(s):
  if not isinstance(s,dict) or not finite(s.get('value')) or not 0<=s['value']<=1 or s.get('shotType') not in ['2分投篮','3分投篮']:raise ValueError('出手需0–1预期命中率及两分/三分类型。')
  if s.get('success') is not None and (isinstance(s['success'],bool) or s['success'] not in [0,1]):raise ValueError('success为0、1或省略。')
  out={k:s[k] for k in ['value','shotType','success'] if k in s}
  if s.get('period') is not None:
   if not isinstance(s['period'],int) or not 1<=s['period']<=20:raise ValueError('节次无效。')
   out['period']=s['period']
  if s.get('gameClock') is not None:out['gameClock']=str(s['gameClock'])[:20]
  return out
 clean={k:ctx[k] for k in ['gameId','team','playerId']};clean['shooter']=str(ctx.get('shooter','出手队友'))[:80];clean['shot']=shot(ctx.get('shot'))
 if ctx.get('eventId') is not None:
  if not isinstance(ctx['eventId'],(str,int)) or len(str(ctx['eventId']))>80:raise ValueError('eventId无效。')
  clean['eventId']=ctx['eventId']
 peer=ctx.get('playerShots')
 if peer is not None:
  if not isinstance(peer,dict) or peer.get('gameId')!=ctx['gameId'] or str(peer.get('playerId'))!=ctx['playerId']:raise ValueError('同场对照需匹配比赛与出手者。')
  samples=peer.get('shotList')
  if not isinstance(samples,list) or len(samples)>500:raise ValueError('同场对照最多500条。')
  clean['playerShots']={'gameId':ctx['gameId'],'playerId':ctx['playerId'],'shotList':[shot(s) for s in samples]}
 return clean
