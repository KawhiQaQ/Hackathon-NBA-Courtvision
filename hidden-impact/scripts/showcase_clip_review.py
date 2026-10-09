"""Clip-specific visual corrections, reviewed against the source at the stated times.
These manual annotations repair missed/merged identities, not model predictions.
Coordinates below use a 480 x 270 reference image. No generic jersey inference.
"""
from copy import deepcopy
import numpy as np

# time, x, y, width, height. 44 is absent in the saved detector before 8.333 s.
HERO=[(6,245,182,27,54),(6.5,268,182,34,55),(7,310,161,29,68),(7.5,340,164,43,57),(8,331,163,43,59),(8.167,317,178,35,50),(8.333,299,171,42,51)]
DEF21=[(7.5,194,135,25,52),(8,259,140,29,55),(8.25,282,145,22,57),(8.5,286,147,21,56),(8.75,275,146,22,56),(9,260,146,27,55),(9.25,229,148,30,52),(9.5,186,135,49,70)]
DEF30=[(7.5,188,156,31,65),(8,267,152,29,61),(8.25,292,159,32,53),(8.5,301,154,30,63),(8.75,294,149,23,65),(9,291,150,30,65),(9.25,300,150,23,66),(9.5,303,149,21,68)]
def box_at(rows,t):
 if not rows[0][0]<=t<=rows[-1][0]:return None
 for a,b in zip(rows,rows[1:]):
  if a[0]<=t<=b[0]:
   ratio=(t-a[0])/(b[0]-a[0]);return {k:(a[i]+ratio*(b[i]-a[i]))/size for i,(k,size) in enumerate([('x',480),('y',270),('w',480),('h',270)],1)}

def reviewed_tracks(result):
 for f in result['vision']['frames']:
  t=f['time'];original={p['trackId']:p for p in f['people']}
  updates=[]
  for pid,rows,source,team in [('P6',HERO,'P6','light'),('P21',DEF21,'P7' if t<7.5 else 'P19','dark'),('P30',DEF30,'P5' if t<7.5 else 'P7','dark')]:
   box=box_at(rows,t);prior=original.get(source)
   if pid=='P6' and t<6:continue
   if pid!='P6' and not 6<=t<=11.333:continue
   if not box and not prior:continue
   p=deepcopy(prior or {});p.update(box or {});p.update(trackId=pid,team=team,association=.95,annotationSource='manual-source-video-review')
   matrix=(f.get('calibration') or {}).get('courtToImage')
   if matrix:
    point=np.linalg.solve(np.array(matrix),[p['x']+p['w']/2,p['y']+p['h'],1]);p['court']=(point[:2]/point[2]).tolist()
   else:p.pop('court',None)
   updates.append(p)
  ids={p['trackId'] for p in updates};f['people']=[p for p in f['people'] if p['trackId'] not in ids]+updates
 for pid,source in [('P21','P7'),('P30','P5')]:
  p=deepcopy(next(p for p in result['players'] if p['id']==source));p.update(id=pid,label='马刺防守者',team='dark',role='defense');result['players'].append(p)
 result['clipAnnotations']={'source':'manual-source-video-review','jersey44TrackId':'P6','defenderTracks':['P21','P30'],'reason':'44号前段漏检；两名近身防守者在交汇处发生轨迹混淆，按连续画面修正。'}
 return result
