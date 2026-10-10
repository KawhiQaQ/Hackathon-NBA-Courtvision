"""Reproducible five-play reviewed showcase, using production scores and outputs.
Human review inputs remain in the repository and generation metadata; no fake
model receipts or automatic-inference claims are written by this script.
"""
import copy,json,math,sys,shutil
from pathlib import Path
from statistics import median
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud/api'))
from presentation import build,motion
from render_video import render
from game_summary import measured_action,round_score,aggregate
from game_review_annotations import CLIPS


def peer_data(official):
    for p in (ROOT/'data/nba').glob('*.json'):
        try:d=json.loads(p.read_text());d=d.get('data',d)
        except (ValueError,AttributeError):continue
        if isinstance(d,dict) and str(d.get('playerId'))==str(official['playerId']) and d.get('gameId')==official['gameId'] and d.get('shotList'):return d
    ref=json.loads((ROOT/'data/reference/showcase-deep-data.json').read_text())['playerShots']
    return ref if str(ref['playerId'])==str(official['playerId']) else None


def reviewed_result(item,config):
    ids=['NYK-'+config['hero'],'NYK-'+config['mate'],'SAS-'+config['defender']]
    from reviewed_role_paths import reviewed_frames
    duration=item['duration'];frames=reviewed_frames(item['official']['eventId'],ids,duration)
    from camera_motion import attach
    from vision import sample_video
    camera=attach({'frames':frames},sample_video(ROOT/f'data/videos/nba-public/{item["id"]}.mp4',duration))
    rows=[];start,end=config['window']
    for f in frames:
        if not start<=f['time']<=end or len(f['people'])!=3:continue
        points=[((p['x']+p['w']/2)*16/9,p['y']+p['h']) for p in f['people']];unit=median(p['h'] for p in f['people']);a,b,d=points
        rows.append({'time':f['time'],'a':a,'b':b,'d':d,'engagement':math.dist(a,d)/unit,'separation':math.dist(b,d)/unit})
    action=measured_action(rows)
    players=[dict(id=pid,label=f"{'尼克斯' if j<2 else '马刺'} {num}号",role='offense' if j<2 else 'defense',team='light' if j<2 else 'dark',score=action if j==0 else None,status='candidate' if j==0 else 'observed') for j,(pid,num) in enumerate(zip(ids,[config['hero'],config['mate'],config['defender']]))]
    observations=[{'time':r['time'],'text':'队友与相关防守者的相对间距 '+str(round(r['separation'],1))+' 人物高度','marks':[]} for r in [rows[0],rows[len(rows)//2],rows[-1]]]
    event={'id':item['id']+'-reviewed','actorTrackId':ids[0],'beneficiaryTrackId':ids[1],'defenderTrackId':ids[2],'start':start,'end':end,'keyTime':(start+end)/2,'title':config['title'],'actionType':config['kind'],'score':action,'visualVerified':True,'verificationSource':'human-video-review',
        'components':[],'summary':config['story'][2][3],'observations':observations,'measurement':{'series':rows,'quality':.81,'units':'人物高度'}}
    segments=[]
    for start,end,title,text in config['story']:
        refs=[round((start+end)/2,2),round(min(end-.2,duration-.1),2)]
        segments.append(dict(start=start,end=end,title=title,text=text,frameTimes=refs))
    deep=copy.deepcopy(item.get('deepData') or {'videoId':item['id'],'official':item['official']});peer=peer_data(item['official'])
    if peer:deep['playerShots']=peer
    ref=json.loads((ROOT/'data/reference/showcase-deep-data.json').read_text())
    deep['official']['gravityScope']='2025–26 季后赛'
    deep['official']['rosterGravity']=[{'id':str(p['PLAYERID']),'name':p.get('FIRSTNAME','')+' '+p.get('LASTNAME',''),'team':p.get('lightLogo','').split('/')[-1].split('_')[0],'games':p.get('GP'),'gravity':{k:v for k,v in p.items() if k.endswith('_GRAV')}} for p in ref['gravityPlayers']]
    return dict(version='basketball-roster-v3',scoringVersion='temporal-impact-v5',video={k:item[k] for k in ['id','duration','title']},players=players,events=[event],vision={**camera,'aspectRatio':16/9},deepData=deep,
        modelInvoked=False,model=None,review={'source':'human-reviewed-keyframes'},narration={'schema':'hidden-impact/timed-narration-v1','source':'prepared-evidence-script','modelInvoked':False,'segments':segments})


def render_first(audit,manifest,destination):
    destination.mkdir(exist_ok=True)
    manifest.update(mode='analysis',status='ready',eventId=audit['events'][0]['id'])
    audit['presentation']=manifest
    from camera_motion import attach
    from vision import sample_video
    # Preserve accepted reviewed positions, regenerate BOTH arrows through the
    # production motion builder instead of retaining a separate first-play style.
    frames=[{'time':row['time'],'scene':0,'people':[p for p in row['people'] if not p.get('offscreen')]} for row in audit['presentationMotion']['frames']]
    audit['vision']=attach({**audit['vision'],'frames':frames},sample_video(ROOT/'web/demo/original.mp4',audit['video']['duration']))
    audit['presentationMotion']=motion(audit,audit['events'][0],fps=30)
    for k,entry in enumerate(manifest['evidence']):entry['image']=f'frame-{k+1}.jpg'
    render(ROOT/'web/demo/original.mp4',audit,destination/'replay.mp4')
    manifest.update(mode='demo',video='game/197/replay.mp4',rendered=True,renderStyle='dual-route-v3')
    for k,entry in enumerate(manifest['evidence']):entry['image']=f'game/197/frame-{k+1}.jpg'
    manifest['poster']=manifest['evidence'][0]['image']


def package():
    catalog={str(v['official']['eventId']):v for v in json.loads((ROOT/'web/data/nba-catalog.json').read_text())}
    out=ROOT/'web/demo/game';out.mkdir(parents=True,exist_ok=True)
    archive=ROOT/'data/review-archive/game';archive.mkdir(parents=True,exist_ok=True)
    rounds=[]
    # The reviewed 44 play keeps the user's accepted visualization.
    first=json.loads((ROOT/'web/demo/showcase.json').read_text())
    audit=json.loads((ROOT/'data/review-archive/showcase-audit.json').read_text())['analysis']
    e=audit['events'][0];series=[]
    for f in audit['vision']['frames']:
        if not e['start']<=f['time']<=e['end']:continue
        people={p['trackId']:p for p in f['people']}
        ids=[e[k] for k in ['actorTrackId','beneficiaryTrackId','defenderTrackId']]
        if not all(i in people for i in ids):continue
        ps=[people[i] for i in ids];unit=median(p['h'] for p in ps)
        a,b,d=[((p['x']+p['w']/2)*16/9,p['y']+p['h']) for p in ps]
        series.append({'time':f['time'],'engagement':math.dist(a,d)/unit,'separation':math.dist(b,d)/unit})
    action=measured_action(series)
    first['impact']=round_score(action,first['insights']['shot']);first['score']=action
    first.update(gameId='0042500404',team='尼克斯',videoId='nba-0042500404-197',roundKey='0042500404:197',identity={'jersey':'44','confirmed':True,'source':'user-and-video-review'},actionTitle='接应之后，及时分球',summary='44号接应并推进，再把球转移给外线的8号。')
    first['scoreKind']='reviewed-geometric-index';first['generation']={'source':'human-reviewed-presentation','modelInvoked':False}
    for key in ['video','original','poster']:
        if key in first:first[key]=first[key].replace('demo/','',1)
    for f in first['evidence']:f['image']=f['image'].replace('demo/','',1)
    for i,number in enumerate(['44','8','30']):first['roles'][i]['displayName']=('尼克斯' if i<2 else '马刺')+' '+number+'号 · '+first['roles'][i]['label']
    first['actor']['label']='尼克斯 44号'
    first['insights']['shooter']='尼克斯 8号';first['insights']['gravity']['player']='尼克斯 8号'
    def rename(x):
        if isinstance(x,str):return x.replace('8号阿努诺比','8号').replace('OG 阿努诺比','尼克斯8号').replace('阿努诺比','8号')
        if isinstance(x,list):return [rename(y) for y in x]
        if isinstance(x,dict):return {k:rename(v) for k,v in x.items()}
        return x
    first=rename(first)
    first['provenance']='历史视觉轨迹与人工复核位置；动作观察指数及回合贡献分由当前统一公式重新计算。'
    first['scoreSource']='measured-reviewed-geometry';first['scoreComponents']=[]
    render_first(audit,first,out/'197')
    single=copy.deepcopy(first);single['video']='replay.mp4';single['original']='../../original.mp4';single['poster']='frame-1.jpg'
    for k,f in enumerate(single['evidence']):f['image']=f'frame-{k+1}.jpg'
    (out/'197/showcase.json').write_text(json.dumps(single,ensure_ascii=False,indent=2))
    (archive/'197.json').write_text(json.dumps(audit,ensure_ascii=False))
    rounds.append(first)
    for event_id,cfg in CLIPS.items():
        item=catalog[str(event_id)];result=reviewed_result(item,cfg);manifest=build(result)
        manifest.update(renderStyle='dual-route-v3',mode='demo',identity={'jersey':cfg['hero'],'confirmed':True,'source':'human-video-review'},duration=item['duration'])
        manifest['insights']['shooter']='尼克斯 '+cfg['mate']+'号'
        if manifest['insights'].get('gravity'):manifest['insights']['gravity']['player']='尼克斯 '+cfg['mate']+'号'
        destination=out/str(event_id);destination.mkdir(exist_ok=True)
        # Renderer uses the same contract in both cases; mode has no effect on markings.
        manifest['mode']='analysis';render(ROOT/f'data/videos/nba-public/{item["id"]}.mp4',result,destination/'replay.mp4');manifest['mode']='demo'
        shutil.copyfile(ROOT/f'data/videos/nba-public/{item["id"]}.mp4',destination/'original.mp4')
        (archive/f'{event_id}.json').write_text(json.dumps(result,ensure_ascii=False))
        # Keep per-clip standalone manifests plus collection-relative asset links.
        manifest['rendered']=True
        (destination/'analysis.json').write_text(json.dumps({**result,'demo':True,'presentation':manifest},ensure_ascii=False))
        (destination/'showcase.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        collection=copy.deepcopy(manifest)
        for key in ['video','original']:collection[key]=f'game/{event_id}/'+collection[key]
        for f in collection['evidence']:f['image']=f'game/{event_id}/'+f['image']
        rounds.append(collection)
        print(event_id,manifest['impact']['score'],manifest['identity'],flush=True)
    summary=aggregate(rounds,'0042500404','尼克斯');summary['teamId']='14'
    (ROOT/'web/demo/game.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print('Winner:',summary['winner']['label'] if summary['winner'] else 'tie',flush=True)

if __name__=='__main__':package()
