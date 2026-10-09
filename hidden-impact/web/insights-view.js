// All numeric graphics are derived from the source-linked insight payload.
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = value => (value * 100).toFixed(1).replace(/\.0$/, '') + '%';
const signed = value => (value > 0 ? '+' : '') + value.toFixed(2);

export function cueAt(insights, time) {
  return insights.cues.find(c => time >= c.start && time < c.end) || {title:'回合画面',text:'',evidence:''};
}

export function narrationAt(insights, time) {
  return insights.narration?.segments?.find(s => time >= s.start && time < s.end) || cueAt(insights, time);
}

export function phaseMarkup(insights) {
  return insights.cues.map((c, i) => `<button data-cue="${i}" aria-label="回看${escapeHTML(c.phase)}"><small>0${i + 1}</small>${escapeHTML(c.phase)}<i></i></button>`).join('');
}

export function opportunityMarkup(insights) {
  const s = insights.shot;
  if(!s)return '';
  const compared=Number.isFinite(s.baseline)&&Number.isFinite(s.deltaPercentagePoints);
  const delta = s.deltaPercentagePoints;
  return `<div class="data-kicker">这一球的机会质量</div>
    <div class="opportunity-number"><strong>${pct(s.probability)}</strong><span>${escapeHTML(insights.probabilitySource||'官方预期命中率')}<br><b>${escapeHTML(insights.shooter||'出手者')} · ${s.points===3?'三分':'两分'}出手</b></span></div>
    <div class="quality-plot" role="img" aria-label="本次预期命中率${pct(s.probability)}${compared?`，同场同球员${s.sampleCount}次同类出手均值${pct(s.baseline)}`:''}">
      <div class="quality-row"><span>本次出手</span><div><i style="width:${s.probability * 100}%"></i></div><b>${pct(s.probability)}</b></div>
      ${compared?`<div class="quality-row baseline"><span>同场均值</span><div><i style="width:${s.baseline * 100}%"></i></div><b>${pct(s.baseline)}</b></div>`:''}
      <div class="quality-axis"><span>0%</span><span>50%</span><span>100%</span></div>
    </div>
    ${compared?`<div class="quality-conclusion"><b>${delta >= 0 ? '+' : '−'}${Math.abs(delta).toFixed(1)} <small>个百分点</small></b><span>相对同场 ${s.sampleCount} 次同类出手均值</span></div>
    <p class="data-note">对照包含本次出手；这不是分球前后的提升量。</p>`:''}
    <div class="outcome-pair"><div><span>出手预期得分</span><b>${s.expectedPoints.toFixed(2)} <small>分</small></b></div><div><span>实际结果</span><b>${s.made===null ? '—' : s.made ? '+' + s.points : '0'} <small>${s.made===null ? '结果未提供' : s.made ? '命中' : '未命中'}</small></b></div></div>`;
}

export function gravityMarkup(insights) {
  const g = insights.gravity;
  if(!g?.axes?.length)return '';
  const perimeter = g.axes.find(a => a.key === 'OFF_BALL_PERIM_GRAV');
  const reading = Number.isFinite(perimeter?.percentile) ? `<div class="gravity-reading"><b>无球外线引力 · 第 ${Math.round(perimeter.percentile)} 百分位</b><span>${perimeter.sampleCount} 名有效样本中的相对位置</span></div>` : '';
  const numbers = g.axes.flatMap(a => [a.value, a.teamMedian]).filter(Number.isFinite);
  const limit = Math.max(10, Math.ceil(Math.max(0, ...numbers.map(Math.abs)) / 10) * 10);
  const position = value => 50 + value / limit * 50;
  const rows = g.axes.map(a => {
    const valid = Number.isFinite(a.value);
    const medianValid = Number.isFinite(a.teamMedian);
    const end = valid ? position(a.value) : 50;
    return `<div class="gravity-row ${a.key === 'OFF_BALL_PERIM_GRAV' ? 'featured' : ''}"><span>${escapeHTML(a.label)}</span><div class="gravity-track"><i class="zero"></i>${valid ? `<i class="gravity-bar" style="left:${Math.min(50, end)}%;width:${Math.abs(end - 50)}%"></i>` : ''}${medianValid ? `<i class="median-marker" style="left:${position(a.teamMedian)}%" title="队内中位数 ${signed(a.teamMedian)}"></i>` : ''}</div><b>${valid ? signed(a.value) : '—'}</b></div>`;
  }).join('');
  return `<div class="data-kicker">出手球员的引力画像</div><h3>${escapeHTML(g.player)}</h3><p class="gravity-scope">${escapeHTML(g.scope)} · ${g.games ?? '—'} 场</p>
    <div class="gravity-chart" role="img" aria-label="五类阶段汇总引力，保留正负值，空心圆为队内中位数">${rows}<div class="gravity-axis"><span>−${limit}</span><span>0</span><span>+${limit}</span></div></div>
    <div class="gravity-key"><span><i></i>球员原始引力值</span><span><i class="median-dot"></i>${escapeHTML(g.comparison||'队内样本中位数')}</span></div>
    ${reading}
    <p class="data-note">${escapeHTML(g.note)}</p>`;
}

export function storyFact(insights, frame) {
  if(frame.fact)return frame.fact;
  if (frame.kind === 'shot' && insights.shot) return {label: '出手机会', value: pct(insights.shot.probability) + ' 预期命中率'};
  if (frame.kind === 'made' && insights.shot) return {label: '官方结果', value: insights.shot.made ? '+' + insights.shot.points + ' · 命中' : '未命中'};
  return {label: '画面线索', value: {setup:'接应位置',pressure:'防守向持球侧靠近',pass:'球转移至左侧外线'}[frame.kind] || '回合画面'};
}
