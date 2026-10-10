#!/usr/bin/env python3
"""Export a verified result to the shared showcase viewer, locally or for S3.

python scripts/export_result.py --analysis result.json --video input.mp4 --out web/results/my-play
Open /?result=results/my-play/showcase.json . No demo files or player IDs used.
"""
import argparse,json,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from presentation import build
from render_video import render
from review import reviewed_result


def export(analysis,video,out):
    result=reviewed_result(analysis)
    manifest=build(result)
    if manifest.get('status')!='ready':raise ValueError(manifest['reason'])
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    render(video,result,out/'replay.mp4')
    # Transcode instead of giving a WebM/MOV file a false .mp4 extension.
    import subprocess
    from render_video import ffmpeg
    subprocess.run([ffmpeg(),'-y','-v','error','-i',str(video),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(out/'original.mp4')],check=True)
    manifest['rendered']=True
    (out/'showcase.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (out/'presentation-plan.json').write_text(json.dumps(result['presentationPlan'],ensure_ascii=False,indent=2))
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--analysis',required=True,type=Path);parser.add_argument('--video',required=True,type=Path);parser.add_argument('--out',required=True,type=Path);args=parser.parse_args()
    document=json.loads(args.analysis.read_text());result=document.get('result',document.get('analysis',document))
    export(result,args.video,args.out)
    print(args.out/'showcase.json')
