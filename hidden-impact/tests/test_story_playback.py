import json,sys,unittest,tempfile,subprocess,array,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from story_playback import plan

class StoryPlaybackTests(unittest.TestCase):
    def manifest(self,n=6):
        return {'evidence':[{'time':i*3+1,'label':'配合','text':'幕后MVP掩护，队友借机移动。'} for i in range(n)]}
    def test_frame_exact_holds_have_reading_time_and_bounded_total(self):
        p=plan(self.manifest(),21.55,24)
        self.assertEqual(len(p['beats']),6)
        self.assertLess(p['duration'],59)
        offset=0
        for beat in p['beats']:
            self.assertAlmostEqual(beat['start'],beat['sourceTime']+offset)
            self.assertGreaterEqual(beat['duration']-beat['typingDuration'],.65)
            self.assertEqual(beat['holdFrames'],round(beat['duration']*24))
            offset+=beat['duration']
        self.assertAlmostEqual(p['duration'],p['sourceDuration']+offset)
    def test_many_beats_long_clips_and_duplicate_keyframes_are_safe(self):
        p=plan(self.manifest(20),58,24)
        self.assertLessEqual(p['duration'],59)
        self.assertEqual(plan(self.manifest(),70,24)['beats'],[])
        m=self.manifest(1);m['evidence']*=4
        self.assertEqual(len(plan(m,4,24)['beats']),1)
        self.assertEqual(plan({'evidence':[]},3,24)['duration'],3)
    def test_real_video_freezes_picture_types_caption_and_pauses_sound(self):
        from test_presentation import verified
        from presentation import build
        from render_video import render,ffmpeg
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);src=folder/'in.mp4';out=folder/'out.mp4'
            subprocess.run([ffmpeg(),'-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=10:d=2.5','-f','lavfi','-i','sine=frequency=440:duration=2.5','-c:v','libx264','-c:a','aac','-shortest',str(src)],check=True)
            r=verified();build(r,fps=10);render(src,r,out)
            timeline=r['presentation']['playback'];beat=timeline['beats'][0]
            def pixels(t):
                raw=subprocess.check_output([ffmpeg(),'-v','error','-ss',str(t),'-i',str(out),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
                return np.frombuffer(raw,dtype=np.uint8).reshape(228,320,3).astype(float)
            a=pixels(beat['start']+.1);b=pixels(beat['end']-.2)
            self.assertLess(np.abs(a[:203]-b[:203]).mean(),1.5,'Gameplay and annotations must stay frozen')
            self.assertGreater(np.abs(a[203:]-b[203:]).mean(),.5,'Caption must progress during hold')
            audio=subprocess.check_output([ffmpeg(),'-v','error','-i',str(out),'-vn','-ac','1','-ar','8000','-f','f32le','-'])
            samples=np.frombuffer(audio,dtype=np.float32)
            def rms(a,b):return np.sqrt(np.mean(samples[round(a*8000):round(b*8000)]**2))
            self.assertLess(rms(beat['start']+.2,beat['end']-.2),.001)
            self.assertGreater(rms(beat['end']+.1,beat['end']+.2),.01)
            self.assertAlmostEqual(len(samples)/8000,timeline['duration'],delta=.08)
            # The full final source frame still exists after all insertions.
            self.assertEqual(len(pixels(timeline['duration']-.1)),228)

if __name__=='__main__':unittest.main()
