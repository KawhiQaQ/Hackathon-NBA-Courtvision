"""Source-time story beats and a frame-exact, portable replay edit timeline."""
import math


def plan(manifest, duration, fps):
    total_frames=max(1,round(duration*fps));source_end=total_frames/fps
    # Keep short competition clips under one minute. Longer inputs retain their
    # full source; they are never silently truncated to meet a delivery limit.
    budget=max(0,math.floor((59-source_end)*fps))
    segments=manifest.get('insights',{}).get('narration',{}).get('segments',[])
    beats=[];last=-fps
    for evidence in sorted(manifest.get('evidence',[]),key=lambda e:e['time']):
        frame=max(0,min(total_frames-1,round(evidence['time']*fps)))
        segment=next((s for s in segments if s['start']<=evidence['time']<s['end']),{})
        text=segment.get('text') or evidence.get('text','')
        if not text or frame-last<fps or len(beats)>=8:continue
        typing=min(3.5,max(.85,len(text)/21))
        count=round((typing+.8)*fps)
        if count>budget:continue
        beats.append({'sourceFrame':frame,'sourceTime':frame/fps,'duration':count/fps,'holdFrames':count,
                      'typingDuration':typing,'title':segment.get('title') or evidence.get('label','关键配合'),'text':text})
        budget-=count;last=frame
    offset=0
    for beat in beats:
        beat['start']=(beat['sourceFrame']+offset)/fps
        offset+=beat['holdFrames'];beat['end']=(beat['sourceFrame']+offset)/fps
    return {'schema':'hidden-impact/story-playback-v1','sourceDuration':source_end,
            'duration':(total_frames+offset)/fps,'fps':fps,'beats':beats}


def audio_filter(timeline):
    """Pause the original soundtrack with silence; resume at the same source time."""
    filters=[];inputs=[];cursor=0
    for i,beat in enumerate(timeline['beats']):
        t=beat['sourceTime']
        if t>cursor:
            name=f'a{i}';filters.append(f'[1:a:0]atrim=start={cursor}:end={t},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[{name}]');inputs.append(f'[{name}]')
        name=f'p{i}';filters.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={beat["duration"]}[{name}]');inputs.append(f'[{name}]');cursor=t
    if cursor<timeline['sourceDuration']:
        filters.append(f'[1:a:0]atrim=start={cursor}:end={timeline["sourceDuration"]},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[tail]');inputs.append('[tail]')
    filters.append(''.join(inputs)+f'concat=n={len(inputs)}:v=0:a=1[storyaudio]')
    return ';'.join(filters)
