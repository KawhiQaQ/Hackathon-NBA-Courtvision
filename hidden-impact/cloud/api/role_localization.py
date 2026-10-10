"""Lock replay identities using VLM choices of detector boxes, never invented coordinates.

The scoring observations remain immutable. Replay anchors are a separate model
output, so correcting a receiver cannot silently transfer an old player's score.
"""
import base64,copy,io,math,re
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageDraw,ImageFont

ROLE_KEYS=('actor','beneficiary','defender')
TRACK_KEYS=('actorTrackId','beneficiaryTrackId','defenderTrackId')

def jpeg(image):
    out=io.BytesIO();image.save(out,format='JPEG',quality=80)
    return base64.b64encode(out.getvalue()).decode()

def prepare_frames(dense,vision,duration):
    frames=[]
    for target in [i/2 for i in range(math.ceil(duration*2))]:
        original=min(dense,key=lambda f:abs(f['time']-target))
        f=min(vision['frames'],key=lambda f:abs(f['time']-original['time']))
        if abs(f['time']-original['time'])>.04:continue
        im=Image.open(io.BytesIO(base64.b64decode(original['image']))).convert('RGB')
        im.thumbnail((960,960));raw=im.copy();draw=ImageDraw.Draw(im);font=ImageFont.load_default(size=17)
        boxes={}
        for i,p in enumerate(f['people']):
            if p.get('confidence',0)<.35:continue
            name=f'D{i}';boxes[name]=p
            x,y,w,h=[p[k]*(im.width if k in ('x','w') else im.height) for k in ('x','y','w','h')]
            draw.rectangle((x,y,x+w,y+h),outline='#ffff55',width=2)
            draw.rectangle((x,max(0,y-19),x+40,max(0,y-19)+19),fill='#101010')
            draw.text((x+2,max(0,y-19)),name,font=font,fill='white')
        sheet=Image.new('RGB',(800, max(1,math.ceil(len(boxes)/5))*190),'#17251e');sd=ImageDraw.Draw(sheet)
        for index,(name,p) in enumerate(boxes.items()):
            x,y,w,h=[p[k]*(raw.width if k in ('x','w') else raw.height) for k in ('x','y','w','h')]
            crop=raw.crop((int(x),int(y),int(x+w),int(y+h)));crop.thumbnail((150,164))
            ox=(index%5)*160;oy=(index//5)*190
            sheet.paste(crop,(ox+(160-crop.width)//2,oy+24));sd.text((ox+6,oy+2),name,font=font,fill='white')
        frames.append(dict(crops=jpeg(sheet),time=original['time'],scene=f.get('scene',0),cameraOffset=f.get('cameraOffset',[0,0]),boxes=boxes,image=jpeg(im),raw=raw))
    return frames

def reference(frame,box):
    im=frame['raw'];x,y,w,h=[box[k]*(im.width if k in ('x','w') else im.height) for k in ('x','y','w','h')]
    crop=im.crop((max(0,int(x-w*.15)),max(0,int(y-h*.05)),min(im.width,int(x+w*1.15)),min(im.height,int(y+h*1.05))))
    crop.thumbnail((200,260))
    return jpeg(crop)

def clean_frame(f):return {'time':f['time'],'image':f['image'],'detections':list(f['boxes']),'crops':f['crops'],'individuals':[{'id':name,'image':reference(f,box)} for name,box in list(f['boxes'].items())[:18]]}

def grounded_reference(value,frames):
    if not isinstance(value,dict) or not isinstance(value.get('time'),(int,float)):return None
    f=min(frames,key=lambda f:abs(f['time']-value['time']))
    if abs(f['time']-value['time'])>.04:return None
    p=f['boxes'].get(value.get('detectionId'))
    return (f,p) if p else None

def resolve(result,raw_vision,dense,invoke,progress=None):
    hints=event_role_hints(result.get('deepData') or {})
    if all(key in hints for key in ROLE_KEYS):return resolve_known(result,raw_vision,dense,invoke,progress,hints)
    events=[e for e in result.get('events',[]) if e.get('visualVerified')]
    duration=result['video']['duration']
    event=max(events,key=lambda e:e['score']) if events else None
    frames=prepare_frames(dense,raw_vision,duration)
    if not frames:raise ValueError('No detector-backed replay frames')
    actor_ref=None
    if event:
        target=(event['start']+event['end'])/2
        vf=min(result['vision']['frames'],key=lambda f:abs(f['time']-target))
        actor=next((p for p in vf['people'] if p['trackId']==event['actorTrackId']),None)
        if actor:
            af=min(frames,key=lambda f:abs(f['time']-vf['time']))
            def distance(p):return math.hypot(p['x']+p['w']/2-actor['x']-actor['w']/2,p['y']+p['h']-actor['y']-actor['h'])
            choices=sorted(af['boxes'].values(),key=distance)
            if choices and distance(choices[0])<=actor['h']*.8:actor_ref={'image':reference(af,choices[0]),'time':af['time']}
    # Concentrate on release/finish instead of a sparse whole-clip montage that
    # can omit the actual shot. Include the candidate action as context.
    shot_hint=((result.get('deepData') or {}).get('alignment') or {}).get('shotVideoTime') or result.get('vision',{}).get('attackEnd') or duration*.8
    target=(event['start']+event['end'])/2 if event else max(0,shot_hint-4)
    indices=set()
    for t in [max(0,shot_hint-d) for d in (6,4,2,1,.5,0)]+[event['start'] if event else max(0,shot_hint-8),target]:
        indices.add(min(range(len(frames)),key=lambda i:abs(frames[i]['time']-t)))
    selected=[frames[i] for i in sorted(indices)]
    official=(result.get('deepData') or {}).get('official') or {}
    hints=event_role_hints(result.get('deepData') or {})
    intro=invoke({'mode':'resolve-replay-roles','video':result['video'],'actorReference':actor_ref,
        'event':{k:event.get(k) for k in ['start','end','actionType']} if event else None,'shot':{k:official.get(k) for k in ['shooter','shooterJersey','team','shot']},'roster':(result.get('deepData') or {}).get('roster',[]),'shotTimeHint':shot_hint,'roleHints':hints,
        'frames':[clean_frame(f) for f in selected]})
    if intro.get('beneficiaryIsFinalShooter') is not True or intro.get('distinctRoles') is not True:raise ValueError('Final shooter or distinct roles remain unconfirmed')
    shot_time=intro.get('shotTime')
    if isinstance(shot_time,bool) or not isinstance(shot_time,(int,float)) or not math.isfinite(shot_time) or not 0<=shot_time<duration:raise ValueError('Invalid verified shot time')
    roles=[];refs=[]
    for key,source_key in zip(ROLE_KEYS,TRACK_KEYS):
        r=next((r for r in intro.get('roles',[]) if r.get('role')==key),None)
        pair=grounded_reference(r.get('reference') if r else None,selected)
        if not pair:raise ValueError('Role reference missing: '+key)
        f,p=pair;jersey=str(r.get('jersey') or '')
        if not re.fullmatch(r'\d{1,2}',jersey):jersey=''
        if key=='beneficiary' and official.get('shooterJersey') and jersey!=str(official['shooterJersey']):raise ValueError('Visual shooter jersey contradicts official shooter')
        team=str(r.get('team') or '')[:25]
        hint=hints.get(key)
        if hint and (jersey!=hint['jersey'] or team!=hint['team']):raise ValueError('Role contradicts official play-by-play: '+key)
        name=(team+' '+jersey+'号').strip() if jersey else (team+' '+{'actor':'配合球员','beneficiary':'终结球员','defender':'防守球员'}[key]).strip()
        roles.append(dict(role=key,id='replay-'+key,sourceTrackId=event[source_key] if event else None,name=name,jersey=jersey,team=team,reference=r['reference']))
        refs.append(dict(role=key,name=name,image=reference(f,p)))
    for a in range(3):
        for b in range(a):
            if roles[a]['reference']==roles[b]['reference'] or (roles[a]['jersey'] and roles[a]['jersey']==roles[b]['jersey'] and roles[a]['team']==roles[b]['team']):raise ValueError('Two roles share the same person')
    groups=[frames[i:i+8] for i in range(0,len(frames),8)]
    def locate(group):return invoke({'mode':'locate-replay-roles','references':refs,'frames':[clean_frame(f) for f in group]})
    responses=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for i,response in enumerate(pool.map(locate,groups)):
            responses.append(response)
            if progress:progress(i+1,len(groups))
    anchored={};usage={}
    for response in [intro]+responses:
        for k,v in response.get('usage',{}).items():
            if isinstance(v,(int,float)):usage[k]=usage.get(k,0)+v
    for group,response in zip(groups,responses):
        for row in response.get('frames',[]):
            if not isinstance(row,dict) or not isinstance(row.get('time'),(int,float)):continue
            f=min(group,key=lambda f:abs(f['time']-row['time']))
            if abs(f['time']-row['time'])>.04 or f['time'] in anchored:continue
            people=[];assigned=set()
            mappings=row.get('roles',{})
            if not isinstance(mappings,dict):continue
            chosen=[mappings.get(k,{}).get('detectionId') for k in ROLE_KEYS if isinstance(mappings.get(k),dict)]
            for role in roles:
                match=mappings.get(role['role']);match=match if isinstance(match,dict) else {}
                box=f['boxes'].get(match.get('detectionId'));confidence=match.get('confidence',0)
                if not box or not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not .7<=confidence<=1 or chosen.count(match.get('detectionId'))!=1:continue
                if match.get('detectionId') in assigned:continue
                assigned.add(match['detectionId'])
                people.append({k:box[k] for k in ['x','y','w','h']}|dict(trackId=role['id'],confidence=confidence,association=confidence,positionSource='vlm-selected-detection',detectorTrackId=box['trackId']))
            anchored[f['time']]=dict(time=f['time'],scene=f['scene'],cameraOffset=f['cameraOffset'],people=people)
    # Explicit empty frames prevent interpolation across an occlusion/rejected match.
    output=[anchored.get(f['time'],dict(time=f['time'],scene=f['scene'],cameraOffset=f['cameraOffset'],people=[])) for f in frames]
    reject_jumps(output)
    agreement=[]
    for role in roles:
        matches=[]
        for f in output:
            p=next((p for p in f['people'] if p['trackId']==role['id']),None)
            nearest=min(result['vision']['frames'],key=lambda q:abs(q['time']-f['time']))
            q=next((q for q in nearest['people'] if q['trackId']==role['sourceTrackId']),None)
            if p and q and abs(nearest['time']-f['time'])<.1:
                matches.append(math.hypot(p['x']+p['w']/2-q['x']-q['w']/2,p['y']+p['h']-q['y']-q['h'])<max(.03,p['h']*.25))
        agreement.append(len(matches)>=3 and sum(matches)/len(matches)>=.9)
    return dict(status='locked',schema='hidden-impact/role-lock-v1',source='bedrock-vlm-detector-grounding',eventId=event['id'] if event else 'visual-role-story',actorAction=str(intro.get('actorAction',''))[:600],actionWindow=intro.get('actionWindow'),
        roles=roles,frames=output,shotTime=shot_time,beneficiaryIsFinalShooter=True,usage=usage,
        sampleFps=2,scoringUnchanged=True,sourceRolesConfirmed=bool(event) and all(agreement),coverage={r['role']:round(sum(any(p['trackId']==r['id'] for p in f['people']) for f in output)/len(output),3) for r in roles})

def reject_jumps(frames):
    """Reject isolated identity switches using camera-relative feet, not shirt color."""
    for i in range(1,len(frames)-1):
        a,b,c=frames[i-1:i+2]
        if a['scene']!=b['scene'] or b['scene']!=c['scene']:continue
        for p in list(b['people']):
            before=next((q for q in a['people'] if q['trackId']==p['trackId']),None)
            after=next((q for q in c['people'] if q['trackId']==p['trackId']),None)
            if not before or not after:continue
            def foot(q,f):return (q['x']+q['w']/2-f['cameraOffset'][0],q['y']+q['h']-f['cameraOffset'][1])
            x,y=foot(p,b);ax,ay=foot(before,a);cx,cy=foot(after,c);unit=max(.05,p['h'])
            if math.hypot(x-(ax+cx)/2,y-(ay+cy)/2)>unit*.85 and math.hypot(cx-ax,cy-ay)<unit:
                b['people'].remove(p)


from role_model import visual_event


def event_role_hints(deep):
    """Select identities from supplied same-possession facts, not screen position."""
    official=deep.get('official') or {};shot=official.get('shot') or {};event=official.get('eventId')
    roster={str(p['playerId']):p for p in deep.get('roster',[])};shooter=roster.get(str(official.get('playerId')))
    if not shooter:return {}
    hints={'beneficiary':shooter};rows=deep.get('playByPlay') or []
    def clock(row):
        try:
            a,b=row['gameClock'].split(':');return int(a)*60+float(b)
        except (KeyError,ValueError,TypeError):return None
    end=clock(shot)
    if end is None:return hints
    same=[r for r in rows if r.get('gameId')==official.get('gameId') and r.get('period')==shot.get('period') and clock(r) is not None and 0<=clock(r)-end<=12]
    for row in reversed(same):
        candidate=roster.get(str(row.get('playerId')))
        if row.get('type') in ['offensive-rebound','assist'] and candidate and candidate['team']==shooter['team'] and candidate['playerId']!=shooter['playerId']:
            hints['actor']={**candidate,'action':row['type'],'gameClock':row['gameClock'],'source':row['source']};break
    foul=next((r for r in same if r.get('type')=='shooting-foul' and r.get('relatedEventId')==event),None)
    if foul and str(foul['playerId']) in roster:hints['defender']=roster[str(foul['playerId'])]
    for row in hints.values():row['uniform']=(deep.get('uniforms') or {}).get(row['team'],'')
    return hints


def resolve_known(result,raw_vision,dense,invoke,progress,hints):
    """One image time per call avoids mixing D labels from different frames."""
    duration=result['video']['duration'];frames=prepare_frames(dense,raw_vision,duration)
    roles=[dict(role=k,id='replay-'+k,sourceTrackId=None,name=hints[k]['team']+' '+hints[k]['jersey']+'号',jersey=hints[k]['jersey'],team=hints[k]['team'],sourcePlayerId=hints[k]['playerId']) for k in ROLE_KEYS]
    def locate(f):return invoke({'mode':'locate-known-roles','roleHints':hints,'frames':[clean_frame(f)]})
    output=[];usage={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for i,(f,response) in enumerate(zip(frames,pool.map(locate,frames))):
            mappings=response.get('roles') or {};people=[]
            chosen=[mappings.get(k,{}).get('detectionId') for k in ROLE_KEYS if isinstance(mappings.get(k),dict)]
            for role in roles:
                match=mappings.get(role['role']);match=match if isinstance(match,dict) else {};confidence=match.get('confidence',0)
                box=f['boxes'].get(match.get('detectionId'))
                if not box or not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not .75<=confidence<=1 or chosen.count(match.get('detectionId'))!=1:continue
                people.append({k:box[k] for k in ['x','y','w','h']}|dict(trackId=role['id'],confidence=confidence,association=confidence,positionSource='vlm-selected-detection',detectorTrackId=box['trackId']))
            output.append(dict(time=f['time'],scene=f['scene'],cameraOffset=f['cameraOffset'],people=people))
            for k,v in response.get('usage',{}).items():
                if isinstance(v,(int,float)):usage[k]=usage.get(k,0)+v
            if progress:progress(i+1,len(frames))
    reject_jumps(output)
    deep=result.get('deepData') or {};shot_time=(deep.get('alignment') or {}).get('shotVideoTime')
    if not isinstance(shot_time,(int,float)):shot_time=result.get('vision',{}).get('attackEnd') or duration*.75
    def seconds(clock):
        m,s=clock.split(':');return int(m)*60+float(s)
    delta=seconds(hints['actor']['gameClock'])-seconds(deep['official']['shot']['gameClock'])
    action_time=max(0,shot_time-delta)
    # Game-clock alignment provides a window, not per-frame trajectory ground truth.
    start=max(0,action_time-1);end=min(shot_time,max(start+.5,action_time+1))
    action=hints['actor']['name']+'在比赛时钟'+hints['actor']['gameClock']+('抢回进攻篮板' if hints['actor']['action']=='offensive-rebound' else '完成助攻')+'；随后'+hints['beneficiary']['name']+'完成最终出手。'
    return dict(status='locked',schema='hidden-impact/role-lock-v1',source='bedrock-vlm-detector-grounding',identitySource='official-play-by-play-and-roster',
        eventId='visual-role-story',actorAction=action,actionWindow={'start':start,'end':end},roles=roles,frames=output,shotTime=shot_time,
        beneficiaryIsFinalShooter=True,usage=usage,sampleFps=2,sourceRolesConfirmed=False,scoringUnchanged=True,
        coverage={r['role']:round(sum(any(p['trackId']==r['id'] for p in f['people']) for f in output)/max(1,len(output)),3) for r in roles})
