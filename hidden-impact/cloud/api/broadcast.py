"""Data-backed broadcast cards; never invent missing values or temporal gravity."""
import math

def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def card_at(insights,time,duration):
    shot=insights.get('shot');gravity=insights.get('gravity')
    # A shot clock is video-relative only after explicit alignment. Otherwise
    # this is a possession summary, not a claim about the current video instant.
    aligned=insights.get('shotVideoTime')
    has_alignment=finite(aligned) and 0<=aligned<=duration
    show_shot=shot and (not gravity or not has_alignment or time>=max(0,aligned-2))
    if show_shot:
        p=shot.get('probability')
        if not finite(p) or not 0<=p<=1:return None
        lines=[insights.get('shooter') or '本回合出手者']
        if finite(shot.get('baseline')):
            lines.append(f"同场同人同类均值 {shot['baseline']*100:.1f}% · n={shot['sampleCount']}")
            lines.append(f"相对均值 {shot['deltaPercentagePoints']:+.1f} 个百分点")
        if finite(shot.get('expectedPoints')):lines.append(f"预期得分 {shot['expectedPoints']:.2f} 分")
        if has_alignment and time>=aligned+1 and shot.get('made') is not None:
            lines.append(('命中 +' + str(shot['points'])+' 分') if shot['made'] else '本次未命中')
        return dict(kind='shot',title='出手机会质量' if has_alignment else '本回合出手 · 数据回看',value=f'{p*100:.1f}%',
                    lines=lines,source=insights.get('probabilitySource','预期命中率'),fraction=p)
    if gravity:
        axis=next((a for a in gravity.get('axes',[]) if a.get('key')=='OFF_BALL_PERIM_GRAV' and finite(a.get('value'))),None)
        if axis:
            return dict(kind='gravity',title='无球外线引力 · 阶段画像',value=f"{axis['value']:+.2f}",
                        lines=[gravity.get('player',''),str(gravity.get('scope','阶段汇总')),'阶段汇总值，非回合实时测量'],source='NBA 深度赛场',fraction=None)
    return None
