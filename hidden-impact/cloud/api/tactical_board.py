"""Compact relative-position tactics board driven by the replay's own tracks.

Image-space feet are shown in a fixed viewport, not invented court coordinates.
Arrows preview observed later positions only around evidence timestamps.
"""
import math
import re


def feet(person, motion):
    if person.get('offscreen'):
        return None
    values = [person.get(k) for k in ('x', 'y', 'w', 'h')]
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        return None
    return ((person['x'] + person['w'] / 2) * motion['width'],
            (person['y'] + person['h']) * motion['height'])


def build_board(motion, manifest):
    window = manifest.get('direction', {}).get('focusWindow')
    if not window:
        return None
    roles = manifest.get('roles', [])
    ids = {r['id'] for r in roles}
    samples = [point for f in motion['frames'] if window[0] <= f['time'] <= window[1]
               for p in f['people'] if p['trackId'] in ids and (point := feet(p, motion)) is not None]
    if len(ids) < 3 or not samples:
        return None
    left, right = min(p[0] for p in samples), max(p[0] for p in samples)
    top, bottom = min(p[1] for p in samples), max(p[1] for p in samples)
    # One viewport for the complete action: no frame-by-frame zoom or rescaling.
    aspect = 280 / 126
    width = max((right-left) * 1.28, (bottom-top) * 1.36 * aspect, motion['width'] * .2)
    height = width / aspect
    center = ((left+right)/2, (top+bottom)/2)
    times = [f['time'] for f in manifest.get('evidence', []) if window[0] < f['time'] < window[1]]
    if not times:
        times = [(window[0]+window[1])/2]
    windows = [[max(window[0], t-.55), min(window[1], t+.65)] for t in times]
    return dict(schema='hidden-impact/tactical-board-v1', coordinateSystem='image-relative',
                viewport=[center[0]-width/2, center[1]-height/2, width, height],
                arrowWindows=windows, trackIds=[r['id'] for r in roles], window=window)


def points_at(motion, time):
    index = max(0, min(len(motion['frames'])-1, round(time * motion['fps'])))
    return {p['trackId']: p for p in motion['frames'][index]['people']}


def board_state(motion, board, time):
    current = points_at(motion, time)
    visible = {pid: point for pid in board['trackIds']
               if pid in current and (point := feet(current[pid], motion)) is not None}
    routes = {}
    if any(start <= time < end for start, end in board['arrowWindows']):
        # An arrow may not bridge an occlusion or a scene cut.
        for pid, point in visible.items():
            path = [point]
            for step in range(1, 5):
                target_time = time + step * .18
                if target_time > board['window'][1]:
                    break
                person = points_at(motion, target_time).get(pid, {})
                q = feet(person, motion)
                if q is None or person.get('scene') != current[pid].get('scene'):
                    break
                path.append(q)
            if len(path) > 1 and math.dist(path[0], path[-1]) > motion['width'] * .008:
                routes[pid] = path
    return visible, routes


def marker_centers(points, bounds):
    """Separate number badges; tiny anchor dots retain measured positions."""
    out={pid:list(point) for pid,point in points.items()}
    ids=list(out)
    for _ in range(6):
        for i,a in enumerate(ids):
            for b in ids[i+1:]:
                dx,dy=out[b][0]-out[a][0],out[b][1]-out[a][1]
                distance=math.hypot(dx,dy)
                if distance>=24:continue
                ux,uy=(dx/distance,dy/distance) if distance>.001 else (1,0)
                shift=(24-distance)/2
                for pid,sign in [(a,-1),(b,1)]:
                    out[pid][0]=max(bounds[0]+12,min(bounds[2]-12,out[pid][0]+sign*ux*shift))
                    out[pid][1]=max(bounds[1]+12,min(bounds[3]-12,out[pid][1]+sign*uy*shift))
    return out


def draw_board(draw, font, motion, manifest, time, bounds):
    board = manifest['direction'].get('board')
    if not board:
        return False
    cx, cy, cw, ch = bounds
    from render_video import instrument_panel
    instrument_panel(draw,bounds)
    draw.text((cx+14,cy+9),'配合战术板',font=font(17),fill='#e3c991')
    draw.text((cx+cw-64,cy+14),'相对站位',font=font(10),fill='#a8b3a4')
    px,py,pw,ph=cx+16,cy+43,280,126
    draw.rounded_rectangle((px,py,px+pw,py+ph),radius=2,fill='#16271c',outline='#4a5944',width=1)
    # A restrained schematic grid; no basket, meter scale or false homography.
    for i in range(1,4):
        draw.line((px+pw*i/4,py,px+pw*i/4,py+ph),fill='#2a3b2b',width=1)
    for i in range(1,3):
        draw.line((px,py+ph*i/3,px+pw,py+ph*i/3),fill='#2a3b2b',width=1)
    left,top,width,height=board['viewport']
    project=lambda p:(px+(p[0]-left)/width*pw,py+(p[1]-top)/height*ph)
    people,routes=board_state(motion,board,time)
    roles={r['id']:r for r in manifest['roles']}
    anchors={pid:project(point) for pid,point in people.items()}
    markers=marker_centers(anchors,(px,py,px+pw,py+ph))
    for pid,path in routes.items():
        points=[project(p) for p in path]
        start,end=points[0],points[-1];dist=math.dist(start,end)
        if dist<16:continue
        ux,uy=(end[0]-start[0])/dist,(end[1]-start[1])/dist
        start=(start[0]+ux*11,start[1]+uy*11)
        color=roles[pid]['color']
        draw.line((start,end),fill=color,width=2)
        draw.line(((end[0]-ux*6-uy*3,end[1]-uy*6+ux*3),end,
                   (end[0]-ux*6+uy*3,end[1]-uy*6-ux*3)),fill=color,width=2)
    for index,role in enumerate(manifest['roles']):
        pid=role['id'];point=people.get(pid)
        if point:
            x,y=markers[pid];color=role['color']
            ax,ay=anchors[pid]
            if math.dist((x,y),(ax,ay))>1:
                draw.line(((ax,ay),(x,y)),fill=color,width=1)
                draw.ellipse((ax-2,ay-2,ax+2,ay+2),fill=color)
            if index==0:draw.ellipse((x-13,y-13,x+13,y+13),outline=(*bytes.fromhex(color[1:]),100),width=1)
            draw.ellipse((x-10,y-10,x+10,y+10),fill=color,outline='#d8e4db',width=1)
            match=re.search(r'(\d+)\s*号',role.get('displayName',''))
            label=match.group(1) if match else str(index+1)
            tw=draw.textlength(label,font=font(11))
            draw.text((x-tw/2,y-8),label,font=font(11),fill='#102028')
        x=cx+15+index*97
        draw.ellipse((x,cy+184,x+5,cy+189),fill=role['color'] if point else '#56636a')
        label=['幕后MVP','受益队友','防守者'][index] + (' · 画外' if not point else '')
        draw.text((x+10,cy+178),label,font=font(11),fill=role['color'] if point else '#879598')
    return True
