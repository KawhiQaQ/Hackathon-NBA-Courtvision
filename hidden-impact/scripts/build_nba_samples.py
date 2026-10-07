"""Small, cached sample of public NBA Inside the Game clips and matched shot records.
Only published public pages/endpoints; no login, scraping bypass or invented gravity.
"""
import base64,hashlib,json,subprocess,time,urllib.request,urllib.parse
from pathlib import Path
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'data/nba';RAW.mkdir(exist_ok=True)
VIDEO=ROOT/'data/videos/nba-public';VIDEO.mkdir(exist_ok=True)
FRAMES=ROOT/'data/frames/nba-public';FRAMES.mkdir(exist_ok=True)
POSTERS=ROOT/'web/posters';POSTERS.mkdir(exist_ok=True)
BASE='https://api.nba.cn/nba-web/api/web/inside/'
def request(path,params=None,cache=None):
 if cache and (RAW/cache).exists():return json.loads((RAW/cache).read_text())
 url=BASE+path+('?' +urllib.parse.urlencode(params) if params else '')
 with urllib.request.urlopen(url,timeout=30) as r:raw=json.load(r)
 if raw.get('code')!=0:raise ValueError('NBA source error '+str(raw.get('code')))
 if cache:(RAW/cache).write_text(json.dumps(raw['data'],ensure_ascii=False,indent=2))
 time.sleep(.25);return raw['data']
config=request('config',cache='config.json');gravity=request('season/playerGravity',{'season':'2025-26','seasonType':'Playoffs'},'gravity-2025-26-playoffs.json')['players']
# Begin with six officially featured, different shot events; no outcome filtering here.
selected=[r for r in config['topShot'] if r['gameId']=='0042500404' and r['eventId'] in [658,622,565,532,497,448]][:6]
if len(selected)<4:selected=config['topShot'][4:10]
for event in [428,197]:
 p=request('gpShot',{'gameId':'0042500404','playerId':'1628384'},'0042500404-1628384.json')
 sh=next(x for x in p['shotList'] if x['eventId']==event)
 selected.append({'gameId':'0042500404','playerId':'1628384','eventId':event,'newsId':sh['newsId']})
roster=[{'id':str(p['PLAYERID']),'name':p['FIRSTNAME']+' '+p['LASTNAME'],'team':'NYK' if '/NYK_' in p['lightLogo'] else 'SAS','gravity':{k:p[k] for k in ['OVERALL_GRAV','ON_BALL_PERIM_GRAV','ON_BALL_INTERIOR_GRAV','OFF_BALL_PERIM_GRAV','OFF_BALL_INTERIOR_GRAV']},'games':p['GP']} for p in gravity if '/NYK_' in p['lightLogo'] or '/SAS_' in p['lightLogo']]
catalog=[];ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
for rec in selected:
 game,player,event=rec['gameId'],rec['playerId'],rec['eventId'];id=f'nba-{game}-{event}';playerdata=request('gpShot',{'gameId':game,'playerId':player},f'{game}-{player}.json');shot=next(s for s in playerdata['shotList'] if s['eventId']==event)
 info=request('videoPlay',{'gameId':game,'eventId':event,'newsId':rec['newsId']})
 out=VIDEO/f'{id}.mp4'
 if not out.exists():
  subprocess.run([ffmpeg,'-y','-loglevel','error','-i',info['url'],'-vf','scale=1280:-2','-c:v','libx264','-preset','fast','-crf','24','-c:a','aac','-b:a','96k','-movflags','+faststart',str(out)],check=True,stdout=subprocess.DEVNULL)
 reader=imageio_ffmpeg.read_frames(str(out));meta=next(reader);reader.close();duration=meta['duration']
 payloadframes=[]
 for i in range(18):
  t=round(.1+i*(min(duration,30)-.3)/17,2);p=FRAMES/f'{id}-{i:02}.jpg'
  if not p.exists():subprocess.run([ffmpeg,'-y','-loglevel','error','-ss',str(t),'-i',str(out),'-frames:v','1','-vf','scale=960:-2','-q:v','5',str(p)],check=True,stdout=subprocess.DEVNULL)
  payloadframes.append({'time':t,'image':base64.b64encode(p.read_bytes()).decode()})
 (POSTERS/f'{id}.jpg').write_bytes((FRAMES/f'{id}-04.jpg').read_bytes())
 title=playerdata['playerFirstName']+' '+playerdata['playerLastName']+' · '+shot['shotDesc']
 official={'source':'NBA China · Inside the Game','url':f'https://china.nba.cn/inside-the-game/video/{player}?gameId={game}&playerId={player}',
  'gameId':game,'eventId':event,'playerId':player,'shooter':playerdata['playerFirstName']+' '+playerdata['playerLastName'],'team':playerdata['teamName'],'date':playerdata['gameDate'],'matchup':playerdata['matchup'],
  'shot':shot,'gravityScope':'2025-26 Playoffs player aggregate; NOT per-possession gravity','rosterGravity':roster,'capturedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 video={'id':id,'title':title,'duration':duration,'source':official['source']}
 payload={'video':video,'frames':payloadframes,'deepData':{'videoId':id,'official':official}}
 (FRAMES/f'{id}-request.json').write_text(json.dumps(payload,ensure_ascii=False))
 entry=video|{'poster':f'posters/{id}.jpg','official':official,'key':f'videos/{id}.mp4','deepData':payload['deepData'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
 catalog.append(entry);print(id,'duration',duration,'quality',shot['value'],flush=True)
(ROOT/'web/data/nba-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2))
