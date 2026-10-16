#!/usr/bin/env python3
"""Run video → perception → Bedrock analysis/Reviewer → annotated MP4 locally."""
import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'cloud/api'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def prepare(video, companion=None, frame_count=18):
    import imageio_ffmpeg
    from vision import sample_video
    from companion import validate_companion
    reader = imageio_ffmpeg.read_frames(str(video))
    meta = next(reader)
    reader.close()
    duration = meta['duration']
    if not .5 <= duration <= 40:
        raise ValueError('Use a single possession clip between 0.5 and 40 seconds.')
    dense = sample_video(video, duration)
    if len(dense) < 3:
        raise ValueError('Video has fewer than three decodable frames.')
    indices = sorted({round(i*(len(dense)-1)/(frame_count-1)) for i in range(frame_count)})
    with video.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    video_id = 'clip-'+digest[:16]
    deep = {'videoId': video_id}
    if companion is not None:
        data = validate_companion(companion, duration)
        deep['companion'] = data
        if data.get('shotContext'):
            deep.update(official=data['shotContext'], opportunitySource=data['source'])
        for name in ['alignment', 'roster', 'playerProfiles', 'playByPlay', 'uniforms']:
            if name in data:
                deep[name] = data[name]
    payload = dict(mode='video', video=dict(id=video_id, title=video.stem[:200], duration=duration),
                   deepData=deep, frames=[dense[i] for i in indices])
    return payload, dense, digest


def analyze(payload, dense, digest, client, out, reviewer=True):
    from vision import build_vision
    from logic import analyze as model_analyze
    from candidate_review import prepare as prepare_review, apply, finalize
    print('1/4 Detecting players, ball and court…', flush=True)
    source_frames = copy.deepcopy(payload['frames'])
    payload['_denseFrames'] = dense
    vision, frames = build_vision(payload)
    payload.pop('_denseFrames', None)
    payload.update(vision=vision, frames=frames)
    save(out/'perception.json', vision)
    print('2/4 Understanding the possession…', flush=True)
    result = model_analyze(payload, client)
    if result.get('scoringVersion') == 'temporal-impact-v5':
        for _ in range(2):
            candidates = [e for e in result.get('events', []) if not e.get('visualVerified')][:3]
            if not candidates:
                break
            request = prepare_review(result, source_frames, candidates)
            if not request['candidates']:
                break
            verdict = model_analyze(request, client)
            result = apply(result, verdict['checks'])
        result = finalize(result)
    result['executionOrigin'] = 'local-bedrock'
    save(out/'analysis.json', result)
    print('3/4 Reviewing roles and commentary…', flush=True)
    if reviewer:
        from model_reviewer import run
        from reviewed_presentation import build
        plan, report, references = run(result, dense, lambda p: model_analyze(p, client),
                                      digest, 'analysis.json')
        save(out/'review.json', plan)
        save(out/'review-report.json', report)
        save(out/'references.json', references)
        result = build(result, plan, digest, 'analysis.json')
        result['modelReview'] = report
    else:
        from narration import request_for_result
        result['narration'] = model_analyze(request_for_result(result, source_frames), client)
    save(out/'result.json', result)
    return result


def export(video, result, out):
    from render_video import render, ffmpeg
    print('4/4 Rendering replay and story frames…', flush=True)
    # A saved cloud result may contain signed URLs. Render only local filenames.
    for i, frame in enumerate(result.get('presentation', {}).get('evidence', []), 1):
        frame['image'] = f'frame-{i}.jpg'
        frame.pop('imageKey', None)
    replay = render(video, result, out/'replay.mp4')
    if not replay or not (out/'replay.mp4').is_file():
        raise ValueError('Insufficient verified evidence to render. Inspect analysis.json; no MVP was invented.')
    subprocess.run([ffmpeg(), '-nostdin', '-y', '-v', 'error', '-i', str(video),
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-movflags', '+faststart', str(out/'original.mp4')], check=True)
    manifest = result['presentation']
    manifest.update(video='replay.mp4', original='original.mp4', rendered=True)
    save(out/'showcase.json', manifest)
    save(out/'presentation-plan.json', result['presentationPlan'])
    save(out/'result.json', result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--companion', type=Path, help='Optional companion-v1/v2 JSON, aligned to this clip')
    parser.add_argument('--out', type=Path, default=ROOT/'web/results/my-play')
    parser.add_argument('--profile', help='AWS profile; otherwise use the standard credential chain')
    parser.add_argument('--region', default=os.getenv('AWS_REGION', 'us-east-1'))
    parser.add_argument('--model', default=os.getenv('HIAGENT_MODEL_ID', 'qwen.qwen3-vl-235b-a22b'))
    parser.add_argument('--frames', type=int, choices=range(3,21), default=18, metavar='3–20')
    parser.add_argument('--no-review', action='store_true', help='Skip independent Reviewer (lower cost)')
    parser.add_argument('--analysis', type=Path, help='Render an existing result without model calls')
    args = parser.parse_args()
    video, out = args.video.resolve(), args.out.resolve()
    if not video.is_file():
        parser.error('Video does not exist: '+str(video))
    if out.exists() and any(out.iterdir()):
        parser.error('Output directory must be empty; choose a new --out to preserve previous results.')
    out.mkdir(parents=True, exist_ok=True)
    try:
        if args.analysis:
            document = json.loads(args.analysis.read_text())
            result = document.get('result', document.get('analysis', document))
        else:
            missing = [name for name in ['player','ball','court'] if not (ROOT/f'models/basketball/{name}.onnx').is_file()]
            if missing:
                raise ValueError('Missing ONNX models: '+', '.join(missing)+'. See docs/setup.md.')
            os.environ['HIAGENT_MODEL_ID'] = args.model
            from app_config import session
            from botocore.config import Config
            client = session(args.profile, args.region).client('bedrock-runtime', config=Config(
                read_timeout=300, retries={'total_max_attempts':3,'mode':'standard'}))
            data = json.loads(args.companion.read_text()) if args.companion else None
            payload, dense, digest = prepare(video, data, args.frames)
            save(out/'input.json', {'video':payload['video'], 'deepData':payload['deepData'], 'videoSha256':digest})
            result = analyze(payload, dense, digest, client, out, not args.no_review)
        export(video, result, out)
        save(out/'status.json', {'status':'completed','replay':'replay.mp4'})
    except Exception as exc:
        save(out/'status.json', {'status':'failed','error':str(exc)})
        print('Failed:', exc, file=sys.stderr)
        return 1
    print('Saved:', out/'replay.mp4')
    if out.is_relative_to(ROOT/'web'):
        print('View: http://127.0.0.1:8765/?result='+out.relative_to(ROOT/'web').as_posix()+'/showcase.json')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
