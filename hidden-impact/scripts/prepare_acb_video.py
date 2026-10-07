"""Read ACB's public same-game highlight stream for research and shot alignment.
Original source: https://vimeo.com/1126497253 (ACB). Not SkillCorner-supplied footage.
The full research copy is local-only. Only short matched excerpts are used in analysis.
"""
import json,urllib.request,subprocess
from pathlib import Path
import imageio_ffmpeg
root=Path(__file__).resolve().parents[1];output=root/'data/videos/acb-114243-highlights.mp4'
config=json.load(urllib.request.urlopen('https://player.vimeo.com/video/1126497253/config'))
hls=config['request']['files']['hls'];url=hls['cdns'][hls['default_cdn']]['url']
if not output.exists():
 subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',url,'-vf','scale=960:-2','-c:v','libx264','-preset','fast','-crf','25','-an',str(output)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
frames=root/'data/frames/acb';frames.mkdir(exist_ok=True)
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(output),'-vf','fps=1/5,scale=720:-2','-q:v','5',str(frames/'frame-%03d.jpg')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print('ACB reference downloaded for alignment:',output.stat().st_size)
