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
 if data.get('alignment') is not None:
  a=data['alignment']
  if not isinstance(a,dict) or not number(a.get('shotVideoTime'),0,duration):raise ValueError('出手对齐时间必须在视频内。')
  out['alignment']={'shotVideoTime':a['shotVideoTime'],'source':str(a.get('source','supplied-companion'))[:100]}
 if data.get('roster') is not None:
  if not isinstance(data['roster'],list) or len(data['roster'])>30:raise ValueError('roster最多30人。')
  import re
  out['roster']=[]
  for p in data['roster']:
   if not isinstance(p,dict) or not re.fullmatch(r'\d{1,12}',str(p.get('playerId',''))) or not re.fullmatch(r'\d{1,2}',str(p.get('jersey',''))):raise ValueError('名单需真实playerId与球衣号码。')
   out['roster'].append({k:str(p.get(k,''))[:80] for k in ['playerId','jersey','name','team','appearance','appearanceSource']})
 if data.get('playerProfiles') is not None:
  profiles=data['playerProfiles'];game=(out.get('shotContext') or {}).get('gameId')
  if not isinstance(profiles,list) or len(profiles)>30 or not game:raise ValueError('球员数据需要对应比赛。')
  out['playerProfiles']=[]
  for p in profiles:
   if not isinstance(p,dict) or p.get('gameId')!=game:raise ValueError('球员数据比赛不匹配。')
   pid=str(p.get('playerId',''));shots=p.get('shots') or {};rows=shots.get('shotList',[])
   if str(shots.get('playerId'))!=pid or shots.get('gameId')!=game or not isinstance(rows,list) or len(rows)>100:raise ValueError('球员出手记录不匹配。')
   clean=[]
   for row in rows:
    s=validate_shot_context({'gameId':game,'team':out['shotContext']['team'],'playerId':pid,'shot':row})['shot']
    if not isinstance(row.get('eventId'),int) or isinstance(row['eventId'],bool):raise ValueError('球员出手缺少eventId。')
    clean.append({**s,'eventId':row['eventId'],'gameId':game,'playerId':pid})
   leverage=p.get('leverage') or {};lv={'PLAYERID':pid}
   if str(leverage.get('PLAYERID'))==pid:
    for key in ['CREATION_LVG','SHOT_LVG','GP']:
     if number(leverage.get(key),-100000,100000):lv[key]=leverage[key]
   out['playerProfiles'].append({'playerId':pid,'gameId':game,'name':str(p.get('name',''))[:80],'scope':str(p.get('scope',''))[:200],
    'shots':{'playerId':pid,'gameId':game,'shotList':clean},'leverage':lv,'sources':[s[:500] for s in p.get('sources',[])[:10] if isinstance(s,str)]})
 if data.get('uniforms') is not None:
  u=data['uniforms']
  if not isinstance(u,dict) or len(u)>2 or any(not isinstance(k,str) or not isinstance(v,str) or len(k)>80 or len(v)>100 for k,v in u.items()):raise ValueError('球衣描述最多两队。')
  out['uniforms']=dict(u)
 if data.get('playByPlay') is not None:
  rows=data['playByPlay'];game=(out.get('shotContext') or {}).get('gameId');known={p['playerId'] for p in out.get('roster',[])}
  if not isinstance(rows,list) or len(rows)>300 or not game:raise ValueError('逐回合事件需要对应比赛。')
  out['playByPlay']=[]
  for row in rows:
   if not isinstance(row,dict) or row.get('gameId')!=game or str(row.get('playerId')) not in known:raise ValueError('逐回合事件比赛或球员不匹配。')
   if row.get('type') not in ['miss','made-two','made-three','offensive-rebound','assist','shooting-foul','block']:raise ValueError('未知事件类型。')
   if not isinstance(row.get('source'),str) or not row['source'].startswith('https://'):raise ValueError('逐回合事件需要来源。')
   if not number(row.get('period'),1,20) or not isinstance(row.get('gameClock'),str):raise ValueError('逐回合事件需要节次与时钟。')
   import re
   if not re.fullmatch(r'\d{1,2}:[0-5]\d(?:\.\d+)?',row['gameClock']):raise ValueError('比赛时钟无效。')
   clean={k:row[k] for k in ['gameId','playerId','type','period','gameClock','source']}
   for key in ['eventId','relatedEventId']:
    if key in row:
     if not number(row[key],0,1000000):raise ValueError('事件编号无效。')
     clean[key]=row[key]
   if row.get('defenderId') in known:clean['defenderId']=row['defenderId']
   out['playByPlay'].append(clean)
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
 if ctx.get('shooterJersey') is not None:
  import re
  if not re.fullmatch(r'\d{1,2}',str(ctx['shooterJersey'])):raise ValueError('出手者号码无效。')
  clean['shooterJersey']=str(ctx['shooterJersey'])
 if ctx.get('rosterGravity') is not None:
  rows=ctx['rosterGravity']
  if not isinstance(rows,list) or len(rows)>40:raise ValueError('引力画像最多40人。')
  clean['gravityScope']=str(ctx.get('gravityScope','阶段汇总'))[:200];clean['rosterGravity']=[]
  for p in rows:
   if not isinstance(p,dict):raise ValueError('引力画像格式错误。')
   gravity={k:p['gravity'][k] for k in ['OVERALL_GRAV','ON_BALL_PERIM_GRAV','ON_BALL_INTERIOR_GRAV','OFF_BALL_PERIM_GRAV','OFF_BALL_INTERIOR_GRAV'] if finite((p.get('gravity') or {}).get(k))}
   clean['rosterGravity'].append({'id':str(p.get('id',''))[:30],'name':str(p.get('name',''))[:80],'team':str(p.get('team',''))[:30],'games':p.get('games') if finite(p.get('games')) else None,'gravity':gravity})
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
