#!/usr/bin/env python3
"""Export multiple analyzed clips through the same renderer and game scoring code.
Project JSON: {gameId, team, rounds:[{analysis, video, jersey?}]}.
Paths resolve relative to the project file. Open /?result=results/game/game.json.
"""
import argparse,json,copy,sys
from pathlib import Path
from export_result import export
from game_summary import aggregate,identity


def export_game(project_path,out):
    path=Path(project_path);project=json.loads(path.read_text());out=Path(out)
    entries=project['rounds'];identity(project['team'],'0')
    if not isinstance(entries,list) or not 1<=len(entries)<=30:raise ValueError('Expected 1–30 analyzed clips')
    prepared=[]
    # Validate the entire collection before starting expensive rendering.
    for entry in entries:
        source=json.loads((path.parent/entry['analysis']).read_text());r=source.get('result',source.get('analysis',source))
        official=(r.get('deepData') or {}).get('official') or {}
        for key in ['gameId','team']:
            if official.get(key) and official[key]!=project[key]:raise ValueError('Mixed games or offensive teams')
        if entry.get('jersey') is not None:identity(project['team'],str(entry['jersey']))
        prepared.append((entry,r))
    rounds=[]
    for i,(entry,r) in enumerate(prepared):
        folder=f'round-{i+1:02d}';manifest=export(r,path.parent/entry['video'],out/folder)
        manifest.update(gameId=project['gameId'],team=project['team'])
        if entry.get('jersey') is not None:manifest['identity']={'jersey':str(entry['jersey']),'confirmed':True,'source':'user-confirmed-jersey'}
        (out/folder/'showcase.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        item=copy.deepcopy(manifest)
        for k in ['video','original','poster']:
            if item.get(k):item[k]=folder+'/'+item[k]
        for frame in item['evidence']:frame['image']=folder+'/'+frame['image']
        rounds.append(item)
    summary=aggregate(rounds,project['gameId'],project['team'])
    (out/'game.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--out',required=True);args=p.parse_args()
    export_game(args.project,args.out);print(Path(args.out)/'game.json')
