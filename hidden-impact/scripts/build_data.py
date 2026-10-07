"""Prepare a reproducible shot-snapshot fixture, then run the independent analyzer.

The source position archive is read once to retain ONLY exact release frames.
No preceding/following frames, speeds, paths, event annotations or outcomes are
used by the contribution index. Official inputs can replace this adapter.
"""
import argparse
import gzip
import hashlib
import json
import math
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from analysis import analyze_document

COMMIT = '4bbed2e35e8fdd2cf083e8c8b280b3e5381a2c66'
GAMES = ['114243', '184439']
RAW = ROOT / 'data' / 'raw'
SOURCE = 'https://github.com/SkillCorner/opendata-basketball'


def download(game):
    RAW.mkdir(parents=True, exist_ok=True)
    for suffix in ['game_data.json', 'dynamic_events.json', 'tracking_data.jsonl.gz']:
        path = f'data/matches/{game}/{game}_{suffix}'
        dest = RAW / f'{game}_{suffix}'
        if dest.exists():
            continue
        url = f'https://raw.githubusercontent.com/SkillCorner/opendata-basketball/{COMMIT}/{path}'
        expected = None
        if suffix.endswith('.gz'):
            pointer = urllib.request.urlopen(url, timeout=60).read().decode()
            expected = next(line.split('sha256:')[1] for line in pointer.splitlines() if line.startswith('oid '))
            url = f'https://media.githubusercontent.com/media/SkillCorner/opendata-basketball/{COMMIT}/{path}'
        temp = dest.with_suffix(dest.suffix + '.part')
        with urllib.request.urlopen(url, timeout=90) as response, temp.open('wb') as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        if expected and hashlib.sha256(temp.read_bytes()).hexdigest() != expected:
            raise ValueError('Source checksum mismatch: ' + path)
        temp.replace(dest)


def normalize(game):
    meta = json.loads((RAW / f'{game}_game_data.json').read_text())
    events = json.loads((RAW / f'{game}_dynamic_events.json').read_text())
    shots = events['shots']
    needed = {s['startFrame'] for s in shots}
    frames = {}
    with gzip.open(RAW / f'{game}_tracking_data.jsonl.gz', 'rt') as source:
        for line in source:
            frame = json.loads(line)
            if frame['frameIdx'] in needed:
                frames[frame['frameIdx']] = frame
    # Verify each team's orientation in each period against supplied release locations.
    alignment = defaultdict(list)
    for s in shots:
        frame = frames.get(s['startFrame'], {})
        p = next((p for p in frame.get('homePlayers', []) + frame.get('awayPlayers', []) if p['playerId'] == s['shooterId']), None)
        if p and s.get('location'):
            errors = [(math.dist([sign * p['xyz'][0], sign * p['xyz'][1]], s['location']), sign) for sign in [1, -1]]
            error, sign = min(errors)
            if error <= 3:
                alignment[(s['offTeamId'], s['period'])].append(sign)
    orientations = {k: 1 if sum(v) >= 0 else -1 for k, v in alignment.items()}
    rosters = {}
    teams = {}
    for side in ['homeTeam', 'awayTeam']:
        team = meta[side]
        teams[team['teamId']] = team['teamName']
        for p in team['players']:
            rosters[p['playerId']] = {'name': p['firstName'] + ' ' + p['lastName'], 'jersey': p['jersey']}
    output = []
    for s in shots:
        frame = frames.get(s['startFrame'])
        sign = orientations.get((s['offTeamId'], s['period']))
        players = []
        if frame and sign:
            for key, side in [('homePlayers', 'homeTeam'), ('awayPlayers', 'awayTeam')]:
                for p in frame[key]:
                    roster = rosters.get(p['playerId'], {'name': str(p['playerId']), 'jersey': str(p.get('jersey', '?'))})
                    players.append({'id': str(p['playerId']), 'teamId': str(meta[side]['teamId']), **roster,
                                    'x': round(sign * p['xyz'][0], 5), 'y': round(sign * p['xyz'][1], 5),
                                    'detected': bool(p['isDetected']),
                                    'errorFt': round(p['predError'], 4) if 0 <= p['predError'] <= 100 else None,
                                    'sourceErrorFt': p['predError']})
            shooter = next((p for p in players if p['id'] == str(s['shooterId'])), None)
            if shooter and s.get('location') and math.dist([shooter['x'], shooter['y']], s['location']) > 3:
                players = []  # No silent misalignment or fabricated fallback position.
        output.append({'id': s['id'], 'chanceId': s['chanceId'], 'possessionId': s['possessionId'],
                       'period': s['period'], 'gameClock': round(s['startGameClock'], 2),
                       'videoTimeMs': s['startWallClock'], 'frame': s['startFrame'],
                       'shooterId': str(s['shooterId']), 'shooterName': rosters[s['shooterId']]['name'],
                       'offenseId': str(s['offTeamId']), 'team': teams[s['offTeamId']],
                       'outcome': 'made' if s['outcome'] else 'missed', 'points': 3 if s['three'] else 2,
                       'shotQuality': s.get('shotQuality'), 'defenderDistance': s.get('closestDefDist'),
                       'contestLevel': s.get('contestLevel'), 'shotType': s.get('complexShotType'),
                       'fouled': s.get('fouled', False), 'players': players,
                       'snapshotSource': 'SkillCorner exact release frame; no trajectory input',
                       'sourceLocation': s.get('location')})
    return {'schemaVersion': '1.0', 'game': {
        'id': game, 'home': meta['homeTeam']['teamName'], 'away': meta['awayTeam']['teamName'],
        'competition': meta['competitionName'], 'date': meta['date'][:10], 'season': meta['seasonName'],
        'source': 'SkillCorner Open Data Basketball', 'sourceUrl': SOURCE, 'sourceCommit': COMMIT,
        'coordinateSystem': 'feet-center-attacking-negative-x', 'videoAvailable': False,
        'note': '西班牙 ACB 真实数据；不是 NBA 官方比赛数据。只保留出手一帧点位。'}, 'shots': output}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--rebuild-snapshots', action='store_true')
    args = parser.parse_args()
    catalog = []
    for game in GAMES:
        normalized = ROOT / 'data' / 'normalized' / f'{game}.json'
        if args.download:
            download(game)
        if args.rebuild_snapshots or not normalized.exists():
            document = normalize(game)
            write_json(normalized, document)
        else:
            document = json.loads(normalized.read_text())
        analyzed = analyze_document(document)
        write_json(ROOT / 'web' / 'data' / f'{game}.json', analyzed)
        catalog.append({**analyzed['game'], **analyzed['stats'], 'file': f'data/{game}.json'})
        print(game, analyzed['stats'])
    write_json(ROOT / 'web' / 'data' / 'catalog.json', catalog)


if __name__ == '__main__':
    main()
