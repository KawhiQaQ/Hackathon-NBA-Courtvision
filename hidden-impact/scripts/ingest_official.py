"""Register a sourced video and an explicitly matched NBA shot in private S3.

No guessed event matching: pass the game/player/event after checking the footage.
Produces a regular /api/jobs request; no prepared player roles or commentary.
"""
from app_config import session as aws_session, outputs as deployment_outputs
import argparse,base64,hashlib,json,subprocess,sys,urllib.parse,urllib.request
from pathlib import Path
import boto3,imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]

def fetch(path,params):
    url='https://api.nba.cn/nba-web/api/web/inside/'+path+'?'+urllib.parse.urlencode(params)
    with urllib.request.urlopen(url,timeout=30) as r:document=json.load(r)
    if document.get('code')!=0:raise ValueError('NBA data unavailable')
    return document['data'],url

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--video',type=Path,required=True);ap.add_argument('--id',required=True)
    ap.add_argument('--game',required=True);ap.add_argument('--player',required=True);ap.add_argument('--event',type=int,required=True)
    ap.add_argument('--publication-basis',choices=['private','licensed','organizer-provided'],default='private');ap.add_argument('--source',required=True);ap.add_argument('--shot-time',type=float);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--season',default='2025-26');ap.add_argument('--season-type',default='Regular Season')
    ap.add_argument('--teams',default='DAL,HOU',help='Team abbreviations for gravity comparison')
    ap.add_argument('--companion',type=Path,help='Validated companion JSON for this same clip')
    ap.add_argument('--prepare-only',action='store_true',help='Prepare request and source metadata without uploading')
    args=ap.parse_args()
    import re
    if not re.fullmatch('[a-zA-Z0-9_-]{1,100}',args.id):raise ValueError('Invalid clip ID')
    shots,url=fetch('gpShot',dict(gameId=args.game,playerId=args.player))
    shot=next(s for s in shots['shotList'] if s['eventId']==args.event)
    gravity,gravity_url=fetch('season/playerGravity',dict(season=args.season,seasonType=args.season_type))
    roster=[]
    for p in gravity['players']:
        team=p['lightLogo'].split('/')[-1].split('_')[0]
        if team not in args.teams.split(','):continue
        roster.append(dict(id=str(p['PLAYERID']),name=p['FIRSTNAME']+' '+p['LASTNAME'],team=team,games=p['GP'],
            gravity={k:p[k] for k in ['OVERALL_GRAV','ON_BALL_PERIM_GRAV','ON_BALL_INTERIOR_GRAV','OFF_BALL_PERIM_GRAV','OFF_BALL_INTERIOR_GRAV']}))
    reader=imageio_ffmpeg.read_frames(str(args.video));meta=next(reader);reader.close();duration=meta['duration']
    if not .5<=duration<=40:raise ValueError('Clip must be 0.5–40s')
    official=dict(source='NBA China · Inside the Game',url=f'https://china.nba.cn/inside-the-game/video/{args.player}?gameId={args.game}&playerId={args.player}',
        gameId=args.game,eventId=args.event,playerId=args.player,shooter=shots['playerFirstName']+' '+shots['playerLastName'],
        team=shots['teamName'],matchup=shots['matchup'],shot=shot,rosterGravity=roster,gravityScope=f'{args.season} {args.season_type} 阶段汇总')
    deep=dict(videoId=args.id,official=official,playerShots=dict(gameId=args.game,playerId=args.player,shotList=shots['shotList']),
        sources=[url,gravity_url])
    if args.shot_time is not None:
        if not 0<=args.shot_time<=duration:raise ValueError('shot-time outside clip')
        deep['alignment']=dict(shotVideoTime=args.shot_time,source='visual-review',eventId=args.event)
    companion=None
    if args.companion:
        sys.path.insert(0,str(ROOT/'cloud/api'))
        from companion import validate_companion
        companion=validate_companion(json.loads(args.companion.read_text()),duration)
        ctx=companion.get('shotContext') or {}
        if ctx.get('gameId')!=args.game or str(ctx.get('playerId'))!=args.player or ctx.get('eventId')!=args.event:raise ValueError('Companion does not match selected game/player/event')
        deep['official'].update(ctx)
        for key in ['roster','playerProfiles','alignment','playByPlay','uniforms']:
            if key in companion:deep[key]=companion[key]
    video=dict(id=args.id,title=shots['teamName']+' · '+official['shooter']+' · '+shot['shotDesc'],duration=duration,source=args.source)
    frames=[]
    for i in range(18):
        t=round(.1+i*(duration-.3)/17,3)
        raw=subprocess.check_output([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-ss',str(t),'-i',str(args.video),'-frames:v','1','-vf','scale=960:-2','-q:v','5','-f','image2pipe','-vcodec','mjpeg','-'])
        frames.append(dict(time=t,image=base64.b64encode(raw).decode()))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    request=dict(mode='video',video=video,frames=frames)
    if companion:request['companion']=companion
    args.out.write_text(json.dumps(request,ensure_ascii=False))
    args.out.with_suffix('.metadata.json').write_text(json.dumps(dict(video=video,deepData=deep),ensure_ascii=False,indent=2))
    if args.prepare_only:
        print('Prepared',args.id,'request',args.out);return
    config=deployment_outputs()
    s3=aws_session().client('s3');key='videos/'+args.id+'.mp4'
    s3.upload_file(str(args.video),config['MediaBucket'],key,ExtraArgs={'ContentType':'video/mp4'})
    item=video|dict(key=key,deepData=deep,sha256=hashlib.sha256(args.video.read_bytes()).hexdigest(),
        publication=dict(basis=args.publication_basis,source=args.source))
    s3.put_object(Bucket=config['MediaBucket'],Key='library/'+args.id+'.json',Body=json.dumps(item,ensure_ascii=False).encode(),ContentType='application/json')
    print('Registered',args.id,'event',args.event,'request',args.out)

if __name__=='__main__':main()
