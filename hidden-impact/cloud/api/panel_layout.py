"""Stable broadcast card placement from player and nameplate geometry."""

def nameplates(people, roles, width, height, measure, obstacle=None):
    occupied = []
    layouts = []
    for p in people:
        if p.get('offscreen'):
            continue
        text = roles[p['trackId']]['displayName'].replace('尼克斯 ', '').replace('马刺 ', '')
        length = measure(text) + 28
        x = (p['x'] + p['w'] / 2) * width
        top = max(48, p['y'] * height + 44 - 35)
        left = max(8, min(width - length - 8, x - length / 2))
        for _ in range(len(people) + 2):
            if obstacle and overlap((left, top, left + length, top + 29), obstacle):
                # Keep the leader attached to the player while shifting the
                # nameplate beside a fixed data card, rather than under it.
                if obstacle[0] < width / 2:
                    left = max(left, obstacle[2] + 8)
                else:
                    left = min(left, obstacle[0] - length - 8)
            if any(left < rr + 8 and left + length > ll - 8 and top < bb + 7 and top + 29 > tt - 7
                   for ll, tt, rr, bb in occupied) and top > 83:
                top -= 35
            else:
                break
        box = (left, top, left + length, top + 29)
        occupied.append(box)
        layouts.append((p, text, x, box))
    return layouts


def overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def choose_position(samples, width=960, card_width=312, card_height=202):
    """Minimize worst obstruction first, keeping one position for the chapter.

    Each sample contains (protected rectangle, priority) pairs. Checking the
    worst frame prevents a quiet later sequence from hiding an early collision.
    Only top corners are eligible: the court floor and scorebug stay clear.
    """
    candidates = [(16, 48), (width - card_width - 16, 48)]
    def cost(position):
        x, y = position
        panel = (x - 2, y - 2, x + card_width + 2, y + card_height + 2)
        collisions = [sum(overlap(panel, box) * priority for box, priority in sample) for sample in samples]
        return (max(collisions, default=0), sum(collisions))
    return min(candidates, key=cost)


def card_position(motion, manifest, kind, duration, height, measure):
    from broadcast import card_at, actor_card
    from story_direction import build_direction, phase_at
    direction = manifest.get('direction') or build_direction(manifest, duration)
    roles = {r['id']: r for r in manifest['roles']}
    beneficiary = manifest['roles'][1]['id'] if len(manifest['roles']) > 1 else None
    samples = []
    fps = motion['fps']
    # Quarter-second samples include chapter boundaries and brief crossings.
    for index in range(0, len(motion['frames']), max(1, round(fps / 4))):
        t = index / fps
        phase = phase_at(direction, t)
        if phase == 1:
            continue
        card = card_at(manifest['insights'], t, duration)
        if phase == 0 and direction.get('focusWindow') and manifest['insights'].get('actorProfile'):
            card = actor_card(manifest['insights']['actorProfile'], t, direction['focusWindow'][0]) or card
        if not card or card['kind'] != kind:
            continue
        protected = []
        for p, _, _, label in nameplates(motion['frames'][index]['people'], roles, 960, height, measure):
            priority = 3 if p['trackId'] == beneficiary else 1
            body = (p['x'] * 960 - 8, p['y'] * height + 40,
                    (p['x'] + p['w']) * 960 + 8, (p['y'] + p['h']) * height + 48)
            protected.extend([(body, priority), (label, priority)])
        samples.append(protected)
    return choose_position(samples, card_width=296 if kind == 'shot' else 312, card_height=160 if kind == 'shot' else 202)
