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
  const compared=Number.isFinite(s.baseline);
  const delta = compared ? (s.probability-s.baseline)*100 : null;
  return `<div class="data-kicker">这一球的机会质量</div>
    <div class="opportunity-number"><div class="probability-dial" role="img" aria-label="预期命中率 ${pct(s.probability)}"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="dial-track" cx="60" cy="60" r="51"/><circle class="dial-value" cx="60" cy="60" r="51" pathLength="100" stroke-dasharray="${s.probability*100} 100"/>${compared?`<circle class="dial-baseline" cx="60" cy="60" r="43" pathLength="100" stroke-dasharray="${s.baseline*100} 100"/>`:''}</svg><strong>${pct(s.probability)}</strong></div><span>${escapeHTML(insights.probabilitySource||'官方预期命中率')}<br><b>${escapeHTML(insights.shooter||'出手者')} · ${s.points===3?'三分':'两分'}出手</b></span></div>
    <div class="quality-plot" role="img" aria-label="本次预期命中率${pct(s.probability)}${compared?`，同场同球员${s.sampleCount}次同类出手均值${pct(s.baseline)}`:''}">
      <div class="quality-row"><span>本次出手</span><div><i style="width:${s.probability * 100}%"></i></div><b>${pct(s.probability)}</b></div>
      ${compared?`<div class="quality-row baseline"><span>同场均值</span><div><i style="width:${s.baseline * 100}%"></i></div><b>${pct(s.baseline)}</b></div>`:''}
      <div class="quality-axis"><span>0%</span><span>50%</span><span>100%</span></div>
    </div>
    ${compared?`<div class="quality-conclusion ${delta>0?'gain':delta<0?'loss':'neutral'}"><b><i aria-hidden="true">${delta>0?'↗':delta<0?'↘':'→'}</i> ${delta >= 0 ? '+' : '−'}${Math.abs(delta).toFixed(1)} <small>个百分点</small></b><span>相对同场 ${s.sampleCount} 次同类出手均值</span></div>
    <p class="data-note">对照包含本次出手；这不是分球前后的提升量。</p>`:''}
    <div class="outcome-pair outcome-bars"><div><span>出手预期得分</span><b>${s.expectedPoints.toFixed(2)} <small>分</small></b><div class="outcome-meter"><i style="width:${s.probability*100}%"></i></div></div><div><span>实际结果</span><b>${s.made===null ? '—' : s.made ? '+' + s.points : '0'} <small>${s.made===null ? '结果未提供' : s.made ? '命中' : '未命中'}</small></b>${typeof s.made==='boolean'?`<div class="outcome-meter actual"><i style="width:${s.made?100:0}%"></i></div>`:''}</div></div>`;
}

function actorMarkup(a) {
  const f=a.finishing;
  const impactRows=[['创造机会影响力',a.creation],['投篮得分影响力',a.scoring]];
  const values=impactRows.map(r=>r[1]).filter(Number.isFinite);
  const lo=Math.min(0,...values),hi=Math.max(0,...values),range=hi-lo||1;
  const zero=(0-lo)/range*100;
  const impacts=impactRows.map(([label,value])=>`<div class="impact-compare-row"><span>${label}</span><div class="impact-track"><i class="impact-zero" style="left:${zero}%"></i>${Number.isFinite(value)?`<i class="impact-fill" style="left:${Math.min(zero,(value-lo)/range*100)}%;width:${Math.abs(value)/range*100}%"></i>`:''}</div><b>${Number.isFinite(value)?signed(value):'—'}</b></div>`).join('');
  const history=(f?.history||[]).filter(h=>typeof h.made==='boolean');
  const shots=history.length?`<div class="shot-ledger" role="img" aria-label="按时间排序的此前出手：${history.map(h=>h.made?'命中':'未命中').join('、')}">${history.map((h,i)=>`<span class="shot-token ${h.made?'made':'miss'}" title="第 ${i+1} 次出手 · ${h.made?'命中':'未命中'}"><i>${h.made?'●':'×'}</i><small>${String(i+1).padStart(2,'0')}</small></span>`).join('')}<span class="shot-ledger-key">实心 · 命中<br>空心 · 未中</span></div>`:'';
  return `<div class="data-kicker">幕后MVP的贡献线索</div><h3>${escapeHTML(a.name)}</h3>
    <p class="gravity-scope">${escapeHTML(a.scope)} · ${escapeHTML(a.games ?? '—')} 场</p>
    <div class="impact-compare" role="img" aria-label="创造机会与投篮得分的阶段影响力">${impacts}</div>
    <p class="data-note">官方影响力的不同组成项；用于说明得分之外的价值，不是本回合贡献分。</p>
    ${f?`<div class="gravity-reading"><b>此回合前：${f.shotType==='3分投篮'?'三分':'两分'} ${f.sampleCount} 投 ${f.made} 中</b><span>终结威胁 · ${pct(f.actual)}</span></div>${shots}
    <div class="quality-plot"><div class="quality-row"><span>实际命中</span><div><i style="width:${f.actual*100}%"></i></div><b>${pct(f.actual)}</b></div>${Number.isFinite(f.expected)?`<div class="quality-row baseline"><span>官方预期</span><div><i style="width:${f.expected*100}%"></i></div><b>${pct(f.expected)}</b></div>`:''}<div class="quality-axis"><span>0%</span><span>50%</span><span>100%</span></div></div>
    <p class="data-note">同场先前${f.shotType==='3分投篮'?'三分':'两分'}出手。终结表现提供背景，防守是否受牵制仍需回看画面。</p>`:''}`;
}

export function gravityMarkup(insights) {
  if(insights.actorProfile)return actorMarkup(insights.actorProfile);
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
