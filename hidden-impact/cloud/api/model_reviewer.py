"""Evidence-based Reviewer: fresh VLM localization and narration, then a render plan.

Never imports reference annotations or changes the original analysis/score.
Artifacts from this module describe calls made during this review only.
"""
import copy
import hashlib
import json
import re
from datetime import datetime, timezone

from presentation_plan import SCHEMA, validate

SOURCE = 'bedrock-vlm-review'


def validate_source(source):
    if not source.get('modelInvoked') or not source.get('vision', {}).get('frames'):
        raise ValueError('Reviewer requires an actual analysis with visual evidence')
    if source.get('presentationReview') or source.get('modelReview'):
        raise ValueError('Review the original analysis, not a previously edited result')
    markers = json.dumps({k:source.get(k) for k in ['events','vision','visualRoleLock','narration']})
    if any(word in markers for word in ['human-reviewed', 'human-video-review', 'manual-annotation']):
        raise ValueError('Automatic Reviewer requires unedited model evidence')
    return source


def run(source, dense_frames, invoke, sha256, source_ref, progress=None):
    validate_source(source)
    if not re.fullmatch('[a-f0-9]{64}', sha256 or ''):
        raise ValueError('Reviewer requires the source video SHA-256')
    current = copy.deepcopy(source)
    for key in ['presentation','presentationMotion','presentationPlan','tacticalReplay','renderError','thumbnails']:
        current.pop(key, None)
    receipts = []
    usage = {}

    def call(document):
        value = invoke(document)
        # This gate distinguishes a model response from a supplied annotation file.
        if value.get('modelInvoked') is not True or not value.get('model'):
            raise ValueError('Reviewer received no model invocation receipt')
        receipts.append({'mode':document['mode'], 'model':value['model'],
                         'requestId':value.get('requestId'), 'usage':value.get('usage', {}),
                         'runtimeAttempts':value.get('runtimeAttempts',1)})
        for key, n in value.get('usage', {}).items():
            if isinstance(n, (int,float)) and not isinstance(n,bool):usage[key]=usage.get(key,0)+n
        return value

    from role_localization import resolve
    lock = resolve(current, current['vision'], dense_frames, call, progress)
    if lock.get('status') != 'locked' or len(lock.get('roles', [])) != 3:
        raise ValueError('Reviewer could not establish three fixed identities')
    if any(not r.get('team') or not re.fullmatch(r'\d{1,2}', str(r.get('jersey',''))) for r in lock['roles']):
        raise ValueError('Reviewer could not confirm team and jersey identities')
    current['visualRoleLock'] = lock
    from narration import request_for_result
    # 18 context frames, plus the aligned release, are grouped into local windows
    # by the existing narrator. Localization independently used two frames/second.
    selected = {round(i*(len(dense_frames)-1)/17) for i in range(18)}
    shot = lock.get('shotTime')
    if isinstance(shot,(float,int)):
        selected.add(min(range(len(dense_frames)),key=lambda i:abs(dense_frames[i]['time']-shot)))
    frames = [dense_frames[i] for i in sorted(selected)]
    payload = request_for_result(current, frames)
    payload['reviewDraft'] = copy.deepcopy(source.get('narration', {}).get('segments', []))
    current['narration'] = call(payload)
    roles, references = [], []
    for role in lock['roles']:
        anchors, candidates = [], []
        for f in lock['frames']:
            person = next((p for p in f['people'] if p['trackId']==role['id']),None)
            if person:
                x=(person['x']+person['w']/2)*640;y=(person['y']+person['h'])*360;h=person['h']*360
                # Same drawable bounds as the editorial input; reject, don't clamp.
                if not (0<=x<=640 and 0<=y<=360 and 10<=h<=180):person=None
            anchors.append([f['time'],x,y,h] if person else [f['time'],None,None,None])
            if person:candidates.append((f,person))
        if not candidates:raise ValueError('No grounded reference for '+role['role'])
        if anchors[0][0]>0:anchors.insert(0,[0,None,None,None])
        anchors.append([source['video']['duration'],None,None,None])
        roles.append(dict(role=role['role'],team=role['team'],jersey=role['jersey'],
                          playerId=role.get('sourcePlayerId'),anchors=anchors))
        f,p=max(candidates,key=lambda pair:pair[1].get('confidence',0))
        references.append(dict(role=role['role'],team=role['team'],jersey=role['jersey'],
                               time=f['time'],box={k:p[k] for k in ['x','y','w','h']},
                               confidence=p.get('confidence'),detectorTrackId=p.get('detectorTrackId')))
    segments=[]
    for s in current['narration']['segments']:
        times=[t for t in s['frameTimes'] if s['start']<=t<s['end']]
        if not times:raise ValueError('Reviewed story lacks an in-window evidence frame')
        segments.append(dict(start=s['start'],end=s['end'],seek=times[len(times)//2],title=s['title'],text=s['text'],
                             factRefs=s.get('factRefs',[])))
    plan=dict(schema=SCHEMA,source=SOURCE,videoId=source['video']['id'],videoSha256=sha256,
              coordinateSpace=dict(width=640,height=360,anchor='feet'),title=segments[0]['title'],
              summary=lock.get('actorAction',''),roles=roles,segments=segments,gravityContexts=[])
    validate(plan,source['video']['duration'])
    report=dict(schema='hidden-impact/model-review-v1',source=SOURCE,modelInvoked=True,
                model=current['narration']['model'],createdAt=datetime.now(timezone.utc).isoformat(),
                sourceReference=source_ref,videoSha256=sha256,coverage=lock.get('coverage'),
                identitySource=lock.get('identitySource',lock.get('source')),calls=receipts,usage=usage,
                scoringUnchanged=True,planSha256=hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    return plan, report, dict(schema='hidden-impact/role-references-v1',source=SOURCE,
                              videoId=source['video']['id'],videoSha256=sha256,roles=references)
