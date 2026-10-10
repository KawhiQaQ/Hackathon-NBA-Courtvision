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


def focus_box(image_size,people,aspect):
    """Crop real pixels only, reject offscreen/invalid geometry. Never fabricate tracks."""
    if len(people)!=2 or any(p.get('offscreen') or any(not finite(p.get(k)) for k in ['x','y','w','h']) or not 0<p['w']<=1 or not 0<p['h']<=1 for p in people):return None
    w,h=image_size
    left=min(p['x'] for p in people)*w;right=max(p['x']+p['w'] for p in people)*w
    top=min(p['y']+p['h']*.04 for p in people)*h;bottom=max(p['y']+p['h']*.68 for p in people)*h
    if right<0 or left>w or bottom<0 or top>h:return None
    width=max((right-left)*1.1,(bottom-top)*1.12*aspect,w*.20)
    if width>w or width/aspect>h:return None
    height=width/aspect;cx=(left+right)/2;cy=(top+bottom)/2
    x=max(0,min(w-width,cx-width/2));y=max(0,min(h-height,cy-height/2))
    return (round(x),round(y),round(x+width),round(y+height))


def draw_chapters(draw,font,direction,t,duration):
    active=phase_at(direction,t);colors=['#f4c45e','#ee927f','#77cfe4']
    for i,label in enumerate(direction['phases']):
        x=522+i*137;selected=i==active
        draw.rounded_rectangle((x,8,x+125,33),radius=5,fill=(*bytes.fromhex(colors[i][1:]),38) if selected else (255,255,255,8))
        draw.text((x+10,10),f'0{i+1}  {label}',font=font(13),fill=colors[i] if selected else '#7f98a0')
    draw.line((20,42,940,42),fill='#243e48',width=1)
    draw.line((20,42,20+920*min(1,max(0,t/max(duration,.01))),42),fill=colors[active],width=2)


def draw_focus(canvas,original,draw,font,frame,manifest,bounds,scale):
    from PIL import Image,ImageDraw
    roles=manifest.get('roles',[])
    if len(roles)<3:return False
    ids=[roles[i]['id'] for i in (0,2)];by_id={p['trackId']:p for p in frame['people']}
    people=[by_id.get(i,{'offscreen':True}) for i in ids]
    crop=focus_box(original.size,people,292/137)
    if not crop:return False
    cx,cy,cw,ch=bounds;accent='#f4c45e'
    draw.rounded_rectangle((cx,cy,cx+cw,cy+ch),radius=10,fill=(5,22,30,248),outline=accent,width=1)
    draw.text((cx+14,cy+9),'02 / 配合放大镜',font=font(17),fill=accent)
    draw.text((cx+cw-64,cy+13),'同步画面',font=font(10),fill='#b4c8cf')
    ix,iy,iw,ih=cx+10,cy+39,292,137
    patch=original.crop(crop).resize((round(iw*scale),round(ih*scale)),Image.Resampling.LANCZOS)
    canvas.paste(patch,(round(ix*scale),round(iy*scale)))
    left,top,right,bottom=crop
    # Fine colored marks associate each magnified figure with the stable role rail.
    for p,role in zip(people,[roles[0],roles[2]]):
        x=ix+((p['x']+p['w']/2)*original.width-left)/(right-left)*iw
        y=iy+(p['y']*original.height-top)/(bottom-top)*ih
        y=max(iy+7,min(iy+ih-7,y-3))
        draw.ellipse((x-4,y-4,x+4,y+4),fill=role['color'],outline='#ffffff')
        draw.line((x,y+5,x,y+13),fill=role['color'],width=2)
    draw.ellipse((cx+15,cy+186,cx+21,cy+192),fill=roles[0]['color'])
    draw.text((cx+27,cy+180),'主角',font=font(12),fill=roles[0]['color'])
    draw.ellipse((cx+80,cy+186,cx+86,cy+192),fill=roles[2]['color'])
    draw.text((cx+92,cy+180),'防守响应',font=font(12),fill=roles[2]['color'])
    f=(manifest.get('insights',{}).get('actorProfile') or {}).get('finishing')
    if f:
        label=f"此前 {f['made']}/{f['sampleCount']}"
        draw.text((cx+cw-14-draw.textlength(label,font=font(12)),cy+180),label,font=font(12),fill=accent)
    return True
