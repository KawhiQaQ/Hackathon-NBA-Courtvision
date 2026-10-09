"""Evidence integrity: no sample cherry-picking, identity guessing or scope mixing."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from showcase_insights import build_insights


class InsightTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((ROOT / 'data/reference/showcase-deep-data.json').read_text())

    def test_same_game_same_shooter_same_shot_type(self):
        d = build_insights(self.source)
        self.assertEqual(d['shot']['sampleCount'], 9)
        self.assertAlmostEqual(d['shot']['baseline'], 0.39022222222222225)
        self.assertEqual(d['shot']['expectedPoints'], 1.26)
        self.assertEqual(d['shot']['deltaPercentagePoints'], 2.978)
        self.assertEqual(d['shot']['probability'], .42)
        self.assertTrue(d['shot']['made'])
        # Adding a two-pointer must not contaminate the three-point comparison.
        self.source['playerShots']['shotList'].append({'eventId':999, 'shotType':'2分投篮', 'value':1, 'success':1})
        self.assertEqual(build_insights(self.source)['shot'], d['shot'])

    def test_unmatched_identity_and_disagreeing_shot_rejected(self):
        for field in ['gameId','playerId']:
            s = copy.deepcopy(self.source)
            s['playerShots'][field] = 'wrong'
            with self.assertRaises(ValueError): build_insights(s)
        self.source['official']['shot']['value'] = .99
        with self.assertRaises(ValueError): build_insights(self.source)

    def test_gravity_signed_scoped_and_missing_is_not_zero(self):
        d = build_insights(self.source)
        axes = {a['key']: a for a in d['gravity']['axes']}
        self.assertEqual(len(axes), 5)
        self.assertEqual(axes['ON_BALL_PERIM_GRAV']['value'], -2.408)
        self.assertEqual(axes['OFF_BALL_PERIM_GRAV']['value'], 6.472)
        self.assertEqual(d['gravity']['games'], 17)
        self.assertNotIn('score', d)
        for p in self.source['gravityPlayers']: p['OFF_BALL_PERIM_GRAV'] = None
        a = build_insights(self.source)['gravity']['axes'][3]
        self.assertIsNone(a['value']);self.assertIsNone(a['percentile']);self.assertIsNone(a['teamMedian'])

    def test_cues_cover_full_clip_without_gaps(self):
        cues = build_insights(self.source)['cues']
        self.assertEqual(cues[0]['start'], 0)
        self.assertGreaterEqual(cues[-1]['end'], 13.49)
        for a, b in zip(cues, cues[1:]): self.assertEqual(a['end'], b['start'])
        for c in cues: self.assertTrue(c['start'] <= c['seek'] < c['end'])


if __name__ == '__main__': unittest.main()
