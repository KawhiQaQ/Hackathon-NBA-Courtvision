const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(v,d=1)=>Number.isFinite(v)?v.toFixed(d):'—';
export function scoreMarkup(impact){
 return (impact?.components||[]).map(c=>`<div class="score-factor"><div><span>${esc(c.label)}</span><b>${num(c.points)}<small>分</small></b></div><div class="factor-bar"><i style="width:${Math.max(0,Math.min(100,(c.value||0)*100))}%"></i></div><p>${esc(c.detail)}</p><small>${Math.round(c.weight/(impact.coverage||1))}% 权重</small></div>`).join('');
}
export function awardMarkup(game){
 const w=game.winner,leaders=game.leaders||[];
 if(!w)return `<div class="award-empty"><span>HIDDEN MVP</span><h3>${game.tie?'并列领先':'等待更多确认的回合'}</h3><p>${game.tie?leaders.map(p=>esc(p.label)).join(' · '):'确认球队、号码和贡献证据后，生成本场汇总。'}</p></div>`;
 return `<div class="award-stage"><div class="award-emblem"><svg viewBox="0 0 160 160" aria-hidden="true"><path d="M49 28h62v29c0 27-13 42-31 42S49 84 49 57V28ZM49 38H28v15c0 22 12 29 27 30M111 38h21v15c0 22-12 29-27 30M80 99v23M58 132h44M67 121h26" fill="none" stroke="currentColor" stroke-width="3"/><path d="m80 41 5 11 13 1-10 8 3 13-11-7-11 7 3-13-10-8 13-1Z" fill="currentColor"/></svg><span>HIDDEN IMPACT</span></div><div class="award-copy"><span class="winner-overline">${esc(game.team)} · 本场幕后 MVP</span><div class="winner-number">${esc(w.jersey)}<span>号</span></div><h3>把一次次配合，累积成全场价值。</h3><p>在 ${game.creditedRounds} 个已归属回合中，${w.wins} 次成为幕后MVP。</p></div><div class="award-stats"><div><span>本场综合指数</span><b>${num(w.gameScore)}<small>/100</small></b></div><div><span>回合贡献总分</span><b>${num(w.total)}</b></div><div><span>平均回合分</span><b>${num(w.average)}</b></div><div><span>回合 MVP</span><b>${w.wins}<small>次</small></b></div></div></div>`;
}
export function rankingMarkup(game){
 const max=Math.max(1,...game.ranking.map(p=>p.total));
 return `<div class="rank-labels"><span>球员 / 贡献累计</span><span>总分</span><span>均分</span><span>MVP 次数</span><span>综合指数</span></div>`+game.ranking.map(p=>`<div class="rank-row"><div class="rank-player"><span class="rank-index">${String(p.rank).padStart(2,'0')}</span><span class="rank-jersey">${esc(p.jersey)}</span><div><b>${esc(p.label)}</b><div class="rank-bar"><i style="width:${p.total/max*100}%"></i></div></div></div><b>${num(p.total)}</b><span>${num(p.average)}</span><span>${p.wins}<small>次</small></span><strong>${num(p.gameScore)}</strong><div class="rank-rounds">${p.rounds.map(key=>{const i=game.rounds.findIndex(r=>r.roundKey===key);return `<button data-round="${i}">回合 ${String(i+1).padStart(2,'0')} ↗</button>`;}).join('')}</div></div>`).join('');
}
