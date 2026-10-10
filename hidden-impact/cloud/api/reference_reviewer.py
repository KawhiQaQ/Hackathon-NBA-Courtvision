"""Apply an explicitly calibrated reference only to the identical source video.

This is deterministic reuse of source-bound annotations, not a new VLM verdict.
Raw analysis and the reference's actual provenance remain available separately.
"""
import copy
import hashlib
import json
from datetime import datetime, timezone


def select(profile, sha, video, deep):
    if not profile or profile.get('schema') != 'hidden-impact/reference-profile-v1':
        return None
    plan = profile['plan']
    if sha != plan.get('videoSha256'):
        return None
    duration = plan['segments'][-1]['end']
    if abs(video['duration']-duration) > .04:
        return None
    official = (deep or {}).get('official') or {}
    binding = profile['binding']
    for field in ['gameId','eventId','playerId']:
        if str(official.get(field)) != str(binding[field]):
            return None
    if any((official.get('shot') or {}).get(k) != v for k,v in binding['shot'].items()):
        return None
    beneficiary = plan['roles'][1]
    if str(beneficiary.get('playerId')) != str(official['playerId']):
        raise ValueError('Calibrated beneficiary does not match the final shooter')
    selected = copy.deepcopy(profile)
    selected['plan']['videoId'] = video['id']
    # Browser metadata may round the identical file's duration by milliseconds.
    selected['plan']['segments'][-1]['end'] = video['duration']
    for role in selected['plan']['roles']:
        role['anchors'][-1][0] = video['duration']
    from reviewed_presentation import validate
    validate(selected['plan'], {'video':video}, sha)
    return selected


def apply(source, profile, sha, source_ref):
    from reviewed_presentation import build
    plan = copy.deepcopy(profile['plan'])
    report = dict(schema='hidden-impact/reference-review-v1',
                  method='reference-calibration', source=plan['source'], modelInvoked=False,
                  profileId=profile['id'], sourceReference=source_ref, videoSha256=sha,
                  createdAt=datetime.now(timezone.utc).isoformat(),
                  planSha256=hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                  scoringUnchanged=True)
    references = []
    for role in plan['roles']:
        anchors = [a for a in role['anchors'] if a[1] is not None]
        a = anchors[len(anchors)//2]
        t,x,y,h = a; w = h*.48
        references.append(dict(role=role['role'],team=role['team'],jersey=role['jersey'],
                               playerId=role.get('playerId'),time=t,
                               box=dict(x=(x-w/2)/640,y=(y-h)/360,w=w/640,h=h/360)))
    refs = dict(schema='hidden-impact/role-references-v1', source=plan['source'],
                method='reference-calibration', videoId=source['video']['id'],videoSha256=sha,roles=references)
    reviewed = build(source,plan,sha,source.get('job') or source_ref)
    reviewed['referenceReview'] = report
    reviewed['presentationReview']['sourceArtifact'] = source_ref
    reviewed['mode'] = 'reference-reviewed-presentation'
    return reviewed, {'review.json':plan,'references.json':refs,'review-report.json':report}
