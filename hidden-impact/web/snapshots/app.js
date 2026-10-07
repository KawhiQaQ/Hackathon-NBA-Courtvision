const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (value, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : '—';
const meters = value => Number.isFinite(value) ? (value * .3048).toFixed(1) : '—';
const clock = seconds => `${Math.floor(seconds / 60).toString().padStart(2,'0')}:${Math.floor(seconds % 60).toString().padStart(2,'0')}`;
const shortName = name => String(name || '').split(' ').slice(-1)[0];
const shotTypes = {catchAndShoot:'接球投篮',dribblePullUp:'运球急停',layup:'上篮',dunk:'扣篮',floater:'抛投',postFadeaway:'背身后仰',hook:'勾手',tip:'补篮',stepback:'后撤步',offMove:'移动中投篮',lob:'空接',heave:'远距离出手',shakeAndRaise:'晃动后出手',leaner:'倾身投篮'};
const state = {catalog:[],data:null,scope:'top',search:'',outcome:'all',sort:'impact',shotId:null,playerId:null,view:'analysis',step:2,playing:false};
let timers = [], loadSequence = 0, toastTimer;

function toast(message, error = false) {
  clearTimeout(toastTimer); $('toast').textContent=message; $('toast').classList.toggle('error',error); $('toast').hidden=false;
  toastTimer=setTimeout(()=>{$('toast').hidden=true;},5000);
}
function banner(message) { $('status-banner').textContent=message; $('status-banner').hidden=!message; }
function selectedShot() { return state.data?.shots.find(s=>s.id===state.shotId); }
function selectedCandidate() { return selectedShot()?.analysis.candidates.find(c=>c.playerId===state.playerId); }
function stopStory() { timers.forEach(clearTimeout);timers=[];state.playing=false;$('explain-play').textContent='▷ 分步解读'; }
function updateHash() {
  if(state.data&&state.shotId)history.replaceState(null,'',`#${encodeURIComponent(state.data.game.id)}/${encodeURIComponent(state.shotId)}/${encodeURIComponent(state.playerId||'')}`);
}
async function loadGame(id, preferredShot, preferredPlayer) {
  const entry=state.catalog.find(g=>g.id===id);if(!entry)return;
  const sequence=++loadSequence;stopStory();$('workspace').setAttribute('aria-busy','true');banner('');
  try{
    const response=await fetch(entry.file);if(!response.ok)throw new Error(`比赛数据读取失败（${response.status}）`);
    const data=await response.json();if(sequence!==loadSequence)return;
    if(!Array.isArray(data.shots)||!data.shots.length)throw new Error('比赛没有可展示的出手机会。');
    state.data=data;state.shotId=preferredShot||null;state.playerId=preferredPlayer||null;
    $('game-select').value=id;
    if(preferredShot&&!visibleShots().some(s=>s.id===preferredShot)){state.scope='all';state.search='';state.outcome='all';$('search').value='';$('outcome').value='all';syncScope();}
    renderAll();
  }catch(error){if(sequence===loadSequence)banner(error.message+'。请刷新重试，或检查本地服务是否仍在运行。');}
  finally{if(sequence===loadSequence)$('workspace').setAttribute('aria-busy','false');}
}
function visibleShots() {
  if(!state.data)return [];
  let shots=state.data.shots.filter(s=>state.scope==='all'||s.analysis.eligible);
  if(state.outcome!=='all')shots=shots.filter(s=>s.outcome===state.outcome);
  if(state.search){const query=state.search.toLocaleLowerCase();shots=shots.filter(s=>[s.team,s.shooterName,...s.analysis.candidates.map(c=>c.name)].join(' ').toLocaleLowerCase().includes(query));}
  shots.sort((a,b)=>{
    if(state.sort==='time')return a.period-b.period||b.gameClock-a.gameClock||a.id.localeCompare(b.id);
    const key=state.sort==='quality'?'shotQuality':null;
    const av=key?a[key]:a.analysis.score,bv=key?b[key]:b.analysis.score;
    return (bv??-1)-(av??-1)||a.period-b.period||b.gameClock-a.gameClock;
  });
  return state.scope==='top'?shots.slice(0,10):shots;
}
function syncScope(){document.querySelectorAll('[data-scope]').forEach(b=>{b.classList.toggle('selected',b.dataset.scope===state.scope);b.setAttribute('aria-pressed',b.dataset.scope===state.scope);});}
function renderAll(){
  if(!state.data)return;
  document.querySelector('.source-chip').textContent=`${state.data.game.source} / ${state.data.game.competition}`;
  $('shot-count').textContent=state.data.stats.shots;$('eligible-count').textContent=state.data.stats.rankable;
  renderList();renderDetail();
}
function renderList(){
  const shots=visibleShots();$('list-count').textContent=`${shots.length} 个机会`;
  if(!shots.some(s=>s.id===state.shotId)){
    state.shotId=shots[0]?.id||null;state.playerId=null;stopStory();state.step=2;
  }
  $('shot-list').innerHTML=shots.length?shots.map((shot,i)=>{
    const candidate=shot.analysis.candidates[0];const active=shot.id===state.shotId;
    return `<button class="shot-item ${active?'selected':''}" data-shot="${esc(shot.id)}" aria-pressed="${active}" aria-label="第 ${i+1} 个机会，${esc(candidate?.name||shot.shooterName)}，指数 ${num(shot.analysis.score)}，第 ${shot.period} 节 ${clock(shot.gameClock)}"><div class="shot-topline"><span class="shot-rank">${String(i+1).padStart(2,'0')}</span><span>Q${shot.period} · ${clock(shot.gameClock)}</span><span class="result-pill ${shot.outcome==='missed'?'missed':''}">${shot.outcome==='made'?'命中':shot.outcome==='missed'?'未命中':'结果未知'}</span></div><div class="shot-row"><div class="shot-names"><strong>${esc(candidate?.name||shot.shooterName)}</strong><small>${candidate?'无球候选':'点位不足'} · ${esc(shot.team)}</small></div><span class="shot-value">${num(shot.analysis.score,0)}</span></div><div class="shot-mini-bar"><i style="width:${shot.analysis.score??0}%"></i></div></button>`;
  }).join(''):'<div class="empty-list">没有符合条件的机会。<br>试试其他筛选，或清空搜索。</div>';
}
function renderDetail(){
  const shot=selectedShot();
  if(!shot){
    $('play-title').textContent='没有匹配的出手机会';$('play-label').textContent='NO MATCHING SHOTS';$('play-clock').textContent='—';
    $('court').setAttribute('viewBox','0 0 600 530');$('court').innerHTML=courtBase(false);$('court-empty').textContent='暂无匹配机会';$('court-empty').hidden=false;
    $('impact-score').textContent='—';$('player-name').textContent='等待选择';$('player-jersey').textContent='—';
    $('quality-badge').textContent='没有匹配结果';$('quality-badge').className='quality-badge unknown';
    for(const id of ['components','evidence-list','candidates','quality-note','outcome-note'])$(id).textContent='';
    $('narrative').textContent='调整左侧筛选条件后继续查看。';
    for(const id of ['metric-quality','metric-distance','metric-outcome','metric-type'])$(id).textContent='—';
    $('export-btn').disabled=true;$('explain-play').disabled=true;return;
  }
  const analysis=shot.analysis;
  if(!analysis.candidates.some(c=>c.playerId===state.playerId))state.playerId=analysis.candidates[0]?.playerId||null;
  const candidate=selectedCandidate();
  $('export-btn').disabled=false;$('explain-play').disabled=!candidate;
  $('play-label').textContent=`${state.data.game.competition.toUpperCase()} / ${shot.team}`;
  $('play-title').textContent=`${shortName(shot.shooterName)} 的这次出手`;
  $('play-clock').textContent=`Q${shot.period}  ${clock(shot.gameClock)}`;
  $('metric-quality').innerHTML=`${num(shot.shotQuality)}<em>/ 100</em>`;
  $('metric-distance').innerHTML=`${meters(shot.defenderDistance)}<em>m</em>`;
  $('metric-outcome').textContent=shot.outcome==='made'?'命中':shot.outcome==='missed'?'未命中':'未知';
  $('metric-outcome').style.color=shot.outcome==='made'?'#476b44':'#b08567';
  $('metric-type').textContent=`${shot.points===3?'三分出手':shot.points===2?'两分出手':'出手'} · ${shotTypes[shot.shotType]||'投篮'}${shot.fouled?' · 被犯规':''}`;
  $('impact-score').textContent=num(candidate?.score,0);
  $('player-name').textContent=candidate?.name||'暂不评分';$('player-jersey').textContent=candidate?.jersey||'—';
  $('quality-badge').textContent=candidate&&!candidate.keyPointsReliable?'关键点位需谨慎':analysis.qualityLabel;
  $('quality-badge').className=`quality-badge ${candidate&&!candidate.keyPointsReliable?'low':analysis.quality}`;
  $('components').innerHTML=candidate?candidate.components.map(c=>`<div class="component"><div class="component-top"><span>${esc(c.label)}</span><strong>${num(c.points)}<span>/ ${c.weight}</span></strong></div><div class="component-track"><i style="width:${c.value}%"></i></div></div>`).join(''):'<p class="quality-note">补充完整出手点位后，才会生成分项评分。</p>';
  $('evidence-list').innerHTML=candidate?candidate.evidence.map(e=>`<div class="evidence-row"><div>${esc(e.label)}<small>${e.type==='computed'?'快照几何计算':'几何关联估计 · 非盯防标注'}</small></div><strong>${esc(e.value)}</strong></div>`).join(''):'';
  $('candidates').innerHTML=analysis.candidates.map(c=>`<button class="candidate-row ${c.playerId===state.playerId?'selected':''}" data-player="${esc(c.playerId)}" aria-pressed="${c.playerId===state.playerId}" aria-label="查看 ${esc(c.name)} 的贡献证据"><span class="candidate-num">${esc(c.jersey)}</span><span class="candidate-name">${esc(c.name)}</span><strong>${num(c.score)}</strong></button>`).join('');
  $('quality-note').textContent=analysis.warnings.length?analysis.warnings.join(' '):'空间关联线是几何估计，不表示实际盯防任务。快照无法证明跑动过程或战术因果。';
  if(candidate){
    $('narrative').textContent=`出手的是 ${shot.shooterName}，${candidate.name} 的无球站位也值得关注。出手瞬间，两人相距 ${meters(candidate.shooterSpacingFt)} 米，后者身边最近的防守人距离为 ${meters(candidate.nearestDefenderFt)} 米。这一空间关系提供了牵制作用的线索，但无法证明是他的跑动创造了机会。`;
  }else $('narrative').textContent=analysis.summary;
  $('outcome-note').textContent=analysis.outcomeNote||'缺失点位不会被填成零分，也不会生成虚构站位。';
  renderCourt();updateHash();
}
function courtBase(full){
  const bottom=full?944.6:485.3;
  const half=`<rect class="court-key" x="219.6" y="26" width="160.8" height="190.3"/><circle class="court-line" cx="300" cy="216.3" r="59.1"/><path class="court-line" d="M83.5 26V126.5 A221.5 221.5 0 0 0 516.5 126.5V26"/><path class="court-line" d="M259.5 79.5 A40.5 40.5 0 0 0 340.5 79.5"/><path class="court-rim" d="M270.5 65.4h59"/><circle class="court-rim" cx="300" cy="79.5" r="7.4"/>`;
  let lines='';for(let x=65;x<540;x+=22)lines+=`<path class="court-grain" d="M${x} 26V${bottom}"/>`;
  return `<defs><radialGradient id="spotlight"><stop stop-color="#d3ed84" stop-opacity=".14"/><stop offset="1" stop-color="#d3ed84" stop-opacity="0"/></radialGradient></defs><rect x="54" y="26" width="492.1" height="${bottom-26}" rx="2" class="court-floor"/>${lines}<rect x="54" y="26" width="492.1" height="${bottom-26}" class="court-line"/>${half}${full?`<g transform="translate(0,970.6) scale(1,-1)">${half}</g><path class="court-line" d="M54 485.3h492.1"/><circle class="court-line" cx="300" cy="485.3" r="59.1"/>`:'<path class="court-line" d="M240.9 485.3 A59.1 59.1 0 0 1 359.1 485.3"/>'}<text class="court-label" x="300" y="${bottom+25}" text-anchor="middle">${full?'FULL COURT':'HALF COURT'} / RELEASE SNAPSHOT</text><text class="court-label" x="300" y="16" text-anchor="middle">进攻方向 ↑</text>`;
}
function renderCourt(){
  const shot=selectedShot();if(!shot)return;const players=shot.players||[];
  const full=players.some(p=>p.x>1);const svg=$('court');svg.setAttribute('viewBox',`0 0 600 ${full?990:530}`);
  let html=courtBase(full);const candidate=selectedCandidate();const byId=Object.fromEntries(players.map(p=>[p.id,p]));
  const contributor=candidate?byId[candidate.playerId]:null;const shooter=byId[shot.shooterId];
  const position=p=>({x:300-p.y*10,y:26+(p.x+45.93)*10});
  const analysis=state.view==='analysis';const showCandidate=analysis&&state.step>=1;const showEvidence=analysis&&state.step>=2;
  if(contributor&&showCandidate){const p=position(contributor);html+=`<circle cx="${p.x}" cy="${p.y}" r="58" fill="url(#spotlight)"/><circle cx="${p.x}" cy="${p.y}" r="23" fill="none" stroke="#d3ed84" stroke-opacity=".32" stroke-width="1"/>`;}
  if(showEvidence&&contributor&&shooter){
    const a=position(contributor),b=position(shooter);
    html+=`<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="spacing-link"/><text x="${(a.x+b.x)/2+5}" y="${(a.y+b.y)/2-8}" class="distance-tag">间距 ${meters(candidate.shooterSpacingFt)} m</text>`;
    const link=candidate.links[0],defender=byId[link?.defenderId];
    if(defender){const d=position(defender);html+=`<line x1="${a.x}" y1="${a.y}" x2="${d.x}" y2="${d.y}" class="defense-link"/>`;}
  }
  // All points are the observed release snapshot. Nothing is animated as a player path.
  players.forEach(p=>{
    const point=position(p),isOffense=p.teamId===shot.offenseId,isShooter=p.id===shot.shooterId,isSelected=showCandidate&&p.id===state.playerId;
    const fill=isShooter?'#d89574':isSelected?'#d3ed84':isOffense?'#749786':'#1c342e';
    const stroke=isShooter?'#e6b69a':isSelected?'#e1f3aa':isOffense?'#8cad99':'#a0b4aa';
    const color=isOffense?'#18382d':'#c1d0c7';
    const role=isShooter?'出手者':isOffense?'无球队员':'防守方';
    html+=`<g class="player" data-player="${esc(p.id)}" ${isOffense?'tabindex="0" role="button"':''} aria-label="${esc(p.name)}，${esc(p.jersey)} 号，${role}${isOffense&&!isShooter?'，点击查看贡献证据':''}"><title>${esc(p.name)} · ${role}${p.detected===false?' · 外推点位':''}</title><circle cx="${point.x}" cy="${point.y}" r="${isSelected||isShooter?14:12}" fill="${fill}" stroke="${stroke}" stroke-width="1.3" ${p.detected===false?'stroke-dasharray="3 3"':''}/><text x="${point.x}" y="${point.y}" fill="${color}">${esc(p.jersey)}</text></g>`;
    if(isSelected||(isShooter&&analysis)){
      const label=`${isShooter?'出手 · ':''}${shortName(p.name)}`;const width=Math.min(140,Math.max(67,label.length*5.7+14));
      const lx=Math.min(600-width-8,Math.max(8,point.x-width/2));const ly=point.y<100?point.y+20:point.y-38;
      html+=`<g class="player-tag" pointer-events="none"><rect x="${lx}" y="${ly}" width="${width}" height="19" rx="4" ${isShooter?'style="fill:#e9bfa5"':''}/><text x="${lx+width/2}" y="${ly+13}" text-anchor="middle">${esc(label)}</text></g>`;
    }
  });
  svg.innerHTML=html;$('court-empty').innerHTML='缺少球员点位<br><small>保留投篮信息，不绘制虚构站位。</small>';$('court-empty').hidden=!!players.length;
  $('court-mode').textContent=state.view==='raw'?'出手瞬间 · 原始点位':['聚焦出手者','关注无球队员','出手瞬间 · 空间关系'][state.step];
  document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('selected',b.dataset.view===state.view);b.setAttribute('aria-pressed',b.dataset.view===state.view);});
  document.querySelectorAll('[data-step]').forEach(b=>{b.classList.toggle('selected',Number(b.dataset.step)===state.step&&analysis);b.setAttribute('aria-pressed',Number(b.dataset.step)===state.step&&analysis);});
}
function choosePlayer(id){
  const shot=selectedShot();if(!shot)return;
  if(id===shot.shooterId){stopStory();state.view='analysis';state.step=0;renderCourt();return;}
  if(!shot.analysis.candidates.some(c=>c.playerId===id))return;
  stopStory();state.playerId=id;state.view='analysis';state.step=2;renderDetail();
}
function downloadJson(name,data){const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function openMethod(){$('method-dialog').showModal();}
$('method-open').addEventListener('click',openMethod);$('score-help').addEventListener('click',openMethod);$('method-close').addEventListener('click',()=>$('method-dialog').close());
$('method-dialog').addEventListener('click',e=>{if(e.target===$('method-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
$('discover').addEventListener('click',()=>{$('workspace').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});});
$('game-select').addEventListener('change',e=>loadGame(e.target.value));
document.querySelectorAll('[data-scope]').forEach(b=>b.addEventListener('click',()=>{state.scope=b.dataset.scope;syncScope();stopStory();renderAll();}));
$('search').addEventListener('input',e=>{state.search=e.target.value.trim();stopStory();renderAll();});
$('outcome').addEventListener('change',e=>{state.outcome=e.target.value;stopStory();renderAll();});
$('sort').addEventListener('change',e=>{state.sort=e.target.value;stopStory();renderAll();});
$('shot-list').addEventListener('click',e=>{const b=e.target.closest('[data-shot]');if(!b)return;stopStory();state.shotId=b.dataset.shot;state.playerId=null;state.step=2;renderAll();});
$('candidates').addEventListener('click',e=>{const b=e.target.closest('[data-player]');if(b)choosePlayer(b.dataset.player);});
$('court').addEventListener('click',e=>{const b=e.target.closest('[data-player]');if(b)choosePlayer(b.dataset.player);});
$('court').addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){const b=e.target.closest('[data-player]');if(b){e.preventDefault();choosePlayer(b.dataset.player);}}});
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{stopStory();state.view=b.dataset.view;state.step=2;renderCourt();}));
document.querySelectorAll('[data-step]').forEach(b=>b.addEventListener('click',()=>{stopStory();state.view='analysis';state.step=Number(b.dataset.step);renderCourt();}));
$('explain-play').addEventListener('click',()=>{
  if(state.playing){stopStory();return;}stopStory();state.playing=true;state.view='analysis';state.step=0;renderCourt();$('explain-play').textContent='Ⅱ 暂停解读';
  timers.push(setTimeout(()=>{state.step=1;renderCourt();},1800),setTimeout(()=>{state.step=2;renderCourt();stopStory();},3600));
});
$('export-btn').addEventListener('click',()=>{const shot=selectedShot();if(shot){downloadJson(`hidden-impact-${shot.id}.json`,{schemaVersion:'1.0',game:state.data.game,shots:[shot],method:state.data.method});toast('已导出快照、分项评分和数据证据。');}});
$('schema-download').addEventListener('click',()=>{if(!state.data)return;const shot=structuredClone(selectedShot()||state.data.shots[0]);delete shot.analysis;downloadJson('snapshot-example.json',{schemaVersion:'1.0',game:state.data.game,shots:[shot]});toast('示例包含一张真实快照，可作为官方数据适配格式。');});
$('import-btn').addEventListener('click',()=>$('import-file').click());
$('import-file').addEventListener('change',async e=>{
  const file=e.target.files[0];if(!file)return;
  try{
    if(file.size>5*1024*1024)throw new Error('文件超过 5 MB。');
    const content=await file.text();JSON.parse(content);
    $('import-btn').disabled=true;
    const response=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:content,signal:AbortSignal.timeout(30000)});
    const type=response.headers.get('content-type')||'';
    if(!type.includes('application/json'))throw new Error('导入计算需要 Python 服务，请使用 python3 server.py 启动。');
    const data=await response.json();if(!response.ok)throw new Error(data.error||'分析失败。');
    ++loadSequence;stopStory();state.data=data;state.shotId=null;state.playerId=null;state.scope='all';state.search='';state.outcome='all';
    $('search').value='';$('outcome').value='all';syncScope();
    document.querySelector('option[data-imported]')?.remove();const option=new Option(`导入 · ${data.game.home} vs ${data.game.away}`,'imported');option.dataset.imported='true';$('game-select').add(option);$('game-select').value='imported';
    banner('当前为导入数据，计算完成后仅保存在浏览器内存中；刷新后回到内置样例。');$('workspace').setAttribute('aria-busy','false');renderAll();toast(`分析完成：${data.stats.shots} 次出手，${data.stats.rankable} 张快照可进入精选。`);
  }catch(error){toast(error instanceof SyntaxError?'不是有效的 JSON 文件。':error.message,true);}
  finally{$('import-btn').disabled=false;e.target.value='';}
});
async function start(){
  try{
    const response=await fetch('data/catalog.json');if(!response.ok)throw new Error('数据目录加载失败。');
    state.catalog=await response.json();$('game-select').innerHTML=state.catalog.map(g=>`<option value="${esc(g.id)}">${esc(g.home)} vs ${esc(g.away)} · ${esc(g.date)}</option>`).join('');
    let parts=[];try{parts=location.hash.slice(1).split('/').map(decodeURIComponent);}catch{}
    const id=state.catalog.some(g=>g.id===parts[0])?parts[0]:state.catalog[0].id;
    syncScope();await loadGame(id,parts[1],parts[2]);
  }catch(error){banner(error.message+' 请先执行 python3 scripts/build_data.py，再启动 python3 server.py。');$('workspace').setAttribute('aria-busy','false');}
}
start();
