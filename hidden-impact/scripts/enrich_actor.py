"""Fetch source-linked actor profiles; optionally enrich our registered clip library."""
import argparse,json,datetime
from pathlib import Path
from ingest_official import fetch
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--player',required=True);p.add_argument('--game',required=True);p.add_argument('--season',default='2025-26');p.add_argument('--upload',action='store_true');a=p.parse_args()
 shots,shot_url=fetch('gpShot',dict(gameId=a.game,playerId=a.player))
 table,leverage_url=fetch('season/playerLeverage',dict(season=a.season,seasonType='Regular Season'))
 row=next(r for r in table['players'] if str(r['PLAYERID'])==a.player)
 if str(shots['playerId'])!=a.player or shots['gameId']!=a.game:raise ValueError('Mismatched NBA profile')
 profile=dict(playerId=a.player,gameId=a.game,name=row['FIRSTNAME']+' '+row['LASTNAME'],scope=a.season+' 常规赛',leverage=row,shots=shots,sources=[shot_url,leverage_url],capturedAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
 out=ROOT/'data/reference'/f'{a.video}-actor-profile.json';out.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n')
 if a.upload:
  import boto3
  cfg=json.loads((ROOT/'infra/cdk-outputs.json').read_text())['HiddenImpactTeam14'];session=boto3.Session(profile_name='nba',region_name='us-east-1')
  if cfg['AgentRuntimeArn'].split(':')[4]!=session.client('sts').get_caller_identity()['Account']:raise ValueError('Wrong AWS account')
  s3=session.client('s3');key='library/'+a.video+'.json';bucket=cfg['MediaBucket']
  item=json.loads(s3.get_object(Bucket=bucket,Key=key)['Body'].read());deep=item['deepData']
  if deep['videoId']!=a.video or deep['official']['gameId']!=a.game:raise ValueError('Wrong video/game')
  profiles=[r for r in deep.get('playerProfiles',[]) if r['playerId']!=a.player];profiles.append(profile);deep['playerProfiles']=profiles
  deep['sources']=list(dict.fromkeys(deep.get('sources',[])+profile['sources']))
  s3.put_object(Bucket=bucket,Key=key,Body=json.dumps(item,ensure_ascii=False).encode(),ContentType='application/json')
 print('Actor profile saved:',out.name,'uploaded:',a.upload)
if __name__=='__main__':main()
