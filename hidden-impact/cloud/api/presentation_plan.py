"""Shared presentation interchange for analysis and source-bound editorial input.

Coordinates are image-space foot centres and person heights on a 640 x 360
reference image. Missing positions stay null; provenance never implies quality.
"""
import copy
import math

SCHEMA = 'hidden-impact/presentation-plan-v1'
ROLES = ('actor', 'beneficiary', 'defender')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(plan, duration):
    if plan.get('schema') != SCHEMA or not finite(duration) or duration <= 0:
        raise ValueError('Invalid presentation plan')
    if plan.get('coordinateSpace') != {'width': 640, 'height': 360, 'anchor': 'feet'}:
        raise ValueError('Unsupported plan coordinate space')
    if not plan.get('videoId') or not isinstance(plan.get('source'), str) or not plan['source']:
        raise ValueError('Plan requires video identity and source')
    roles = plan.get('roles', [])
    if [r.get('role') for r in roles] not in [[], list(ROLES)]:
        raise ValueError('Plan roles must be fixed and ordered')
    for role in roles:
        previous = -1
        if not role.get('anchors'):
            raise ValueError('Missing position anchors')
        for row in role['anchors']:
            if len(row) != 4 or not finite(row[0]) or not previous < row[0] <= duration:
                raise ValueError('Invalid anchor timeline')
            previous = row[0]
            if row[1:] == [None, None, None]:
                continue
            if not all(finite(n) for n in row[1:]) or row[3] <= 0:
                raise ValueError('Invalid position anchor')
    previous = 0
    for segment in plan.get('segments', []):
        if not all(finite(segment.get(k)) for k in ('start', 'end', 'seek')):
            raise ValueError('Invalid segment time')
        if not previous <= segment['start'] <= segment['seek'] < segment['end'] <= duration:
            raise ValueError('Overlapping or out-of-bounds story segment')
        if not all(isinstance(segment.get(k), str) and segment[k] for k in ('title', 'text')):
            raise ValueError('Missing story text')
        previous = segment['end']
    return plan


def from_result(result):
    """Export the actual generated roles/motion/story, without changing scores."""
    presentation = result['presentation']
    duration = result['video']['duration']
    review = result.get('presentationReview')
    if review:
        plan = copy.deepcopy(review)
        plan['schema'] = SCHEMA
    else:
        lock = result.get('visualRoleLock') or {}
        roles = []
        frames = result.get('presentationMotion', {}).get('frames', [])
        for key, role in zip(ROLES, presentation.get('roles', [])):
            identity = next((r for r in lock.get('roles', []) if r['id'] == role['id']), {})
            anchors = []
            for frame in frames:
                person = next((p for p in frame['people'] if p['trackId'] == role['id']), None)
                t = frame['time']
                if t >= duration:
                    continue
                if not person or person.get('offscreen'):
                    anchors.append([t, None, None, None])
                else:
                    anchors.append([t, (person['x'] + person['w']/2)*640,
                                    (person['y'] + person['h'])*360, person['h']*360])
            if not anchors:
                anchors = [[0, None, None, None]]
            # The end boundary carries no inferred location beyond the final frame.
            anchors.append([duration, None, None, None])
            roles.append(dict(role=key, id=role['id'], name=role['name'],
                              team=identity.get('team'), jersey=identity.get('jersey'),
                              playerId=identity.get('playerId'), anchors=anchors))
        segments = []
        narration = (presentation.get('insights') or {}).get('narration') or result.get('narration') or {}
        for s in narration.get('segments', []):
            start, end = s['start'], s['end']
            times = [t for t in s.get('frameTimes', []) if start <= t < end]
            segments.append(dict(start=start, end=end, seek=times[0] if times else (start+end)/2,
                                 title=s['title'], text=s['text']))
        plan = dict(schema=SCHEMA, videoId=result['video']['id'],
                    videoSha256=result['video'].get('sha256'), source='analysis-pipeline',
                    title=presentation.get('actionTitle', ''), summary=presentation.get('summary', ''),
                    roles=roles, segments=segments,
                    gravityContexts=copy.deepcopy((presentation.get('insights') or {}).get('gravityContexts', [])))
    plan['coordinateSpace'] = dict(width=640, height=360, anchor='feet')
    plan['provenance'] = dict(analysisModel=result.get('model'),
                              analysisModelInvoked=bool(result.get('modelInvoked')),
                              positionsSource=(review or result.get('visualRoleLock') or {}).get('source', 'vision-pipeline'),
                              narrationSource=result.get('narration', {}).get('source'),
                              narrationModelInvoked=bool(result.get('narration', {}).get('modelInvoked')))
    return validate(plan, duration)


def attach(result):
    result['presentationPlan'] = from_result(result)
    return result['presentationPlan']
