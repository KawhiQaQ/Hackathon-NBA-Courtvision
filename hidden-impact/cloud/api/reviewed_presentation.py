"""Explicit, source-bound presentation review. Never changes model event scores.

Reviewed image-space anchors are independent of detector track IDs. This keeps
identity corrections usable by both replay and evidence-frame rendering while
preserving the unedited model output and the editorial provenance.
"""
import bisect
import copy
import math
import re
from presentation import insights, finite, FIELDS, arrow_anchor

ROLE_STYLE=[('actor','主角','#f4c45e'),('beneficiary','受益队友','#77cfe4'),('defender','防守者','#ee927f')]


def validate(review,result,sha256):
    if not isinstance(review,dict) or review.get('schema')!='hidden-impact/presentation-review-v1':raise ValueError('Unsupported presentation review')
    if review.get('videoId')!=result['video']['id'] or review.get('videoSha256')!=sha256 or not re.fullmatch('[a-f0-9]{64}',sha256 or ''):raise ValueError('Review belongs to a different video')
    if review.get('source')!='human-reviewed-video':raise ValueError('Review source must be explicit')
    duration=result['video']['duration'];roles=review.get('roles')
    if not isinstance(roles,list) or [r.get('role') for r in roles]!=[r[0] for r in ROLE_STYLE]:raise ValueError('Exactly three fixed roles are required')
    if len({(r.get('team'),r.get('jersey')) for r in roles})!=3:raise ValueError('Roles must refer to distinct players')
    for role in roles:
        if role.get('playerId') is not None and not re.fullmatch(r'\d+',str(role['playerId'])):raise ValueError('Invalid NBA player ID')
        if not isinstance(role.get('team'),str) or not 1<=len(role['team'])<=30 or not re.fullmatch(r'\d{1,2}',str(role.get('jersey',''))):raise ValueError('Invalid player identity')
        rows=role.get('anchors',[])
        if not 2<=len(rows)<=500:raise ValueError('Missing reviewed positions')
        last=-1
        for row in rows:
            if not isinstance(row,list) or len(row)!=4 or not finite(row[0]) or not last<row[0]<=duration:raise ValueError('Invalid keyframe time')
            last=row[0]
            if row[1:] == [None,None,None]:continue
            if not all(finite(n) for n in row[1:]) or not 0<=row[1]<=640 or not 0<=row[2]<=360 or not 10<=row[3]<=180:raise ValueError('Invalid image-space anchor')
        if rows[0][0]!=0 or abs(rows[-1][0]-duration)>.001:raise ValueError('Review must cover the whole clip, including offscreen intervals')
    segments=review.get('segments',[])
    if not 2<=len(segments)<=12:raise ValueError('Missing story segments')
    previous=0
    for s in segments:
        if not all(finite(s.get(k)) for k in ['start','end','seek']) or abs(s['start']-previous)>.001 or not s['start']<=s['seek']<s['end']<=duration:raise ValueError('Story must cover the clip in chronological order')
        if not isinstance(s.get('title'),str) or not 1<=len(s['title'])<=40 or not isinstance(s.get('text'),str) or not 1<=len(s['text'])<=300:raise ValueError('Invalid story copy')
        previous=s['end']
    if abs(previous-duration)>.001:raise ValueError('Story does not cover the clip')
    contexts=review.get('gravityContexts',[])
    if not isinstance(contexts,list) or len(contexts)>12:raise ValueError('Invalid gravity contexts')
    previous=0
    for c in contexts:
        if not isinstance(c,dict) or not re.fullmatch(r'\d+',str(c.get('playerId',''))) or c.get('metric') not in dict(FIELDS):raise ValueError('Invalid gravity identity or metric')
        if not finite(c.get('start')) or not finite(c.get('end')) or not previous<=c['start']<c['end']<=duration:raise ValueError('Invalid gravity time window')
        previous=c['end']
    return review


def build(source,review,sha256,source_job,fps=24,profiles=None):
    validate(review,source,sha256)
    result=copy.deepcopy(source)
    if profiles is not None and result.get('deepData'):
        result['deepData']['playerProfiles']=copy.deepcopy(profiles)
    # Immutable source job remains the authoritative automatic analysis.
    result['presentationReview']={**copy.deepcopy(review),'sourceJob':source_job}
    result['originalNarration']=copy.deepcopy(source.get('narration'))
    segments=[{**s,'frameTimes':[s['seek']]} for s in review['segments']]
    result['narration']={'status':'reviewed','source':'human-reviewed-video','modelInvoked':False,'segments':segments}
    for key in ['tacticalReplay','renderError','thumbnails']:result.pop(key,None)
    roles=[]
    for r,(_,label,color) in zip(review['roles'],ROLE_STYLE):
        name=f"{r['team']} {r['jersey']}号"
        roles.append(dict(id='review-'+r['role'],name=name,label=label,displayName=name+' · '+label,color=color))
    info=insights(result)
    info['gravityContexts']=copy.deepcopy(review.get('gravityContexts',[]))
    from actor_profile import build_profile
    info['actorProfile']=build_profile(result,review['roles'][0].get('playerId'))
    info['cues']=[{**s,'phase':s['title'],'evidence':f"画面 · {s['seek']:.2f}s"} for s in segments]
    evidence=[dict(time=s['seek'],label=s['title'],chapter=s['title'],text=s['text'],kind='analysis',source='human-reviewed-video',image=f'frame-{i+1}.jpg') for i,s in enumerate(segments)]
    official=(result.get('deepData') or {}).get('official') or {}
    result['presentation']=dict(schema='hidden-impact/showcase-v1',mode='analysis',status='ready',analysisStatus='reviewed-story',
        eventId=str(official.get('eventId','')),video='replay.mp4',original='original.mp4',videoId=result['video']['id'],gameId=official.get('gameId'),team=review['roles'][0]['team'],
        actor={'id':roles[0]['id'],'label':roles[0]['name']},identity={'jersey':str(review['roles'][0]['jersey']),'confirmed':True,'source':'human-reviewed-video'},
        score=None,components=[],roles=roles,evidence=evidence,insights=info,matchup=official.get('matchup','回合分析'),
        actionTitle=review.get('title','从掩护到终结'),summary=review.get('summary',''),storyTitle='沿着这次配合，看到机会如何出现。',
        generation={'analysisModel':result.get('model'),'modelInvoked':result.get('modelInvoked',False),'sourceJob':source_job,'presentationSource':'human-reviewed-video','narration':{'status':'reviewed','modelInvoked':False,'source':'human-reviewed-video'}})
    from story_direction import build_direction
    result['presentation']['direction']=build_direction(result['presentation'],result['video']['duration'])
    result['presentationMotion']=build_motion(review,result['video']['duration'],fps)
    return result


def build_motion(review,duration,fps=24):
    width,height=1280,720
    def locate(r,t):
        rows=r['anchors'];times=[row[0] for row in rows];j=bisect.bisect_left(times,t)
        if j<len(rows) and abs(times[j]-t)<.00001:a=b=rows[j]
        else:a,b=rows[max(0,j-1)],rows[min(len(rows)-1,j)]
        pid='review-'+r['role']
        if a[1] is None or b[1] is None:return dict(trackId=pid,offscreen=True,positionSource='reviewed-offscreen')
        f=(t-a[0])/max(.000001,b[0]-a[0]);x,y,h=[a[k]+f*(b[k]-a[k]) for k in (1,2,3)]
        bw=h*.48
        return dict(trackId=pid,x=(x-bw/2)/640,y=(y-h)/360,w=bw/640,h=h/360,positionSource='reviewed-keyframe-interpolation')
    frames=[];headings={};lengths={}
    for i in range(math.ceil(duration*fps)):
        t=i/fps;people=[locate(r,t) for r in review['roles']];arrows={}
        for idx,key in [(0,'heroArrow'),(2,'defenderArrow')]:
            p=people[idx];arrow=None
            if not p.get('offscreen'):
                q=locate(review['roles'][idx],min(duration,t+.65))
                if not q.get('offscreen'):
                    dx=(q['x']+q['w']/2-p['x']-p['w']/2)*width;dy=(q['y']+q['h']-p['y']-p['h'])*height
                else:dx=dy=0
                if math.hypot(dx,dy)>6:
                    angle=math.atan2(dy,dx);old=headings.get(idx,angle)
                    headings[idx]=old+max(-4/fps,min(4/fps,((angle-old+math.pi)%(2*math.pi)-math.pi)*.4))
                    lengths[idx]=.8*lengths.get(idx,80)+.2*max(64,min(112,math.hypot(dx,dy)))
                if idx in headings:
                    angle=headings[idx];u=(math.cos(angle),math.sin(angle));length=lengths[idx]
                    start=arrow_anchor(p,u,width,height)
                    points=[[start[k]+u[k]*length*v/16 for k in (0,1)] for v in range(17)]
                    arrow=dict(trackId=p['trackId'],points=points,mode='reviewed-image-direction')
            else:headings.pop(idx,None);lengths.pop(idx,None)
            arrows[key]=arrow
        frames.append(dict(time=round(t,5),people=people,**arrows))
    return dict(schema='hidden-impact/presentation-motion-v2',source='human-reviewed-video',fps=fps,width=width,height=height,frames=frames)
