"""Data-driven broadcast chapters shared by automatic and reviewed presentations."""
import math


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


def build_direction(manifest, duration, event=None):
    info=manifest.get('insights') or {};shot=info.get('shotVideoTime')
    window=None
    if event and finite(event.get('start')) and finite(event.get('end')):
        window=[event['start'],event['end']]
    elif manifest.get('analysisStatus')=='reviewed-story':
        # Reviewed chapters carry their provenance; no clip IDs or player numbers.
        cues=[c for c in info.get('cues',[]) if any(w in c.get('title','') for w in ['掩护','挡拆','绕防','牵制','分球']) and finite(c.get('start')) and finite(c.get('end'))]
        if cues:window=[cues[0]['start'],cues[min(1,len(cues)-1)]['end']]
    if window:
        start=max(0,window[0]);end=min(duration,window[1],shot-.5 if finite(shot) else duration)
        if end-start<.4 or len(manifest.get('roles',[]))<3:window=None
        else:window=[start,end]
    return {'schema':'hidden-impact/broadcast-direction-v1','focusWindow':window,
            'focusRoleIndices':[0,2], 'phases':['威胁','动作','机会'],
            'source':'reviewed-chapters' if manifest.get('analysisStatus')=='reviewed-story' else 'verified-event',
            'shotTime':shot if finite(shot) else None}


def phase_at(direction,t):
    window=direction.get('focusWindow')
    if window:return 0 if t<window[0] else 1 if t<window[1] else 2
    shot=direction.get('shotTime');return 2 if finite(shot) and t>=max(0,shot-5) else 0


def draw_chapters(draw,font,direction,t,duration):
    active=phase_at(direction,t);colors=['#f4c45e','#ee927f','#77cfe4']
    for i,label in enumerate(direction['phases']):
        x=522+i*137;selected=i==active
        draw.rounded_rectangle((x,8,x+125,33),radius=5,fill=(*bytes.fromhex(colors[i][1:]),38) if selected else (255,255,255,8))
        draw.text((x+10,10),f'0{i+1}  {label}',font=font(13),fill=colors[i] if selected else '#7f98a0')
    draw.line((20,42,940,42),fill='#243e48',width=1)
    draw.line((20,42,20+920*min(1,max(0,t/max(duration,.01))),42),fill=colors[active],width=2)
