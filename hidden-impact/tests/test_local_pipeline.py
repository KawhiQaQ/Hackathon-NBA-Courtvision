import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from analyze_video import analyze, export
from app_config import outputs
from test_presentation import verified


class LocalPipelineTests(unittest.TestCase):
    def test_local_analysis_uses_model_result_and_writes_original(self):
        source = verified()
        source['modelInvoked'] = True
        frames = [{'time':0,'image':'sample'}]
        payload = {'video':source['video'], 'frames':frames}
        calls = []
        def model(document, client):
            calls.append(document.get('mode'))
            if document.get('mode') == 'narrate-video':
                return source['narration']
            return copy.deepcopy(source)
        with tempfile.TemporaryDirectory() as temp, patch('vision.build_vision', return_value=(source['vision'], frames)), patch('logic.analyze', side_effect=model):
            result = analyze(payload, frames, '0'*64, object(), Path(temp), reviewer=False)
            self.assertEqual(result['executionOrigin'], 'local-bedrock')
            saved = json.loads((Path(temp)/'analysis.json').read_text())
            self.assertTrue(saved['modelInvoked'])
            self.assertIn('narrate-video', calls)
            self.assertNotIn('referenceReview', result)

    def test_export_replaces_remote_and_unsafe_image_paths(self):
        source = verified()
        from presentation import build
        build(source)
        source['presentation']['evidence'][0]['image'] = 'https://example.com/a.jpg?signature=private'
        source['presentation']['evidence'][1]['image'] = '../../escape.jpg'
        def renderer(video, result, target):
            self.assertEqual([e['image'] for e in result['presentation']['evidence']], [f'frame-{i+1}.jpg' for i in range(len(result['presentation']['evidence']))])
            target.write_bytes(b'mp4')
            result['presentationPlan'] = {'schema':'test'}
            return {'status':'ready'}
        with tempfile.TemporaryDirectory() as temp, patch('render_video.render', side_effect=renderer), patch('subprocess.run'), patch('render_video.ffmpeg', return_value='ffmpeg'):
            export(Path('input.mp4'), source, Path(temp))
            manifest = json.loads((Path(temp)/'showcase.json').read_text())
            self.assertEqual(manifest['video'], 'replay.mp4')
            self.assertTrue(manifest['rendered'])

    def test_unrenderable_analysis_does_not_produce_success_manifest(self):
        with tempfile.TemporaryDirectory() as temp, patch('render_video.render', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Insufficient'):
                export(Path('input.mp4'), {'events':[]}, Path(temp))
            self.assertFalse((Path(temp)/'showcase.json').exists())

    def test_config_selects_custom_stack_without_old_account(self):
        import app_config
        with tempfile.TemporaryDirectory() as temp, patch.object(app_config,'ROOT',Path(temp)):
            (Path(temp)/'infra').mkdir()
            (Path(temp)/'infra/cdk-outputs.json').write_text(json.dumps({'MyProject':{'MediaBucket':'mine','FrontendUrl':'https://example.com'}}))
            self.assertEqual(outputs()['MediaBucket'],'mine')
