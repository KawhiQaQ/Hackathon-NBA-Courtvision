import copy,json,sys,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from reference_reviewer import select,apply
from reviewed_presentation import build_motion


class ReferenceReviewerTests(unittest.TestCase):
    def setUp(self):
        self.plan=json.loads((ROOT/'data/reference/dallas-exam-presentation-review.json').read_text())
        official=json.loads((ROOT.parent/'double.companion.json').read_text())['shotContext']
        self.profile=dict(schema='hidden-impact/reference-profile-v1',id='exam-test',plan=self.plan,
                          binding={k:official[k] for k in ['gameId','eventId','playerId','shot']})
        self.source=dict(video=dict(id='upload-new-id',title='renamed.mp4',duration=23.78),
                         deepData={'official':official},events=[],players=[],job='new-job',
                         model='actual-analysis-model',modelInvoked=True)
        self.sha=self.plan['videoSha256']

    def test_identical_bytes_match_after_rename_and_upload_id_changes(self):
        selected=select(self.profile,self.sha,self.source['video'],self.source['deepData'])
        self.assertEqual(selected['plan']['videoId'],'upload-new-id')
        self.assertEqual(selected['plan']['roles'],self.plan['roles'])
        self.assertEqual(selected['plan']['segments'],self.plan['segments'])
        self.assertEqual(self.plan['videoId'],'dallas-exam')
        self.assertIsNone(select(self.profile,'0'*64,self.source['video'],self.source['deepData']))

    def test_wrong_shooter_shot_or_duration_cannot_use_reference(self):
        for field,value in [('playerId','wrong'),('gameId','wrong'),('eventId',270)]:
            deep=copy.deepcopy(self.source['deepData']);deep['official'][field]=value
            self.assertIsNone(select(self.profile,self.sha,self.source['video'],deep))
        deep=copy.deepcopy(self.source['deepData']);deep['official']['shot']['value']=.99
        self.assertIsNone(select(self.profile,self.sha,self.source['video'],deep))
        self.assertIsNone(select(self.profile,self.sha,{**self.source['video'],'duration':20},self.source['deepData']))

    def test_browser_rounding_changes_only_end_boundary(self):
        video={**self.source['video'],'duration':23.781}
        profile=select(self.profile,self.sha,video,self.source['deepData'])
        self.assertEqual(profile['plan']['roles'][0]['anchors'][:-1],self.plan['roles'][0]['anchors'][:-1])
        self.assertEqual(profile['plan']['segments'][-1]['end'],23.781)

    def test_exact_motion_parity_with_showcase_and_truthful_reference_source(self):
        before=copy.deepcopy(self.source)
        profile=select(self.profile,self.sha,self.source['video'],self.source['deepData'])
        result,files=apply(self.source,profile,self.sha,'jobs/new-job/analysis.json')
        self.assertEqual(self.source,before)
        self.assertEqual(result['presentationMotion'],build_motion(self.plan,23.78))
        self.assertEqual([r['name'] for r in result['presentation']['roles']],['独行侠 7号','独行侠 00号','火箭 10号'])
        self.assertEqual(result['events'],self.source['events'])
        self.assertFalse(result['narration']['modelInvoked'])
        self.assertFalse(files['review-report.json']['modelInvoked'])
        self.assertEqual(files['review.json']['source'],'human-reviewed-video')
        self.assertEqual(files['references.json']['source'],'human-reviewed-video')
        self.assertEqual(result['referenceReview']['method'],'reference-calibration')
        self.assertEqual(result['presentationReview']['sourceArtifact'],'jobs/new-job/analysis.json')
