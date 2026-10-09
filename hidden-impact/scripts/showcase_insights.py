"""Build source-linked display insights without turning context into attribution.

Shot baselines use the complete returned shot list, not the seven selected videos.
Gravity keeps its raw signed values and season scope. No identity is inferred from
a jersey number, and none of these values changes the contribution score.
"""
import json
import math
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    ('OVERALL_GRAV', '总体引力'),
    ('ON_BALL_PERIM_GRAV', '持球 · 外线'),
    ('ON_BALL_INTERIOR_GRAV', '持球 · 内线'),
    ('OFF_BALL_PERIM_GRAV', '无球 · 外线'),
    ('OFF_BALL_INTERIOR_GRAV', '无球 · 内线'),
]


def finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def build_insights(source):
    official = source['official']
    player = source['playerShots']
    if str(player['playerId']) != str(official['playerId']) or player['gameId'] != official['gameId']:
        raise ValueError('Shot comparison must match the official game and shooter')
    shot = next(s for s in player['shotList'] if s['eventId'] == official['eventId'])
    if shot != official['shot']:
        raise ValueError('Catalog and shot source disagree')
    probability = shot['value']
    if not finite(probability) or not 0 <= probability <= 1:
        raise ValueError('Missing or invalid expected make probability')
    peers = [s for s in player['shotList'] if s['shotType'] == shot['shotType'] and finite(s.get('value')) and 0 <= s['value'] <= 1]
    baseline = mean(s['value'] for s in peers)
    points = {'3分投篮': 3, '2分投篮': 2}[shot['shotType']]
    gravity = source['gravityPlayers']
    shooter = next((p for p in gravity if str(p['PLAYERID']) == str(official['playerId'])), None)
    axes = []
    if shooter:
        team = [p for p in gravity if p.get('lightLogo') == shooter.get('lightLogo')]
        for key, label in FIELDS:
            values = [p[key] for p in gravity if finite(p.get(key))]
            teammates = [p[key] for p in team if finite(p.get(key))]
            value = shooter.get(key)
            axes.append({'key': key, 'label': label, 'value': value if finite(value) else None,
                         'teamMedian': median(teammates) if teammates else None,
                         'sampleCount': len(values),
                         'percentile': round(100 * sum(v <= value for v in values) / len(values), 1) if finite(value) and values else None})
    result = {
        'schema': 'hidden-impact/evidence-insights-v1',
        'sourceUrl': official['url'], 'gameId': official['gameId'], 'eventId': official['eventId'],
        'shooter': official['shooter'], 'period': shot['period'], 'gameClock': shot['gameClock'],
        'shot': {'probability': probability, 'points': points, 'made': shot['success'] == 1,
                 'expectedPoints': round(probability * points, 3), 'baseline': baseline,
                 'deltaPercentagePoints': round((probability - baseline) * 100, 3),
                 'sampleCount': len(peers), 'baselineScope': '同一球员、本场、同类出手，含当前出手',
                 'samples': [{'eventId': s['eventId'], 'probability': s['value'], 'made': s['success'] == 1} for s in peers]},
        'gravity': {'playerId': str(official['playerId']), 'player': official['shooter'],
                    'scope': source['gravityScope'], 'games': int(shooter['GP']) if shooter else None,
                    'axes': axes, 'comparison': '尼克斯榜单球员中位数',
                    'note': '阶段汇总引力用于解释球员特点；不代表这一回合的实时牵制。'},
        'interpretation': '44号的接应与分球，把进攻衔接到阿努诺比的外线出手。画面解释过程，出手质量刻画机会，命中记录确认结果。',
        'narrationSource': 'prepared-evidence-script',
    }
    pct = f'{probability * 100:.0f}%'
    diff = result['shot']['deltaPercentagePoints']
    comparison = f"比他本场同类出手均值{'高' if diff >= 0 else '低'} {abs(diff):.1f} 个百分点"
    result['cues'] = [
        {'start': 0, 'end': 8.1, 'seek': 7.5, 'phase': '接应', 'title': '先看机会出现之前',
         'text': '看金色的44号：他向接应位置移动，阿努诺比留在左侧外线。把视线从最后的投篮，移到配合的起点。', 'evidence': '画面 · 接应与站位', 'frame': 0},
        {'start': 8.1, 'end': 9.1, 'seek': 8.25, 'phase': '分球', 'title': '防守靠近，球向外线转移',
         'text': '44号接球推进，防守者向持球区域靠近；随后把球分向左侧。值得关注的是出球时机与外线队友的衔接。', 'evidence': '画面 · 推进到分球', 'frame': 2},
        {'start': 9.1, 'end': 10.8, 'seek': 9.5, 'phase': '出手', 'title': f'这次机会，预期命中率 {pct}',
         'text': f'阿努诺比接球出手。官方给这次投篮的预期命中率为 {pct}，{comparison}。这描述机会质量，不是44号个人创造的增益。', 'evidence': f'官方出手 · {pct} 预期命中率', 'frame': 3},
        {'start': 10.8, 'end': 14, 'seek': 11.1, 'phase': '命中', 'title': '得分记在队友，故事回到44号',
         'text': f'三分命中。记分牌留下了阿努诺比的得分，而回放让我们看见44号此前的接应、推进和分球。', 'evidence': f'官方结果 · +{points}' if shot['success'] == 1 else '官方结果 · 未命中', 'frame': 4},
    ]
    # Timed narration uses the same segment contract as the VLM runtime. The
    # prepared showcase keeps its origin; sharing a schema is not an inference.
    result['narration'] = {
        'schema': 'hidden-impact/timed-narration-v1',
        'source': 'prepared-evidence-script', 'modelInvoked': False,
        'segments': [
            {'start': 0, 'end': 2.6, 'title': '8号靠向底角，44号绕向外线',
             'text': '8号阿努诺比向左侧底角附近靠，44号从同侧向右侧外线绕出。两人的站位逐渐分开。',
             'frameTimes': [0, 1.5]},
            {'start': 2.6, 'end': 5.4, 'title': '一人在左侧，一人绕到右侧接应',
             'text': '8号保持左侧接应点；44号继续绕到右侧外线，转身看球，寻找下一次接应的位置。',
             'frameTimes': [3, 4.5]},
            {'start': 5.4, 'end': 8.1, 'title': '8号调整站位，44号迎球',
             'text': '8号向左侧外线调整，44号在右侧迎球。接到球后，44号向左前方推进，防守者也随之靠近。',
             'frameTimes': [6, 7.5]},
            *[{k: c[k] for k in ['start', 'end', 'title', 'text']} | {'frameTimes': [c['seek']]} for c in result['cues'][1:]],
        ],
    }
    return result


def attach_insights(manifest, root=ROOT):
    source = Path(root) / 'data/reference/showcase-deep-data.json'
    if source.exists():
        manifest['insights'] = build_insights(json.loads(source.read_text()))
    return manifest


if __name__ == '__main__':
    from showcase_payload import export_payload
    archive = json.loads((ROOT / 'data/review-archive/showcase-audit.json').read_text())
    export_payload(archive['analysis'], attach_insights(archive['showcase']), ROOT)
    print('Updated source-linked insights; video geometry unchanged.')
