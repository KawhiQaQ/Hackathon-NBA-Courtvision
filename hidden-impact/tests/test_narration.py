import base64
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cloud/agent'))
from narration import normalize_segments, request_for_result
from logic import analyze


class Client:
    def __init__(self, value, stop='end_turn'):
        self.value, self.stop, self.calls = value, stop, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {'output': {'message': {'content': [{'text': json.dumps(self.value)}]}},
                'stopReason': self.stop, 'usage': {'inputTokens': 10, 'outputTokens': 20}}


class NarrationTests(unittest.TestCase):
    def setUp(self):
        self.payload = {'mode': 'narrate-video', 'video': {'id': 'test', 'title': 'test', 'duration': 6},
                        'frames': [{'time': t, 'image': base64.b64encode(b'\xff\xd8test').decode()} for t in [0, 1.5, 3, 4.5, 6]]}
        self.raw = {'segments': [
            {'start': 0, 'end': 3, 'title': '向外线移动', 'text': '球员向右侧外线移动。', 'frameTimes': [0, 1.5]},
            {'start': 3, 'end': 6, 'title': '转身接应', 'text': '他转身面向持球队友，准备接应。', 'frameTimes': [3, 4.5]}]}

    def test_runtime_mode_calls_model_with_images_and_preserves_response(self):
        client = Client(self.raw)
        result = analyze(self.payload, client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(result['segments'], self.raw['segments'])
        self.assertTrue(result['modelInvoked'])
        self.assertEqual(result['usage']['outputTokens'], 20)
        self.assertEqual(sum('image' in c for c in client.calls[0]['messages'][0]['content']), 5)

    def test_invalid_timing_references_and_text_are_rejected(self):
        variants = [
            {'start': -1}, {'end': 5}, {'start': float('nan')}, {'title': ''},
            {'frameTimes': []}, {'frameTimes': [1.2]}, {'frameTimes': [6]}, {'text': 3}]
        for change in variants:
            raw = copy.deepcopy(self.raw); raw['segments'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): normalize_segments(raw, self.payload)
        self.raw['segments'][1]['start'] = 2
        with self.assertRaises(ValueError): normalize_segments(self.raw, self.payload)

    def test_failure_never_falls_back_to_demo_copy(self):
        for client in [Client({'segments': []}), Client(self.raw, 'max_tokens')]:
            with self.assertRaises(ValueError): analyze(self.payload, client)

    def test_early_outcome_is_repaired_by_model_not_rewritten_locally(self):
        self.payload['deepData']={'videoId':'test','alignment':{'shotVideoTime':5}}
        bad=copy.deepcopy(self.raw);bad['segments'][0]['text']='球员突破挑篮命中。'
        good=copy.deepcopy(self.raw)
        class RepairClient(Client):
            def converse(self,**kwargs):
                self.value=bad if not self.calls else good
                return super().converse(**kwargs)
        client=RepairClient(bad);result=analyze(self.payload,client)
        self.assertEqual(len(client.calls),2);self.assertEqual(result['validationRepairs'],1)
        self.assertEqual(result['segments'],good['segments']);self.assertEqual(result['usage']['inputTokens'],20)
        self.assertIn('校验失败',client.calls[1]['system'][0]['text'])

    def test_only_final_verified_roles_go_to_narrator(self):
        result = {'video': self.payload['video'], 'players': [], 'events': [
            {'actorTrackId': 'rejected', 'visualVerified': False},
            {'actorTrackId': 'accepted', 'visualVerified': True}]}
        request = request_for_result(result, self.payload['frames'])
        self.assertEqual(request['narrationContext']['events'], [{'actorTrackId': 'accepted'}])
        self.assertEqual(request['frames'], self.payload['frames'])

    def test_long_video_is_narrated_in_separate_visual_windows(self):
        p=copy.deepcopy(self.payload);p['video']['duration']=10
        p['frames']=[{'time':t,'image':p['frames'][0]['image']} for t in [0,1.5,3,4.5,6,7.5,9]]
        class WindowClient(Client):
            def converse(self,**kwargs):
                document=json.loads(kwargs['messages'][0]['content'][0]['text']);w=document['narrationWindow']
                self.value={'segments':[{'start':w['start'],'end':min(w['start']+3,w['end']),'title':'接应','text':'球员向外线移动。','frameTimes':[w['start']]}]}
                return super().converse(**kwargs)
        client=WindowClient({});value=analyze(p,client)
        self.assertEqual(value['visualWindows'],2);self.assertEqual(len(client.calls),2)
        self.assertEqual(value['usage']['inputTokens'],20)

    def test_api_and_agent_contracts_match(self):
        for file in ['logic.py', 'narration.py', 'temporal.py', 'playmaking.py']:
            self.assertEqual((ROOT/'cloud/api'/file).read_bytes(), (ROOT/'cloud/agent'/file).read_bytes())


if __name__ == '__main__': unittest.main()
