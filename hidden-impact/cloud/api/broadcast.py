"""Compact, source-backed comparisons for broadcast overlays."""
import math


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def comparison(kind, title, subject, value, baseline, labels, unit, context):
    rows = []
    if finite(baseline):
        rows.append(dict(label=labels[0], value=baseline, baseline=True))
    rows.append(dict(label=labels[1], value=value, baseline=False))
    # Probability always uses 0–100%; signed gravity shares one zero and scale.
    values = [r['value'] for r in rows]
    domain = [0, 100] if kind in ('shot', 'actor-finishing') else [min(0, min(values)), max(0, max(values))]
    if domain[0] == domain[1]:
        domain = [-1, 1]
    delta = value - baseline if finite(baseline) else None
    return dict(kind=kind, title=title, subject=subject, rows=rows, domain=domain,
                delta=delta, unit=unit, context=context, outcome=None)


def actor_card(profile, time, switch_time):
    if not profile:return None
    creation=profile.get('creation');scoring=profile.get('scoring');finishing=profile.get('finishing')
    if finite(creation) and finite(scoring) and (time < switch_time / 2 or not finishing):
        c=comparison('actor-creation','主角不止得分',profile['name'],creation,scoring,
                     ('投篮得分','创造机会'),'影响力',f"{profile.get('scope','阶段汇总')} · {profile.get('games','—')} 场")
        # These are two components, not before/after or a causal uplift.
        c.update(delta=None,headline=f'{creation:+.2f}',headlineUnit='创造机会影响力',accent='#f4c45e')
        return c
    if finishing:
        c=comparison('actor-finishing','主角的终结威胁',profile['name'],finishing['actual']*100,finishing['expected']*100 if finite(finishing.get('expected')) else None,
                     ('官方预期','实际命中'),'个百分点','本回合前 · 同场'+('三分' if finishing.get('shotType')=='3分投篮' else '两分')+'出手')
        c.update(delta=None,headline=f"{finishing['made']} / {finishing['sampleCount']}",headlineUnit='三分命中' if finishing.get('shotType')=='3分投篮' else '两分命中',history=finishing.get('history',[]),accent='#f4c45e')
        return c
    return None


def card_at(insights, time, duration):
    shot = insights.get('shot'); gravity = insights.get('gravity')
    aligned = insights.get('shotVideoTime')
    has_alignment = finite(aligned) and 0 <= aligned <= duration
    # Leave enough time to read the comparison before the finish, without
    # describing a historical shot estimate as a live probability trajectory.
    switch_time=max(0,aligned-5) if has_alignment else 0
    if has_alignment and time<switch_time:
        actor=actor_card(insights.get('actorProfile'),time,switch_time)
        if actor:return actor
    show_shot = shot and (not gravity or not has_alignment or time >= max(0, aligned - 5))
    if show_shot:
        p = shot.get('probability')
        if not finite(p) or not 0 <= p <= 1:
            return None
        baseline = shot.get('baseline')
        baseline = baseline * 100 if finite(baseline) and 0 <= baseline <= 1 else None
        card = comparison('shot', '预期命中率' if has_alignment else '预期命中率 · 数据回看',
                          insights.get('shooter') or '本回合出手者', p * 100, baseline,
                          ('同场均值', '本次出手'), '个百分点', '同人同类出手 · '+('配套预期值' if insights.get('probabilitySource','').startswith('配套') else '官方预期值'))
        if has_alignment and time >= aligned + 1 and isinstance(shot.get('made'), bool):
            points = shot.get('points')
            card['outcome'] = f'命中 +{points} 分' if shot['made'] and points in (2, 3) else ('命中' if shot['made'] else '未命中')
        return card
    if gravity:
        # A specialized metric requires an explicit, player-bound time window.
        # Without one, describe the overall profile rather than guessing possession.
        titles = {'OVERALL_GRAV': '总体引力', 'ON_BALL_PERIM_GRAV': '持球外线引力',
                  'ON_BALL_INTERIOR_GRAV': '持球内线引力', 'OFF_BALL_PERIM_GRAV': '无球外线引力',
                  'OFF_BALL_INTERIOR_GRAV': '无球内线引力'}
        context = next((c for c in insights.get('gravityContexts', [])
                        if c.get('playerId') and str(c['playerId']) == str(gravity.get('playerId'))
                        and finite(c.get('start')) and finite(c.get('end'))
                        and 0 <= c['start'] <= time < c['end'] <= duration
                        and c.get('metric') in titles), None)
        key = context['metric'] if context else 'OVERALL_GRAV'
        axis = next((a for a in gravity.get('axes', []) if a.get('key') == key and finite(a.get('value'))), None)
        if axis:
            return comparison('gravity', titles[key], gravity.get('player') or '球员',
                              axis['value'], axis.get('teamMedian'), ('队内中位', '球员画像'),
                              '引力值', '赛季阶段画像 · 非本回合增益')
    return None
