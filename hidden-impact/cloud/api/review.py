"""Corrections from visual review, scoped to an exact model run, not a whole clip."""
import copy

REJECTIONS = {
    '1b7de85f8ecb74cd4ead103c9bef6f4e': {
        'status': 'rejected',
        'method': 'visual-frame-review',
        'reason': '所引用画面中的32号位于弧顶至禁区附近，不在出手者所在底角；模型所述底角掩护及球员ID不匹配，已撤下评分。',
        'frameTimes': [6.23, 7.76],
    },
    'abdcfc6f6cc30d577ea20bdef14c215d': {
        'status': 'rejected',
        'method': 'visual-frame-review',
        'reason': '模型给出的32号球员身份ID不匹配；引用画面及人物框不足以支持所描述的掩护与弱侧牵制，已撤下候选评分。',
        'frameTimes': [3.0, 4.74],
    },
    'b275ce7b4e99e9f8d07973a4b6fc67f2': {
        'status': 'rejected',
        'method': 'visual-frame-review',
        'reason': '引用的6.31秒和7.86秒画面不支持“44号在底角为阿努诺比完成掩护”的描述，已撤下该归因及评分。',
        'frameTimes': [6.31, 7.86],
    },
    '6d19f03b58941f8de021367f5db55ea3': {
        'status': 'rejected',
        'method': 'visual-frame-review',
        'reason': '关键帧中的白衣8号是最终出手者。模型将其误认成无球贡献者，并给出了不匹配的球员ID，已撤下该归因及评分。',
        'frameTimes': [7.49, 8.31, 9.13],
    }
}


def reviewed_result(result):
    """Keep the original stored result intact; return its current reviewed view."""
    output = copy.deepcopy(result)
    # Recompute only deterministic scoring on preserved measured inputs. No new VLM call.
    if output.get('scoringVersion')!='temporal-impact-v5' and output.get('version')=='basketball-roster-v3' and output.get('cropClassification') and output.get('vision',{}).get('roster'):
        from basketball import player_reports,SCORING_VERSION
        if output.get('scoringVersion')!=SCORING_VERSION:
            output['players'],output['events']=player_reports(output['vision']['roster'],output['vision'],(output.get('deepData') or {}).get('companion'))
            output['scoringVersion']=SCORING_VERSION
    review = REJECTIONS.get(output.get('job'))
    if review:
        output.update(review=review, events=[], thumbnails=[],
                      overview='该片段的模型归因未通过画面核验，暂不提供无球贡献评分。')
    else:
        output.setdefault('review', {'status': 'unverified', 'reason': '模型候选分析，需结合视频核验。'})
    return output
