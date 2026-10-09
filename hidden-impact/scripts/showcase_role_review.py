"""Explicit local review selection. A changed actor does not inherit another actor's score."""
import math,statistics

def reviewed_demo(result):
 if result['video']['id']!='nba-0042500404-197':raise ValueError('This role review belongs to the NYK/SAS demo only')
 actor,beneficiary,defender='P2','P1','P4'
 start,key,end=7.5,8.63,9.5
 frames=result['vision']['frames'];series=[];evidence=[]
 for f in frames:
  if not start<=f['time']<=end:continue
  people={p['trackId']:p for p in f['people']}
  if not all(pid in people and people[pid].get('court') for pid in [actor,beneficiary,defender]):continue
  a,b,d=[people[pid] for pid in [actor,beneficiary,defender]]
  series.append({'time':f['time'],'separation':math.dist(b['court'],d['court']),'engagement':math.dist(a['court'],d['court']),'a':a['court'],'b':b['court'],'d':d['court']})
 for t in [start,key,end]:
  f=min(frames,key=lambda f:abs(f['time']-t));people={p['trackId']:p for p in f['people']}
  evidence.append({'time':t,'text':'人工指定观察对象；收益队友按出手画面绑定。','marks':[{**people[pid],'role':role} for pid,role in [(actor,'actor'),(beneficiary,'beneficiary'),(defender,'defender')] if pid in people]})
 result['events']=[{'id':'reviewed-focus-P2-shooter-P1','actorTrackId':actor,'beneficiaryTrackId':beneficiary,'defenderTrackId':defender,'start':start,'keyTime':key,'end':end,'score':None,'components':[],'actionType':'review','origin':'user-selected-visual-review','observations':evidence,'measurement':{'score':None,'rawScore':None,'components':[],'series':series,'quality':None,'separationBefore':statistics.median(s['separation'] for s in series[:3]),'separationAfter':statistics.median(s['separation'] for s in series[-3:]),'sustainedSeconds':None,'expectedPointsChange':None,'reason':'角色重新绑定，旧候选评分失效；尚未确认机会创造关系。','units':'参考球场单位'}}]
 result['roleReview']={'source':'user-selection-and-shot-frame-review','status':'hypothesis','actorTrackId':actor,'beneficiaryTrackId':beneficiary,'defenderTrackId':defender,'shooterEvidenceTime':9.5,'scoreInvalidated':True,'note':'得分者依据出手帧与官方出手记录绑定；主角为用户指定观察对象；防守者为靠近主角的观察对象，非已确认对位。'}
 for p in result['players']:
  p.update(score=None,components=[],eventIds=[],measurement=None)
  if p['role']=='defense':p['status']='defense'
  elif p['id']==beneficiary:p['status']='shooter';p['reason']='本回合最终出手者，不参与幕后主角排名。'
  else:p['status']='insufficient';p['reason']='角色已重新绑定，贡献归因待复核。'
  if p['id']==actor:p.update(evidence=evidence,eventIds=[result['events'][0]['id']],summary='用户指定观察主角，贡献大小待核验。')
 result['focusPlayerId']=actor
 return result
