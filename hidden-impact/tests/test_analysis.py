import copy
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from analysis import analyze_document, analyze_shot, validate_document


class SnapshotAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((ROOT / 'data/normalized/114243.json').read_text())
        cls.shot = next(s for s in cls.document['shots'] if len(s['players']) == 10)

    def test_outcome_and_shot_quality_do_not_change_contribution(self):
        before = analyze_shot(self.shot)['analysis']
        changed = copy.deepcopy(self.shot)
        changed['outcome'] = 'made' if changed['outcome'] == 'missed' else 'missed'
        changed['shotQuality'] = 100
        changed['points'] = 3
        after = analyze_shot(changed)['analysis']
        self.assertEqual(before['candidates'], after['candidates'])

    def test_rotation_preserves_index(self):
        rotated = copy.deepcopy(self.shot)
        for player in rotated['players']:
            player['x'] *= -1
            player['y'] *= -1
        self.assertEqual(analyze_shot(self.shot)['analysis']['candidates'],
                         analyze_shot(rotated)['analysis']['candidates'])

    def test_missing_snapshot_abstains_instead_of_zero(self):
        changed = copy.deepcopy(self.shot)
        changed['players'] = []
        result = analyze_shot(changed)['analysis']
        self.assertIsNone(result['score'])
        self.assertFalse(result['eligible'])
        self.assertEqual([], result['candidates'])

    def test_incomplete_team_abstains(self):
        changed = copy.deepcopy(self.shot)
        changed['players'].pop()
        self.assertIsNone(analyze_shot(changed)['analysis']['score'])

    def test_unknown_or_unreliable_quality_not_curated(self):
        for error in [None, 8]:
            shot = copy.deepcopy(self.shot)
            for player in shot['players']:
                player['errorFt'] = error
            self.assertFalse(analyze_shot(shot)['analysis']['eligible'])

    def test_unreliable_leader_not_curated_even_when_team_median_is_good(self):
        shot = copy.deepcopy(self.shot)
        for player in shot['players']:
            player['detected'] = True
            player['errorFt'] = 1
        leader_id = analyze_shot(shot)['analysis']['candidates'][0]['playerId']
        next(p for p in shot['players'] if p['id'] == leader_id)['detected'] = False
        self.assertFalse(analyze_shot(shot)['analysis']['eligible'])

    def test_invalid_units_nan_and_duplicate_ids_rejected(self):
        doc = copy.deepcopy(self.document)
        doc['game']['coordinateSystem'] = 'meters'
        with self.assertRaises(ValueError):
            validate_document(doc)
        for field, value in [('x', math.nan), ('errorFt', -1), ('detected', 'yes')]:
            doc = copy.deepcopy(self.document)
            doc['shots'][0]['players'][0][field] = value
            with self.assertRaises(ValueError):
                validate_document(doc)
        doc = copy.deepcopy(self.document)
        doc['shots'][0]['players'][1]['id'] = doc['shots'][0]['players'][0]['id']
        with self.assertRaises(ValueError):
            validate_document(doc)

    def test_all_real_samples_respect_bounds_and_exclude_shooter(self):
        count = 0
        for path in (ROOT / 'data/normalized').glob('*.json'):
            analyzed = analyze_document(json.loads(path.read_text()))
            for shot in analyzed['shots']:
                count += 1
                candidates = shot['analysis']['candidates']
                self.assertNotIn(shot['shooterId'], [c['playerId'] for c in candidates])
                if candidates:
                    self.assertEqual(len(candidates), 4)
                    self.assertEqual(shot['analysis']['score'], max(c['score'] for c in candidates))
                for c in candidates:
                    self.assertTrue(0 <= c['score'] <= 100)
                    self.assertAlmostEqual(c['score'], sum(p['points'] for p in c['components']), delta=.21)
        self.assertGreater(count, 250)


if __name__ == '__main__':
    unittest.main()
