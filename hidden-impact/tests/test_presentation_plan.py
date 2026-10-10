import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'cloud/api'))
from presentation_plan import SCHEMA, validate
from presentation import build
from reviewed_presentation import build as build_review
from test_presentation import verified


class PresentationPlanTests(unittest.TestCase):
    def test_automatic_analysis_exports_actual_positions_and_story(self):
        result = verified()
        original = copy.deepcopy(result)
        build(result)
        plan = result['presentationPlan']
        self.assertEqual(plan['schema'], SCHEMA)
        self.assertEqual([r['role'] for r in plan['roles']], ['actor', 'beneficiary', 'defender'])
        p = result['presentationMotion']['frames'][0]['people'][0]
        anchor = plan['roles'][0]['anchors'][0]
        self.assertAlmostEqual(anchor[1], (p['x']+p['w']/2)*640)
        self.assertAlmostEqual(anchor[2], (p['y']+p['h'])*360)
        self.assertEqual(plan['segments'][0]['text'], original['narration']['segments'][0]['text'])
        self.assertEqual(result['events'], original['events'])
        self.assertEqual(plan['source'], 'analysis-pipeline')
        self.assertFalse(plan['provenance']['narrationModelInvoked'])
        validate(json.loads(json.dumps(plan)), result['video']['duration'])

    def test_reference_inputs_use_same_contract_and_keep_source(self):
        for name, duration, video in [('dallas-presentation-review.json',21.55,'dallas-practice'),
                                      ('dallas-exam-presentation-review.json',23.78,'dallas-exam')]:
            plan = json.loads((ROOT/'data/reference'/name).read_text())
            validate(plan, duration)
            result = build_review(dict(video={'id':video,'duration':duration}, events=[],players=[]),
                                  plan, plan['videoSha256'], 'source-job')
            self.assertEqual(result['presentationPlan']['schema'], SCHEMA)
            self.assertEqual(result['presentationPlan']['source'], 'human-reviewed-video')
            self.assertEqual(result['presentationPlan']['roles'], plan['roles'])
            self.assertFalse(result['presentationPlan']['provenance']['narrationModelInvoked'])

    def test_invalid_timeline_and_position_rejected(self):
        result = verified(); build(result)
        for mutation in ('position','timeline','segment'):
            plan = copy.deepcopy(result['presentationPlan'])
            if mutation == 'position': plan['roles'][0]['anchors'][0][1] = float('nan')
            elif mutation == 'timeline': plan['roles'][0]['anchors'][1][0] = -1
            else: plan['segments'][0]['end'] = 999
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(plan,result['video']['duration'])
