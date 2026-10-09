"""Separate the presentation contract from the complete analysis/audit record.
Export only fields consumed by the UI. Keep original provenance in the source archive;
a presentation payload must never assert successful inference or verified scoring.
"""
import json
from pathlib import Path

def pick(value,keys):return {key:value[key] for key in keys if key in value}

def person(value):return pick(value,['trackId','x','y','w','h','team','court','association','offscreen','role'])

def export_payload(result,manifest,root):
 root=Path(root)
 if 'roleReview' not in result:raise ValueError('Export requires the full analysis, not an already exported presentation')
 archive=root/'data/review-archive';archive.mkdir(parents=True,exist_ok=True)
 # This record remains reproducible in the repository and outside the web deployment root.
 (archive/'showcase-audit.json').write_text(json.dumps({'analysis':result,'showcase':manifest},ensure_ascii=False,separators=(',',':')))
 ids={role['id'] for role in manifest['roles']};event=result['events'][0];event_id='play-'+result['video']['id']
 observations=[{'time':o['time'],'text':'关键动作画面','marks':[person(p) for p in o.get('marks',[]) if p['trackId'] in ids]} for o in event['observations']]
 players=[]
 for p in result['players']:
  if p['id'] not in ids:continue
  item=pick(p,['id','label','team','role','status','visibleSeconds'])
  item.update(score=None,components=[],eventIds=[event_id] if p['id']==result['focusPlayerId'] else [],evidence=observations if p['id']==result['focusPlayerId'] else [],summary=event['summary'] if p['id']==result['focusPlayerId'] else '')
  players.append(item)
 public_event=pick(event,['actorTrackId','beneficiaryTrackId','defenderTrackId','defenderTrackIds','supportTrackIds','actor','beneficiary','start','keyTime','end','title','commentary','summary'])
 public_event.update(id=event_id,actionType='presentation',score=None,components=[],observations=observations)
 vision={'aspectRatio':result['vision']['aspectRatio'],'coordinateSystem':'normalized-image','frames':[{**pick(f,['time','scene']), 'people':[person(p) for p in f['people'] if p['trackId'] in ids]} for f in result['vision']['frames']]}
 motion={'fps':result['presentationMotion']['fps'],'frames':[{'time':f['time'],'people':[person(p) for p in f['people']],'heroArrow':{'points':f['heroArrow']['points']}} for f in result['presentationMotion']['frames']]}
 public={'schema':'hidden-impact/presentation-v1','demo':True,**pick(result,['video','overview','focusPlayerId','teamNames','tacticalReplay']),'displayNames':{k:v for k,v in result['displayNames'].items() if k in ids},'players':players,'events':[public_event],'vision':vision,'presentationMotion':motion,'presentationScore':{**pick(result['presentationScore'],['value','trackId']),'kind':'presentation'}}
 public_manifest=pick(manifest,['schema','teamId','mode','title','matchup','source','duration','renderStyle','width','height','video','original','poster','actor','roles','score','components','evidence','storyOutcome'])
 public_manifest['scoreKind']='presentation'
 if 'insights' in manifest:public_manifest['insights']=manifest['insights']
 out=root/'web/demo'
 (out/'analysis.json').write_text(json.dumps(public,ensure_ascii=False,separators=(',',':')))
 (out/'showcase.json').write_text(json.dumps(public_manifest,ensure_ascii=False,indent=2))
 return public,public_manifest
