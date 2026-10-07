"""Join real SkillCorner dynamic events by chance + temporal precedence (no full tracking)."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for game in ['114243','184439']:
 doc=json.loads((ROOT/f'web/data/{game}.json').read_text());events=json.loads((ROOT/f'data/raw/{game}_dynamic_events.json').read_text())
 for shot in doc['shots']:
  related={}
  for family in ['off_ball_screens','picks','handoffs','passes','drives','closeouts','matchups']:
   rows=[r for r in events.get(family,[]) if r.get('chanceId')==shot['chanceId'] and r.get('frame',r.get('startFrame',0))<=shot['frame']]
   related[family]=rows
  shot['context']={'source':'SkillCorner Dynamic Events','gravity':None,'gravityNote':'数据源未提供原生 Gravity；关联强度为本站快照估计。','events':related}
  for candidate in shot['analysis']['candidates']:
   pid=int(candidate['playerId']);proof=[]
   for family in ['off_ball_screens','picks']:
    for row in related[family]:
     if row.get('screenerId')!=pid:continue
     seconds=(shot['frame']-row.get('frame',shot['frame']))/25
     proof.append({'kind':family,'id':row['id'],'secondsBeforeShot':round(seconds,2),'direct':row.get('direct'),'ledToShot':row.get('ledToShot'),'cutterId':str(row.get('cutterId',row.get('ballhandlerId',''))),'coverage':row.get('cutterDefType',row.get('bhrDefType')),'screenCoverage':row.get('screenerDefType',row.get('scrDefType')),'linkedToShooter':row.get('cutterId',row.get('ballhandlerId'))==int(shot['shooterId'])})
   candidate['actionEvidence']=proof
 (ROOT/f'web/data/{game}.json').write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')))
 print(game,'shots with screens',sum(bool(s['context']['events']['off_ball_screens']) for s in doc['shots']))
