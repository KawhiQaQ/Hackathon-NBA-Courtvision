"""Presentation continuity for the reviewed clip; never alters analytical scores.
Short, bracketed gaps interpolate positions. Exits retain a docked identity marker.
A direction cue holds its last observed heading when future movement is too small.
"""
import bisect,math
import numpy as np
from showcase_motion import W,H

def prepare_continuity(result,fps=30):
 e=result['events'][0];ids=[e['actorTrackId'],e['beneficiaryTrackId'],e['defenderTrackId']];frames=result['vision']['frames']
 observations={pid:[(f['time'],f['scene'],p) for f in frames for p in f['people'] if p['trackId']==pid] for pid in ids}
 def person_at(pid,t):
  rows=observations[pid];times=[row[0] for row in rows];i=bisect.bisect_right(times,t);a=rows[max(0,i-1)];b=rows[min(len(rows)-1,i)]
  p={k:a[2][k] for k in ['trackId','x','y','w','h','team']};p['association']=.95
  if a[1]==b[1] and 0<b[0]-a[0]<=.75:
   ratio=max(0,min(1,(t-a[0])/(b[0]-a[0])))
   for k in ['x','y','w','h']:p[k]=a[2][k]+ratio*(b[2][k]-a[2][k])
   p['positionSource']='bracketed-interpolation'
  elif abs(t-a[0])>.25:
   p['offscreen']=True;p['x']=.93 if a[2]['x']>.5 else .01;p['w']=.05
   p['positionSource']='edge-identity-marker'
  else:p['positionSource']='observed'
  if pid==e['actorTrackId'] and t>=11.4:
   p.update(offscreen=True,x=.93,w=.05,positionSource='edge-identity-marker')
  return p
 output=[];heading=None
 for i in range(math.ceil(result['video']['duration']*fps)):
  t=i/fps;people=[person_at(pid,t) for pid in ids];actor=people[0];current=min(frames,key=lambda f:abs(f['time']-t));matrix=(current.get('calibration') or {}).get('courtToImage')
  if matrix and not actor.get('offscreen'):
   h=np.array(matrix);pt=np.linalg.solve(h,[actor['x']+actor['w']/2,actor['y']+actor['h'],1]);actor['court']=(pt[:2]/pt[2]).tolist()
  vector=None
  if not actor.get('offscreen'):
   after=person_at(ids[0],min(t+.9,result['video']['duration']))
   if not after.get('offscreen'):vector=np.array([(after['x']+after['w']/2-actor['x']-actor['w']/2)*W,(after['y']+after['h']*.4-actor['y']-actor['h']*.4)*H])
  # For this fixed broadcast view, body displacement is more stable than foot calibration.
  # The cue previews the observed next movement; a pause retains the last valid heading.
  mode='observed-heading'
  if actor.get('offscreen'):vector=np.array([1.,0.]);mode='edge-heading'
  if vector is not None and np.linalg.norm(vector)>8:
   direction=vector/np.linalg.norm(vector)
   if heading is None:heading=direction
   else:
    angle=math.atan2(heading[1],heading[0]);target=math.atan2(direction[1],direction[0]);delta=(target-angle+math.pi)%(2*math.pi)-math.pi
    angle+=max(-.30,min(.30,delta*.45));heading=np.array([math.cos(angle),math.sin(angle)])
  elif heading is None:heading=np.array([1.,0.]);mode='heading-held'
  else:mode='heading-held'
  if actor.get('offscreen'):heading=np.array([1.,0.]);mode='edge-heading'
  origin=np.array([(actor['x']+actor['w']/2)*W,(actor['y']+actor['h']*.4)*H]);length=95
  # Keep the cue inside the picture even when the player has just exited.
  origin[0]=min(W-135,max(135,origin[0]));origin[1]=min(H-65,max(65,origin[1]));end=origin+heading*length
  points=[(origin+(end-origin)*u).tolist() for u in [0,.25,.5,.75,1]]
  output.append({'time':t,'people':people,'heroArrow':{'points':points,'mode':mode}})
 result['presentationMotion']={'fps':fps,'semantics':'Continuous direction cue; holds last heading while stationary. Offscreen identities dock to the edge.','frames':output}
 return result
