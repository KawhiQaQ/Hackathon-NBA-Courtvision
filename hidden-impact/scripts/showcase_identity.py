"""Display identities for the reviewed NYK/SAS demo context, not jersey-number recognition."""
TEAM_NAMES={'light':'尼克斯','dark':'马刺'}
def display_names(result):
 # Never apply this clip-specific uniform/team mapping to arbitrary uploaded footage.
 if result['video']['id']!='nba-0042500404-197':return {}
 counts={};names={}
 for p in sorted(result['players'],key=lambda p:int(p['id'][1:])):
  team=TEAM_NAMES.get(p.get('team'))
  if not team:continue
  ordinal=counts.get(team,0);counts[team]=ordinal+1
  names[p['id']]=f'{team} · 球员 {chr(65+ordinal)}'
 e=result['events'][0]
 for key,role in [('actorTrackId','主角'),('beneficiaryTrackId','收益队友'),('defenderTrackId','防守者')]:
  pid=e[key];player=next(p for p in result['players'] if p['id']==pid)
  names[pid]=f"{TEAM_NAMES[player['team']]} · {role}"
 return names
