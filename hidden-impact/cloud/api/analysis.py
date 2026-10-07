"""Snapshot-only, deterministic evidence index. No models, trajectories or outcome labels."""
import copy
import math
import statistics

VERSION = 'snapshot-v1.0'
WEIGHTS = [('attention', '近身防守关注', 45), ('separation', '远端防守分布', 35), ('spacing', '进攻站位间距', 20)]


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


def distance(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def validate_document(doc):
    if not isinstance(doc, dict) or doc.get('schemaVersion') != '1.0':
        raise ValueError('需要 schemaVersion 为 1.0 的快照文件。')
    if not isinstance(doc.get('game'), dict) or not isinstance(doc.get('shots'), list):
        raise ValueError('文件需要 game 对象和 shots 数组。')
    if not 1 <= len(doc['shots']) <= 500:
        raise ValueError('每个文件需要 1–500 个出手机会。')
    game = doc['game']
    for key in ['id', 'home', 'away', 'competition', 'date', 'source']:
        if not isinstance(game.get(key), str) or not 1 <= len(game[key]) <= 250:
            raise ValueError('game.' + key + ' 必须为非空短文本。')
    if game.get('coordinateSystem') != 'feet-center-attacking-negative-x':
        raise ValueError('坐标必须是英尺、球场中心原点、进攻篮筐在负 x 方向。')
    ids = set()
    for shot in doc['shots']:
        if not isinstance(shot, dict):
            raise ValueError('每个出手机会必须是对象。')
        for key in ['id', 'shooterId', 'offenseId', 'team', 'shooterName']:
            if not isinstance(shot.get(key), str) or not 1 <= len(shot[key]) <= 250:
                raise ValueError('shot.' + key + ' 必须为非空短文本。')
        if shot['id'] in ids:
            raise ValueError('shot.id 不可重复。')
        ids.add(shot['id'])
        if not isinstance(shot.get('period'), int) or isinstance(shot['period'], bool) or not 1 <= shot['period'] <= 20:
            raise ValueError('period 必须为 1–20 的整数。')
        if not number(shot.get('gameClock')) or not 0 <= shot['gameClock'] <= 720:
            raise ValueError('gameClock 必须为 0–720 秒。')
        if shot.get('outcome') not in ['made', 'missed', 'unknown']:
            raise ValueError('outcome 必须为 made / missed / unknown。')
        for key, maximum in [('shotQuality', 100), ('defenderDistance', 100)]:
            value = shot.get(key)
            if value is not None and (not number(value) or not 0 <= value <= maximum):
                raise ValueError(key + ' 数值超出范围。')
        players = shot.get('players', [])
        if not isinstance(players, list) or len(players) > 10:
            raise ValueError('players 应为最多 10 人的数组；无点位时使用空数组。')
        seen = set()
        for player in players:
            if not isinstance(player, dict):
                raise ValueError('球员点位必须是对象。')
            for key in ['id', 'teamId', 'name', 'jersey']:
                if not isinstance(player.get(key), str) or len(player[key]) > 250:
                    raise ValueError('player.' + key + ' 必须为短文本。')
            if not player['id'] or not player['teamId'] or player['id'] in seen:
                raise ValueError('球员 id 与 teamId 必须非空，同一快照不能有重复球员。')
            seen.add(player['id'])
            if not number(player.get('x')) or not number(player.get('y')) or abs(player['x']) > 60 or abs(player['y']) > 35:
                raise ValueError('球员坐标无效，检查单位和原点。')
            if player.get('detected') is not None and not isinstance(player['detected'], bool):
                raise ValueError('detected 应为 true / false / null。')
            error = player.get('errorFt')
            if error is not None and (not number(error) or error < 0 or error > 100):
                raise ValueError('errorFt 必须为非负英尺数值。')
    return doc


def analyze_shot(shot):
    result = copy.deepcopy(shot)
    result.pop('analysis', None)
    players = shot.get('players', [])
    offense = [p for p in players if p['teamId'] == shot['offenseId']]
    defense = [p for p in players if p['teamId'] != shot['offenseId']]
    shooter = next((p for p in offense if p['id'] == shot['shooterId']), None)
    analysis = {'version': VERSION, 'score': None, 'candidates': [], 'eligible': False,
                'quality': 'insufficient', 'qualityLabel': '数据不足', 'warnings': [],
                'narrativeMode': 'deterministic', 'gravityAvailable': False}
    result['analysis'] = analysis
    if len(offense) != 5 or len(defense) != 5 or len({p['teamId'] for p in defense}) != 1 or shooter is None:
        analysis['warnings'].append('缺少完整 5 对 5 出手点位，不计算无球贡献指数。')
        analysis['summary'] = '可以查看投篮指标；当前数据不足以对无球队员进行空间评分。'
        return result
    detected = sum(p.get('detected') is True for p in players)
    unknown = any(p.get('detected') is None or p.get('errorFt') is None for p in players)
    errors = [p['errorFt'] for p in players if p.get('errorFt') is not None]
    median_error = statistics.median(errors) if errors else None
    analysis['detectedCount'] = detected
    analysis['medianErrorFt'] = round(median_error, 2) if median_error is not None else None
    if unknown:
        quality, label = 'unknown', '点位质量未知'
    elif detected < 6 or median_error > 4:
        quality, label = 'low', '需谨慎解读'
    elif detected >= 9 and median_error <= 1.5:
        quality, label = 'high', '点位较可靠'
    else:
        quality, label = 'medium', '部分点位为估计'
    analysis.update(quality=quality, qualityLabel=label)
    if detected < 10 and not unknown:
        analysis['warnings'].append(f'{10-detected} 个球员点位来自数据方外推，虚线圆圈表示。')
    if unknown:
        analysis['warnings'].append('缺少检测标志或位置误差，不纳入默认精选。')
    if quality == 'low':
        analysis['warnings'].append('点位误差较大，不纳入默认精选。')
    # Each defender has one unit of soft association shared across all five attackers.
    # This is geometry, NOT a claim about who actually guards whom.
    associations = {}
    for defender in defense:
        values = [math.exp(-distance(p, defender) / 6.0) for p in offense]
        total = sum(values)
        associations[defender['id']] = {p['id']: v / total for p, v in zip(offense, values)}
    candidates = []
    for player in offense:
        if player['id'] == shooter['id']:
            continue
        links = []
        for defender in defense:
            d = distance(player, defender)
            ds = distance(shooter, defender)
            association = associations[defender['id']][player['id']]
            attention = association * math.exp(-d / 8.0)
            links.append({'defenderId': defender['id'], 'defenderName': defender['name'],
                          'distanceFt': round(d, 3), 'shooterDistanceFt': round(ds, 3),
                          'weight': attention, 'association': association})
        mass = sum(link['weight'] for link in links)
        separated = sum(link['weight'] * clamp((link['shooterDistanceFt'] - 6) / 18) for link in links)
        spacing = distance(player, shooter)
        # Smooth saturation avoids hard ties at 100 when several defenders cluster.
        attention_score = 1 - math.exp(-mass)
        values = {'attention': attention_score, 'separation': 1 - math.exp(-separated),
                  'spacing': clamp(spacing / 24) * attention_score}
        components = [{'id': key, 'label': label, 'weight': weight, 'value': round(values[key] * 100, 1),
                       'points': round(weight * values[key], 1)} for key, label, weight in WEIGHTS]
        score = round(sum(weight * values[key] for key, _, weight in WEIGHTS), 1)
        links.sort(key=lambda link: link['weight'], reverse=True)
        strongest = links[0]
        key_defender = next(p for p in defense if p['id'] == strongest['defenderId'])
        key_points = [player, shooter, key_defender]
        key_reliable = all(p.get('detected') is True and p.get('errorFt') is not None and p['errorFt'] <= 2 for p in key_points)
        candidates.append({'playerId': player['id'], 'name': player['name'], 'jersey': player['jersey'],
                           'score': score, 'components': components,
                           'keyPointsReliable': key_reliable,
                           'nearestDefenderFt': round(min(link['distanceFt'] for link in links), 2),
                           'shooterSpacingFt': round(spacing, 2), 'attentionMass': round(mass, 3),
                           'links': [{**link, 'weight': round(link['weight'], 4), 'association': round(link['association'], 4)} for link in links],
                           'evidence': [
                               {'label': '与出手者的间距', 'value': f'{spacing * .3048:.1f} m', 'type': 'computed'},
                               {'label': '最近防守人距离', 'value': f'{min(link["distanceFt"] for link in links) * .3048:.1f} m', 'type': 'computed'},
                               {'label': '主要空间关联防守人', 'value': strongest['defenderName'], 'type': 'estimate'},
                           ]})
    candidates.sort(key=lambda p: (-p['score'], p['playerId']))
    leader = candidates[0]
    analysis.update(candidates=candidates, score=leader['score'], eligible=quality in ['high', 'medium'] and leader['keyPointsReliable'])
    if not leader['keyPointsReliable']:
        analysis['warnings'].append('最高分候选的关键点位含外推、未知或较大误差，不纳入默认精选。')
    analysis['summary'] = (f'出手的是 {shot["shooterName"]}，值得关注的无球队员是 {leader["name"]}。'
                           f'出手瞬间，两人相距 {leader["shooterSpacingFt"] * .3048:.1f} 米，'
                           f'{leader["name"]} 身边最近的防守人距离为 {leader["nearestDefenderFt"] * .3048:.1f} 米。'
                           '这一站位关系支持空间牵制的解释，但不能证明他通过跑动创造了这次机会。')
    analysis['outcomeNote'] = ('投篮未命中不等于无球站位没有价值；命中结果不参与贡献指数计算。'
                               if shot['outcome'] == 'missed' else '命中结果不参与贡献指数计算，指数不等于得分贡献百分比。')
    return result


def analyze_document(doc):
    validate_document(doc)
    shots = [analyze_shot(s) for s in doc['shots']]
    return {'schemaVersion': '1.0', 'game': copy.deepcopy(doc['game']), 'shots': shots,
            'method': {'version': VERSION, 'usesTrajectories': False, 'usesModel': False,
                       'weights': WEIGHTS, 'scoreMeaning': '单次出手快照下的无球空间贡献启发式指数，不是因果效应。'},
            'stats': {'shots': len(shots), 'rankable': sum(s['analysis']['eligible'] for s in shots),
                      'missingSnapshots': sum(s['analysis']['score'] is None for s in shots)}}
