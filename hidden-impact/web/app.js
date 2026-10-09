const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=(n,d=1)=>Number.isFinite(n)?n.toFixed(d):'—',clock=n=>`${Math.floor(n/60).toString().padStart(2,'0')}:${Math.floor(n%60).toString().padStart(2,'0')}`;
const state={videos:[],id:null,eventId:null,project:null,results:new Map(),frames:new Map(),companion:new Map(),connected:false,busy:false,sort:'rank',stopAt:null,reviews:{},offline:false,localURLs:new Map()};
let toastTimer,loadVersion=0,animation=0;
const selected=()=>state.videos.find(x=>x.id===state.id),result=()=>state.results.get(state.id),currentEvent=()=>state.playerId?result()?.events?.find(e=>e.actorTrackId===state.playerId):result()?.events?.find(e=>e.id===state.eventId)||result()?.events?.[0];
function toast(text){clearTimeout(toastTimer);$('toast').textContent=text;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,6000);}
function status(text,progress=0,error=false){$('status').hidden=!text;$('status-text').textContent=text;$('progress').value=progress;$('status').classList.toggle('error',error);}
function step(n){[1,2,3].forEach(i=>$('step-'+i).classList.toggle('active',i===n));}
function setConnected(ok){state.connected=ok;$('connect').classList.toggle('connected',ok);$('connection-label').textContent=state.offline?'工作区就绪':ok?'团队云端已连接':'连接云端';}
async function api(path,options={}){const res=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json','X-Team-Key':sessionStorage.getItem('hi-team-key')||'',...options.headers},signal:AbortSignal.timeout(45000)});let data;try{data=await res.json();}catch{throw new Error('服务暂未返回有效响应，请重试。');}if(!res.ok){if(res.status===401)setConnected(false);throw new Error(data.error||`请求失败（${res.status}）`);}return data;}
async function ensureConnected(){if(state.offline)return true;if(state.connected)return true;try{await api('/session');setConnected(true);return true;}catch{$('login-dialog').showModal();return false;}}
function reviewed(r){if(r.demo&&state.offline)return r;if(r.scoringVersion==='temporal-impact-v5'&&r.verificationVersion!=='focused-outcome-v2')return {...r,events:[],players:(r.players||[]).map(p=>({...p,score:null,status:p.role==='defense'?'defense':'insufficient',reason:'旧结果未核验最终出手者，请重新分析。',measurement:undefined})),overview:'请重新分析：旧结果未排除本回合最终出手者。'};if(r.version!=='basketball-roster-v3'||!r.cropClassification)return {...r,vision:null,players:undefined,events:[],overview:'这是旧版分析，尚无逐人报告。点击「重新分析」运行新版球员筛选与空间分析。'};const review=state.reviews[r.job];const current=review?{...r,events:[],players:(r.players||[]).map(p=>({...p,score:null,status:'insufficient',reason:'本次归因未通过画面核验。'})),review,overview:'该模型归因未通过画面核验。'}:r;return {...current,players:current.players?.map(p=>p.score===0&&!p.diagnostics?{...p,score:null,status:'insufficient',reason:'旧评分未区分证据不足与零信号；打开历史项目可获取修正报告。'}:p)};}
function projects(){try{return JSON.parse(localStorage.getItem('hi-projects-v2')||'[]');}catch{return [];}}
function saveProject(pending){if(!state.project)return;const all=projects(),old=all.find(p=>p.id===state.project)||{};const p={...old,id:state.project,title:state.videos[0]?.title||'视频分析',videos:state.videos,companion:[...state.companion],updatedAt:new Date().toISOString(),jobs:[...state.results].filter(([,r])=>r.job).map(([id,r])=>({id,job:r.job})),pending:pending===undefined?old.pending:pending};try{localStorage.setItem('hi-projects-v2',JSON.stringify([p,...all.filter(x=>x.id!==p.id)].slice(0,20)));localStorage.setItem('hi-results-v2',JSON.stringify([...state.results].slice(-8)));}catch{toast('浏览器存储已满，云端任务仍保留，可导出结果。');}}
function newProject(){if($('offline-preview'))$('offline-preview').hidden=true;if(state.busy||state.batch)return toast('请等待当前分析完成。');$('video').pause();$('video').removeAttribute('src');$('video').load();state.videos=[];state.id=null;state.project=null;state.results=new Map();state.frames=new Map();state.companion=new Map();$('workspace').hidden=true;$('welcome').hidden=false;status('');step(1);history.replaceState(null,'',location.pathname);}
function setBusy(on){state.busy=on;if(on){$('analyze-btn').textContent='正在处理…';$('impact-content').innerHTML='<div class="empty-next"><b>正在建立证据链</b>完成后在这里查看贡献候选、空间变化与证据质量。</div>';} for(const id of ['analyze-btn','all-analysis','add-video','attach-data','remove-data','home-btn','history-btn','game-summary'])$(id).disabled=on||state.batch;renderList();}
function ordered(){const items=[...state.videos];if(state.sort==='rank')items.sort((a,b)=>(state.results.get(b.id)?.events?.[0]?.score??-1)-(state.results.get(a.id)?.events?.[0]?.score??-1));const n=Number($('top-n').value);return n?items.slice(0,n):items;}
function renderList(){$('event-count').textContent=state.videos.length;$('project-count').textContent=`${state.videos.length} 段已导入视频`;$('event-list').innerHTML=ordered().map((v,i)=>{const r=state.results.get(v.id),e=r?.events?.[0];return `<button class="event-card ${v.id===state.id?'selected':''}" data-video="${esc(v.id)}" ${state.busy||state.batch?'disabled':''}><div class="event-card-head"><span>${String(i+1).padStart(2,'0')} · ${clock(v.duration)}</span><span>${r?'已分析':'已就绪'}</span></div><h3>${esc(e?.title||v.title)}</h3><div class="event-card-bottom"><span>${esc(e?.actor||(r?.players?`${r.players.length} 位球员 · 点击查看`:(r?'旧版结果 · 建议重新分析':'等待开始分析')))}</span><b>${num(e?.score,0)}</b></div></button>`;}).join('');$('rank-sort').classList.toggle('active',state.sort==='rank');$('time-sort').classList.toggle('active',state.sort==='time');}
function chart(m){const rows=m.series||[];if(rows.length<2)return '';const lo=rows[0].time,span=rows.at(-1).time-lo,max=Math.max(1,...rows.map(x=>x.separation));return `<svg class="measurement-chart" viewBox="0 0 230 75" role="img" aria-label="收益队友与防守者的画面间距随时间变化"><path d="M8 60H225" stroke="#dce5d6" fill="none"/><polyline points="${rows.map(r=>`${8+(r.time-lo)/span*215},${58-r.separation/max*47}`).join(' ')}" fill="none" stroke="#7a9c59" stroke-width="2"/><text x="8" y="74" fill="#9aaa90" font-size="8">${num(lo)}s</text><text x="190" y="74" fill="#9aaa90" font-size="8">${num(rows.at(-1).time)}s</text></svg>`;}
function render(){renderList();const item=selected();if(!item)return;const r=result();if(r?.players?.length&&!r.players.some(p=>p.id===state.playerId))state.playerId=r.focusPlayerId||(rankedPlayers(r)[0]||r.players[0]).id;const e=currentEvent(),official=item.official||r?.deepData?.official,shot=official?.shot,m=e?.measurement;
 $('project-title').textContent='幕后 MVP 分析';$('source-title').textContent='素材 · '+item.title;$('video-title').textContent='比赛视频';$('input-video').textContent=`视频已就绪 · ${num(item.duration)} 秒`;
 const companion=state.companion.get(item.id);$('input-data').textContent=companion?`配套数据：${companion.source}`:official?'已匹配官方出手记录':'未添加配套数据 · 可仅分析视频';$('remove-data').hidden=!companion;
 $('play-range').textContent=e?`${clock(e.start)} – ${clock(e.end)}`:`全片 ${num(item.duration)} 秒`;$('replay-btn').disabled=!e;$('analyze-btn').textContent=r?'重新分析':'开始分析';$('metrics-row').hidden=!shot;
 $('shot-quality').textContent=num(shot?.value*100);$('shot-outcome').textContent=shot?(shot.success?'命中':'未命中'):'—';$('shot-clock').textContent=shot?`Q${shot.period} ${shot.gameClock}`:'—';
 $('evidence-section').hidden=!r;['vision','vlm','score'].forEach(k=>$('stage-'+k).className=r?'done':'');
 $('impact-content').innerHTML=e?`<div class="score-block"><span class="score-label">HIDDEN IMPACT · CANDIDATE</span><div class="score-value"><strong>${num(e.score,0)}</strong><span>/ 100</span></div><h3 class="actor-name">${esc(e.actor)}</h3><p class="actor-role">${esc(e.actorTrackId||'')} · 战术角色待核验</p><div class="result-quality">证据质量 ${num(m?.quality*100,0)}% · 独立于贡献大小</div></div>`:`<div class="empty-next"><b>${r?'暂不归因':'素材准备好了'}</b>${r?(r.vision?'已生成视觉定位。还没有足够可靠的无球动作证据，可查看关键帧核验。':'当前没有可评分的贡献候选。'):'点击「开始分析」，依次完成人物检测、战术理解和空间评分。'}</div>`;
 $('impact-details').innerHTML=e?`<div class="contribution-bars">${(e.components||[]).map(c=>`<div class="bar-row"><div class="bar-label"><span>${esc(c.label)}</span><b>${num(c.points)} / ${c.weight}</b></div><div class="bar-track"><i style="width:${c.points/c.weight*100}%"></i></div></div>`).join('')}</div>${m?`<div class="measurement"><strong>机会形成前后</strong><div class="metric-pair"><span>防守间距</span><b>${num(m.separationBefore)} → ${num(m.separationAfter)}</b></div><div class="metric-pair"><span>优势保持</span><b>${num(m.sustainedSeconds)} 秒</b></div>${chart(m)}<small>单位：画面中人物高度倍数</small>${m.expectedPointsChange!==null?`<p>配套数据预期分变化：${num(m.expectedPointsChange,2)}（不代表个人因果增益）</p>`:''}</div>`:''}<p class="score-warning">${esc(m?.reason||e.caveat)}</p>`:'';
 if(shot)$('impact-details').innerHTML+=`<div class="gravity-card"><h3>对应出手 · ${esc(official.shooter)}</h3><small>官方出手记录用于情境核对，不因进球自动加分。</small></div>`;
 $('insight-title').textContent=e?.title||(r?.vision?'视觉检查完成':'分析结果');$('narrative').textContent=e?e.summary:r?.review?.status==='rejected'?r.review.reason:r?.overview||'';
 $('insight-meta').textContent=r?`${r.vision?'YOLOX-S + ':''}Qwen3-VL · ${r.frameTimes?.length||0} 张关键帧${r.vision?' · '+r.vision.frames.length+' 帧视觉检测':''}`:'';
 const observations=e?.observations||r?.vision?.frames.filter(f=>(r.frameTimes||[]).filter((_,i)=>[2,6,10,14].includes(i)).some(t=>Math.abs(t-f.time)<.001)).map(f=>({time:f.time,text:`检测到 ${f.people.length} 个人物候选 · 点击检查编号与位置`}))||[];
 $('frame-count').textContent=e?'动作前后对照 · 点击回放':'人物定位检查';$('frame-list').innerHTML=observations.map((o,i)=>{const frames=state.frames.get(item.id),f=frames?.find(x=>Math.abs(x.time-o.time)<.12),thumb=r?.thumbnails?.find(x=>Math.abs(x.time-o.time)<.12),src=f?'data:image/jpeg;base64,'+f.image:thumb?.url;return `<button class="frame-card" data-time="${o.time}"><div class="frame-image">${src?`<img src="${esc(src)}" alt="关键帧">`:''}<span>${num(o.time,2)}s</span><span class="frame-caption">${e?'证据':'视觉检查'} ${i+1}</span></div><p>${esc(o.text)}</p></button>`;}).join('')||'<div class="inline-empty">未发现足够证据，不生成虚构的贡献事件。</div>';
 $('timeline').innerHTML=(r?.events||[]).map(x=>`<button data-event="${esc(x.id)}" title="${esc(x.title)}" aria-label="${esc(x.title)}" class="${x.id===e?.id?'selected':''}" style="left:${x.start/item.duration*100}%;width:${(x.end-x.start)/item.duration*100}%"></button>`).join('');
 $('view-presentation').hidden=!r?.presentation?.rendered;$('view-presentation').href=r?.job?'./?job='+encodeURIComponent(r.job):selected()?.originalUrl?'./?result='+encodeURIComponent('demo/game/'+state.id.split('-').at(-1)+'/showcase.json'):'#';
 $('export-video').disabled=!r?.tacticalReplay?.url;$('export-video').onclick=()=>{if(r?.tacticalReplay?.url)window.open(r.tacticalReplay.url,'_blank','noopener');};$('export-json').disabled=!r;$('export-text').disabled=!r;$('raw-evidence').textContent=JSON.stringify({video:item,companion,analysis:r},null,2);renderPlayerReports();if(r?.demo){$('project-title').textContent='幕后 MVP 分析';}renderOverlay();if(!state.busy)step(r?3:1);
}
async function addVideo(item){if(state.busy)return;if(!state.project)state.project=crypto.randomUUID();if(!state.videos.some(x=>x.id===item.id))state.videos.push(item);$('welcome').hidden=true;$('workspace').hidden=false;await selectVideo(item.id);saveProject(null);}
async function selectVideo(id){if(state.busy)return;state.id=id;state.eventId=null;state.playerId=null;state.stopAt=null;const version=++loadVersion;$('video').pause();$('video').removeAttribute('src');$('video').load();$('video').poster=selected().poster||'';$('video-placeholder').hidden=false;render();if(state.connected||state.offline)await loadVideo(version);}
function mediaReady(v){if(v.readyState>=2)return Promise.resolve();return new Promise((resolve,reject)=>{const timer=setTimeout(()=>done(new Error('视频加载超时，请重新载入。')),30000);function done(e){clearTimeout(timer);v.removeEventListener('loadeddata',ready);v.removeEventListener('error',bad);e?reject(e):resolve();}function ready(){done();}function bad(){done(new Error('视频无法播放，请检查格式。'));}v.addEventListener('loadeddata',ready);v.addEventListener('error',bad);});}
async function loadVideo(version=loadVersion){if(!(await ensureConnected()))return;try{$('video-message').textContent='正在载入视频…';const item=state.offline?{url:state.localURLs.get(state.id)||selected()?.originalUrl||(state.id==='nba-0042500404-197'?'demo/original.mp4':null)}:await api('/video/'+state.id);if(!item.url)throw new Error('本地素材未在当前会话中，请重新导入视频。');if(version!==loadVersion)return;$('video').src=item.url;$('video').load();await mediaReady($('video'));if(version!==loadVersion)return;$('video-placeholder').hidden=true;const focus=evidenceFor(activePlayer(),currentEvent());if(focus.length)await seek($('video'),focus[Math.min(1,focus.length-1)].time);renderOverlay();refreshEvidenceImages();}catch(e){$('video-message').textContent=e.message;toast(e.message);}}
function seek(v,t){if(Math.abs(v.currentTime-t)<.01&&v.readyState>=2)return Promise.resolve();return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{v.removeEventListener('seeked',done);reject(new Error('定位视频时间超时'));},15000);function done(){clearTimeout(timer);v.removeEventListener('seeked',done);resolve();}v.addEventListener('seeked',done);v.currentTime=t;});}
async function extractFrames(){const v=$('video');await mediaReady(v);if(!Number.isFinite(v.duration)||v.duration<=.5||v.duration>40)throw new Error('当前请使用0.5–40秒的单回合片段。');v.pause();const canvas=document.createElement('canvas');canvas.width=960;canvas.height=Math.round(960*v.videoHeight/v.videoWidth);const frames=[];for(let i=0;i<18;i++){const t=Number((.1+i*(v.duration-.3)/17).toFixed(2));await seek(v,t);canvas.getContext('2d').drawImage(v,0,0,canvas.width,canvas.height);frames.push({time:t,image:canvas.toDataURL('image/jpeg',.74).split(',')[1]});status(`准备画面 ${i+1} / 18`,(i+1)/18*15);}return frames;}
async function analyzeCurrent(){if(state.offline)return analyzeOffline();if(state.busy||!selected()||!(await ensureConnected()))return;const id=state.id;try{if(!$('video').src)await loadVideo();await mediaReady($('video'));setBusy(true);step(2);const frames=await extractFrames();state.frames.set(id,frames);$('stage-vision').className='running';status('正在提交分析任务…',18);const job=await api('/jobs',{method:'POST',body:JSON.stringify({video:{id,title:selected().title,duration:$('video').duration},frames,companion:state.companion.get(id)})});saveProject({job:job.job,id});await pollJob(job.job,id);await seek($('video'),currentEvent()?.observations[0]?.time||result()?.players?.[0]?.evidence?.[0]?.time||frames[6].time);}catch(e){status(e.message,0,true);toast(e.message);}finally{setBusy(false);render();}}
async function pollJob(job,id){const start=Date.now();while(Date.now()-start<650000){const data=await api('/jobs/'+job);if(data.status==='completed'){state.results.set(id,reviewed(data.result));if(id===state.id){state.playerId=null;state.eventId=null;}saveProject(null);status('分析完成 · 点击关键帧检查人物与动作',100);render();return;}if(data.status==='failed'){saveProject(null);throw new Error(data.error||'分析失败，请重试。');}const vision=data.stage==='vision';$('stage-vision').className=vision?'running':'done';$('stage-vlm').className=vision?'':'running';status(vision?`人物检测与短时跟踪 ${data.done||0} / ${data.total||18}`:data.stage==='narrate'?'正在根据画面生成分段解说…':'正在核对上场球员、攻防角色与逐人动作…',vision?20+(data.done||0)/(data.total||18)*25:Math.min(90,50+(Date.now()-start)/4000));await new Promise(r=>setTimeout(r,3000));}throw new Error('任务仍在云端处理，可从历史项目恢复。');}
function visiblePeople(vision,t){
 const frames=vision?.frames||[];if(!frames.length||t<frames[0].time-.08||t>frames.at(-1).time+.08)return [];
 const near=frames.reduce((a,b)=>Math.abs(b.time-t)<Math.abs(a.time-t)?b:a),scene=near.scene;
 const before=new Map(),after=new Map();
 // Bridge only brief same-scene detection gaps, never freeze a lost identity on screen.
 for(const f of frames){if(f.scene!==scene||Math.abs(f.time-t)>.45)continue;for(const p of f.people){if(f.time<=t)before.set(p.trackId,{p,t:f.time});if(f.time>=t&&!after.has(p.trackId))after.set(p.trackId,{p,t:f.time});}}
 const ids=new Set([...before.keys(),...after.keys()]);return [...ids].flatMap(id=>{
 const a=before.get(id),b=after.get(id),closest=!a?b:!b?a:t-a.t<b.t-t?a:b;
 if(!a||!b)return Math.abs(closest.t-t)<=.08?[closest.p]:[];
 if(a.t===b.t)return [a.p];
 if(b.t-a.t>.45||(a.p.association??1)<.5||(b.p.association??1)<.5)return [];
 const k=(t-a.t)/(b.t-a.t),p=a.p,q=b.p;
 return [{...p,...Object.fromEntries(['x','y','w','h'].map(n=>[n,p[n]+k*(q[n]-p[n])])),...(p.court&&q.court?{court:p.court.map((x,i)=>x+k*(q.court[i]-x))}:{})}];
 });
}
function renderTimedCommentary(){const line=result()?.narration?.segments?.find(s=>$('video').currentTime>=s.start&&$('video').currentTime<s.end);$('timed-commentary').hidden=!line;if(line){$('timed-title').textContent=line.title;$('timed-text').textContent=line.text;}}
function renderOverlay(){renderTimedCommentary();if(result()?.players)return renderBasketballOverlay();const v=$('video'),r=result(),e=currentEvent();$('overlay').innerHTML='';$('frame-label').hidden=true;if(!$('overlay-toggle').checked||!r?.vision||!v.videoWidth)return;const people=visiblePeople(r.vision,v.currentTime);if(!people.length)return;$('frame-label').hidden=false;const box=$('video-stage').getBoundingClientRect(),ratio=v.videoWidth/v.videoHeight,w=Math.min(box.width,box.height*ratio),h=w/ratio,ox=(box.width-w)/2,oy=(box.height-h)/2;
 const px=(x)=>(ox+x*w)/box.width*1000,py=(y)=>(oy+y*h)/box.height*562.5,roles=e?{[e.actorTrackId]:'#d9f792',[e.beneficiaryTrackId]:'#ffc294',[e.defenderTrackId]:'#95cfee'}:{};
 const list=e?people.filter(p=>roles[p.trackId]):people;
 $('overlay').innerHTML=list.map(p=>{const x=px(p.x),y=py(p.y),ww=p.w*w/box.width*1000,hh=p.h*h/box.height*562.5,color=roles[p.trackId]||'#9dccb6';let trail='';if($('trail-toggle').checked){const fs=r.vision.frames.filter(f=>f.time<=v.currentTime&&f.time>=v.currentTime-1.8),lastScene=fs.at(-1)?.scene;const points=fs.filter(f=>f.scene===lastScene).map(f=>f.people.find(q=>q.trackId===p.trackId)).filter(Boolean);if(points.length>1)trail=`<polyline points="${points.map(q=>`${px(q.x+q.w/2)},${py(q.y+q.h)}`).join(' ')}" stroke="${color}" fill="none" stroke-width="2" stroke-dasharray="4 3"/>`;}
 return `${trail}<rect x="${x}" y="${y}" width="${ww}" height="${hh}" rx="4" fill="${color}" fill-opacity=".06" stroke="${color}" stroke-width="1.6"/><ellipse cx="${x+ww/2}" cy="${y+hh}" rx="${ww*.4}" ry="5" fill="${color}" fill-opacity=".4"/><rect x="${x}" y="${Math.max(0,y-19)}" width="38" height="18" rx="3" fill="${color}"/><text x="${x+4}" y="${Math.max(0,y-19)+13}" font-size="11" fill="#172c25">${esc(p.trackId)}</text>`;}).join('');}
function animate(){renderOverlay();if(!$('video').paused)animation=requestAnimationFrame(animate);}
async function importFile(file){if(!file)return;if(state.offline)return importOffline(file);if(!(await ensureConnected()))return toast('连接云端后，请重新选择视频。');let url;try{if(file.size>300*1024*1024)throw new Error('视频最大300MB');url=URL.createObjectURL(file);const v=document.createElement('video');v.preload='metadata';await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('读取视频超时')),15000);v.onloadedmetadata=()=>{clearTimeout(timer);resolve();};v.onerror=()=>{clearTimeout(timer);reject(new Error('无法读取该视频'));};v.src=url;});if(!Number.isFinite(v.duration)||v.duration>.0+40||v.duration<=.5)throw new Error('请导入0.5–40秒的单回合视频。');setBusy(true);status('正在导入至团队私有视频库…',10);const req=await api('/upload',{method:'POST',body:JSON.stringify({title:file.name,size:file.size,duration:v.duration,type:file.type||'video/mp4'})});const form=new FormData();Object.entries(req.upload.fields).forEach(([k,val])=>form.append(k,val));form.append('file',file);const response=await fetch(req.upload.url,{method:'POST',body:form});if(!response.ok)throw new Error('上传失败，请重试。');const item=await api('/upload/complete',{method:'POST',body:JSON.stringify({id:req.id})});setBusy(false);await addVideo(item);status('');}catch(e){status(e.message,0,true);}finally{setBusy(false);if(url)URL.revokeObjectURL(url);$('video-file').value='';}}
function download(name,data,type='application/json'){const url=URL.createObjectURL(new Blob([typeof data==='string'?data:JSON.stringify(data,null,2)],{type})),a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
async function openHistory(){$('history-list').innerHTML=projects().map(p=>`<button class="history-item" data-project="${esc(p.id)}">${esc(p.title)}<small>${p.videos.length} 段视频 · ${esc(new Date(p.updatedAt).toLocaleString())}${p.pending?' · 可恢复任务':''}</small></button>`).join('')||'<p class="dialog-note">暂无项目。导入视频后，项目会出现在这里。</p>';$('history-dialog').showModal();}
$('sample-btn').onclick=async()=>{try{const r=await fetch('data/nba-catalog.json');const all=await r.json();const demo=state.offline?await (await fetch('demo/game.json')).json():null;const catalog=demo?demo.rounds.map(r=>({...all.find(v=>r.videoId===v.id),title:`尼克斯 ${r.identity.jersey}号 · ${r.actionTitle}`,originalUrl:new URL(r.original,new URL('demo/game.json',location.href)).href})):all;$('sample-list').innerHTML=(demo?'<button class=sample-choice data-all-samples>载入这 5 个同场回合</button>':'')+catalog.map((x,i)=>`<button class="sample-choice" data-sample="${i}"><img src="${esc(x.poster)}" alt="视频预览"><span><strong>${esc(x.title)}</strong><small>${num(x.duration)} 秒 · 含匹配的官方出手数据</small></span></button>`).join('');$('sample-list').onclick=async e=>{if(e.target.closest('[data-all-samples]')){$('library-dialog').close();for(const item of catalog)await addVideo(item);return;}const b=e.target.closest('[data-sample]');if(!b)return;$('library-dialog').close();await addVideo(catalog[Number(b.dataset.sample)]);};$('library-dialog').showModal();}catch(e){toast(e.message);}};
$('choose-video').onclick=$('add-video').onclick=()=>$('video-file').click();$('video-file').onchange=e=>importFiles([...e.target.files]);const zone=$('drop-zone');zone.ondragover=e=>{e.preventDefault();zone.classList.add('dragover');};zone.ondragleave=()=>zone.classList.remove('dragover');zone.ondrop=e=>{e.preventDefault();zone.classList.remove('dragover');importFiles([...e.dataTransfer.files]);};
$('attach-data').onclick=()=>$('data-file').click();$('data-file').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>500000)throw new Error('配套JSON不超过500KB');const d=JSON.parse(await file.text());if(!['hidden-impact/companion-v1','hidden-impact/companion-v2'].includes(d.schema)||!d.source||!Array.isArray(d.opportunity||[]))throw new Error('格式不符，请下载配套数据模板。');let previous=-1;for(const row of d.opportunity||[]){if(!Number.isFinite(row.time)||!Number.isFinite(row.expectedPoints)||row.time<=previous||row.time>selected().duration||row.expectedPoints<0||row.expectedPoints>4)throw new Error('检查时间顺序、视频时长及预期分范围0–4。');previous=row.time;}state.companion.set(state.id,d);state.results.delete(state.id);saveProject(null);render();toast('配套数据已绑定当前视频，请重新分析。');}catch(err){toast(err.message);}finally{e.target.value='';}};
$('remove-data').onclick=()=>{state.companion.delete(state.id);state.results.delete(state.id);saveProject(null);render();};$('template-btn').onclick=()=>download('companion-template.json',{schema:'hidden-impact/companion-v2',source:'填写数据提供方',players:[],frames:[],gravity:[],opportunity:[],notes:'players: trackId、sourcePlayerId、label、jersey（已确认球衣号码）；frames: time、players[{playerId,x,y,confidence}]、ballHandlerId，x/y为0–1球场坐标；gravity: time、trackId、attentionShare(0–1)；opportunity: time、expectedPoints(0–4)。时间相对当前视频，身份映射须核验，缺失留空。'});
$('analyze-btn').onclick=analyzeCurrent;$('all-analysis').onclick=async()=>{if(state.busy||state.batch)return;state.batch=true;try{for(const v of [...state.videos]){if(state.results.has(v.id))continue;await selectVideo(v.id);await analyzeCurrent();if(!state.results.has(v.id))break;}}finally{state.batch=false;setBusy(false);}};$('home-btn').onclick=newProject;$('history-btn').onclick=$('resume-btn').onclick=openHistory;
$('history-list').onclick=async e=>{const b=e.target.closest('[data-project]');if(!b)return;const p=projects().find(x=>x.id===b.dataset.project);if(!p)return;$('history-dialog').close();state.project=p.id;state.videos=p.videos;state.companion=new Map(p.companion||[]);state.results=new Map();try{const cache=new Map(JSON.parse(localStorage.getItem('hi-results-v2')||'[]'));for(const v of p.videos)if(cache.has(v.id))state.results.set(v.id,reviewed(cache.get(v.id)));}catch{}$('welcome').hidden=true;$('workspace').hidden=false;await selectVideo(p.pending?.id||p.videos[0].id);if(await ensureConnected()){if(!$('video').src)await loadVideo();for(const j of p.jobs||[])try{const d=await api('/jobs/'+j.job);if(d.result)state.results.set(j.id,reviewed({...d.result,confirmedNames:state.results.get(j.id)?.confirmedNames}));}catch{}render();if(p.pending){setBusy(true);step(2);try{await pollJob(p.pending.job,p.pending.id);}catch(err){status(err.message,0,true);}finally{setBusy(false);render();}}}};
$('event-list').onclick=e=>{const b=e.target.closest('[data-video]');if(b)selectVideo(b.dataset.video);};$('rank-sort').onclick=()=>{state.sort='rank';renderList();};$('time-sort').onclick=()=>{state.sort='time';renderList();};$('top-n').onchange=renderList;$('load-video').onclick=()=>loadVideo();
$('frame-list').onclick=async e=>{const b=e.target.closest('[data-time]');if(!b||state.busy)return;try{$('video').pause();state.stopAt=null;await seek($('video'),Number(b.dataset.time));renderOverlay();}catch(err){toast(err.message);}};$('timeline').onclick=e=>{const b=e.target.closest('[data-event]');if(b){state.eventId=b.dataset.event;render();}};$('video').addEventListener('timeupdate',()=>{if(state.stopAt!==null&&$('video').currentTime>=state.stopAt){const end=state.stopAt;state.stopAt=null;$('video').pause();$('video').currentTime=end;}renderOverlay();});$('video').addEventListener('play',()=>{cancelAnimationFrame(animation);animate();});$('video').addEventListener('pause',()=>{cancelAnimationFrame(animation);renderOverlay();});$('video').addEventListener('seeked',renderOverlay);$('overlay-toggle').onchange=$('trail-toggle').onchange=renderOverlay;$('relation-toggle').onchange=()=>{renderOverlay();if(activePlayer())renderEvidenceCards(evidenceFor(activePlayer(),currentEvent()),currentEvent());};window.addEventListener('resize',renderOverlay);
$('replay-btn').onclick=async()=>{const e=currentEvent();if(!e)return;try{state.stopAt=e.end;await seek($('video'),e.start);await $('video').play();}catch(err){toast(err.message);}};$('fullscreen-btn').onclick=()=>$('video-stage').requestFullscreen?.().catch(()=>toast('无法进入全屏'));
for(const id of ['method-btn','score-help'])$(id).onclick=()=>$('method-dialog').showModal();document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());$('connect').onclick=()=>state.offline?toast('工作区已就绪。'):$('login-dialog').showModal();$('login-form').onsubmit=async e=>{e.preventDefault();sessionStorage.setItem('hi-team-key',$('access-code').value.trim());try{await api('/session');setConnected(true);$('login-dialog').close();if(selected())await loadVideo();}catch(err){$('login-error').textContent=err.message;}};
$('speak-btn').onclick=()=>{if(!('speechSynthesis'in window))return toast('浏览器不支持朗读');if(speechSynthesis.speaking)return speechSynthesis.cancel();const u=new SpeechSynthesisUtterance($('narrative').textContent);u.lang='zh-CN';speechSynthesis.speak(u);};$('export-json').onclick=()=>download('hidden-impact-'+state.id+'.json',{video:selected(),companion:state.companion.get(state.id),analysis:result()});$('export-text').onclick=()=>download('hidden-impact-'+state.id+'.txt',`${selected().title}\n\n${result().overview}\n\n${(result().narration?.segments||[]).map(s=>`${s.start.toFixed(2)}–${s.end.toFixed(2)}s · ${s.title}\n${s.text}`).join('\n\n')}\n\n${(result().events||[]).map(e=>`${e.title} · 待核验\n${e.summary}\n候选指数：${e.score??'证据不足'}\n${e.measurement?.reason||e.caveat}`).join('\n\n')}\n\n模型：${result().source}`,'text/plain');
async function start(){newProject();try{const r=await fetch('data/nba-ai-reviews.json');if(r.ok)state.reviews=await r.json();}catch{}try{const session=await api('/session');state.offline=session.mode==='offline';setConnected(true);if(state.offline){$('offline-notice').hidden=true;$('pipeline-card').querySelectorAll('small')[1].textContent='战术解读';}}catch{}/* No catalog, old results or project loaded without an explicit user action. */}

function activePlayer(){return result()?.players?.find(p=>p.id===state.playerId);}
function rankedPlayers(r){return [...(r?.players||[])].filter(p=>p.role==='offense'&&p.status==='candidate'&&p.score>0&&r.events?.some(e=>e.actorTrackId===p.id&&e.score>0)).sort((a,b)=>b.score-a.score||b.visibleSeconds-a.visibleSeconds);}
function playerColor(p){return p?.team==='A'?'#d1dfcb':p?.team==='B'?'#c5dce6':'#dce1df';}
function playerName(p){return result()?.confirmedNames?.[p?.id]||result()?.displayNames?.[p?.id]||p?.label||p?.id||'身份待确认';}
function safeCommentary(e){const text=e.commentary||'';return text&&!/导致|致|造成|创造了|使得|因此/.test(text)?text:e.summary;}
function storyFor(p,e){
 const m=e?.measurement,spacing=e?.actionType==='spacing';
 if(['review','presentation'].includes(e?.actionType))return {title:'跟随主角，看得分机会如何形成',badge:'接应与分球',summary:e.summary,limit:''};
 if(!p)return {title:'这段画面，还不足以选出幕后贡献者',summary:'没有确认到可分析的上场球员。可换用人物更清晰、镜头连续的回合。',badge:'证据不足'};
 if(!e||!m)return {title:p.role==='defense'?'查看这位防守人的画面证据':['ballhandler','shooter'].includes(p.status)?'这是进攻执行者，继续寻找无球贡献':p.score===0?'看到了无球参与，尚未测得贡献信号':p.diagnostics?.knownHandlerFrames<3?'持球者未可靠定位，暂时无法评估贡献':'贡献证据不足，先核验这位球员',summary:p.reason||'暂不评分。',badge:p.role==='defense'?'防守观察':p.score===0?'已观察 · 未检出信号':'暂不评分'};
 if(e.actionType==='draw-kick')return {title:'从持球牵动，到队友的出手',badge:'牵动后分球',summary:safeCommentary(e),limit:'持球转移与防守响应的观察指数'};
 if(e.origin==='temporal-geometry-v5')return {title:{screen:'他接近防守路径，队友的空间随后变化',decoy:'跟随他的跑位，看防守如何被带动',spacing:'他在无球侧，持续撑开进攻空间'}[e.actionType],badge:{screen:'掩护协同候选',decoy:'跑位响应候选',spacing:'空间支撑候选'}[e.actionType],summary:safeCommentary(e),limit:'连续视频测量 · 观察指数，尚不等于因果贡献'};
 const name=id=>playerName(result().players.find(x=>x.id===id));
 return {title:spacing?'他没有持球，但附近的防守人远离持球者':'从他的无球动作，看队友空间如何变化',badge:spacing?'空间支撑线索':'空间变化线索',summary:spacing?`${name(e.actorTrackId)} 处于无球状态，${name(e.defenderTrackId)} 与他邻近，同时与持球者 ${name(e.beneficiaryTrackId)} 保持分离。这个位置结构持续 ${num(m.sustainedSeconds)} 秒。`:`在 ${num(e.start,2)}–${num(e.end,2)} 秒，${name(e.actorTrackId)} 参与的动作附近，${name(e.beneficiaryTrackId)} 与 ${name(e.defenderTrackId)} 的画面间距从 ${num(m.separationBefore)} 变为 ${num(m.separationAfter)}。`,limit:spacing?'观察到空间支撑结构，尚不能证明他吸引了防守。':'观察到同步空间变化，尚不能证明个人因果贡献。'};
}
function evidenceFor(p,e){const rows=e?.observations?.length?e.observations:p?.evidence||[];return rows.length<=3?rows:[rows[0],rows[Math.floor(rows.length/2)],rows.at(-1)];}
function renderPlayerReports(){
 const r=result(),players=r?.players,p=activePlayer(),e=currentEvent();
 $('player-roster').hidden=!players;$('story-hero').hidden=!players;$('spatial-panel').hidden=true;$('pipeline-card').hidden=!!r;
 $('role-strip').hidden=!players;$('return-mvp').hidden=true;if(!players)return;
 const ranked=rankedPlayers(r),other=players.filter(x=>!ranked.includes(x)),story=storyFor(p,e);
 const person=(x,i)=>`<button data-player="${esc(x.id)}" aria-pressed="${x.id===p?.id}" class="roster-person ${x.id===p?.id?'active':''}" style="--team:${playerColor(x)}"><span class="person-id">${i===undefined?'·':String(i+1).padStart(2,'0')}</span><span><strong>${esc(playerName(x))}</strong><small>${x.role==='defense'?'防守观察':x.status==='release-review'?'出手动作待核验 · 不参与排名':x.status==='shooter'?'最终出手者 · 不参与幕后排名':x.status==='ballhandler'?'主要持球 · 不参与无球排名':x.score>0?'空间线索':x.score===0?'未检出贡献信号':'证据不足'}</small></span><b>${r.presentationScore?.trackId===x.id?r.presentationScore.value:Number.isFinite(x.score)?num(x.score,0):'—'}</b></button>`;
 const featured=ranked[0]||(r.presentationScore?players.find(x=>x.id===r.focusPlayerId):null),comparisons=players.filter(x=>x.id!==featured?.id);
 $('player-roster').innerHTML=`<div class="strip-heading"><h2>${featured?'幕后 MVP 候选':'暂未选出幕后 MVP'}</h2><span>本片段</span></div><div class="roster-grid">${featured?person(featured,0):'<p class="roster-note">没有足够可靠的正向贡献证据。可展开逐人报告查看缺少的环节。</p>'}</div>${comparisons.length?`<details class="other-players" ${p&&p.id!==featured?.id?'open':''}><summary>${featured?'比较其他球员':'查看逐人观察'} · ${comparisons.length}</summary><div class="roster-grid">${[...ranked,...other].filter(x=>x.id!==featured?.id).map(x=>person(x,ranked.includes(x)?ranked.indexOf(x):undefined)).join('')}</div></details>`:''}<p class="roster-note">${featured?'点击球员切换观察视角':'证据不足不计零分 · 不按名单顺序选 MVP'}</p>`;
 $('story-hero').innerHTML=`<div class="story-kicker"><span>${e?'HIDDEN IMPACT / 幕后 MVP':'球员观察'}</span><span class="story-badge">${esc(story.badge)}</span></div><h2>${esc(story.title)}</h2><div class="story-subline">${p?`<strong>${esc(playerName(p))}</strong><span>${e?`${num(e.start,2)} – ${num(e.end,2)} 秒`:`可见 ${num(p.visibleSeconds)} 秒`}</span>`:''}<span>${p&&r.confirmedNames?.[p.id]?'姓名已人工确认':e?'连续动作回放':'逐人观察'}</span></div>`;
 if(!p){$('impact-content').innerHTML='<div class="empty-next"><b>暂无可归因对象</b>未确认的场边人物不会进入候选榜。</div>';$('impact-details').innerHTML='';$('frame-list').innerHTML='';$('evidence-intervals').innerHTML='';$('role-strip').innerHTML='';$('narrative').textContent=story.summary;$('insight-meta').textContent='';return;}
 updateRoleStrip(r,p,e,$('video').currentTime,visiblePeople(r.vision,$('video').currentTime));$('video-title').textContent=(e?'主角 · ':'球员观察 · ')+playerName(p);$('return-mvp').hidden=!featured||p.id===featured.id;$('return-mvp').onclick=()=>{state.playerId=featured.id;state.eventId=null;render();};
 const m=e?.measurement||p.measurement,d=p.diagnostics;const diagnostic=d?`<div class="score-diagnostics"><strong>这次计算缺什么</strong><div><span>可见位置</span><b>${p.observationCount||0} 帧</b></div><div><span>无球且有持球者定位</span><b>${d.knownHandlerFrames} / ${d.offBallFrames} 帧</b></div><div><span>完成几何测量的窗口</span><b>${d.evaluatedWindows}</b></div><small>帧数含短时身份关联，不等于人工标注量。</small></div>`:'';
 $('impact-content').innerHTML=`<div class="score-block"><span class="score-label">HIDDEN IMPACT · 观察指数</span><div class="score-value"><strong>${num(r.presentationScore?.trackId===p.id?r.presentationScore.value:p.score,0)}</strong><span>${Number.isFinite(p.score)||r.presentationScore?.trackId===p.id?'/ 100':'—'}</span></div><h3 class="actor-name">${esc(playerName(p))}</h3><button id="confirm-name" class="text-button">${r.confirmedNames?.[p.id]?'修改已确认姓名':'确认球员姓名'} ↗</button><div class="result-quality">${Number.isFinite(m?.quality)?`证据质量 ${num(m.quality*100,0)}% · `:''}可见 ${num(p.visibleSeconds)} 秒</div></div>`;
 $('impact-details').innerHTML=`${m?`<details class="score-breakdown"><summary>分数如何组成</summary><div class="contribution-bars">${(p.components||[]).map(c=>`<div class="bar-row"><div class="bar-label"><span>${esc(c.label)}</span><b>${num(c.points)} / ${c.weight}</b></div><div class="bar-track"><i style="width:${Math.min(100,c.points/c.weight*100)}%"></i></div></div>`).join('')}</div><p>${r.scoringVersion==='temporal-impact-v5'?'分数描述信号强度；证据质量单列，不重复扣分。':'原始分 × 证据质量。'}工程权重尚未校准。</p></details>`:''}<p class="score-warning">${esc(story.limit||p.reason)}</p>${!e?diagnostic:''}`;if(r.presentationScore)$('impact-details').innerHTML='';
 $('confirm-name').onclick=()=>{$('identity-name').value=r.confirmedNames?.[p.id]||'';$('identity-current').textContent=`正在核验：${p.label}。请对照视频、球衣号码与名单填写；留空可恢复临时编号。`;$('identity-dialog').showModal();};
 $('insight-title').textContent='这一回合，值得注意什么';$('narrative').textContent=story.summary;$('insight-meta').textContent=story.limit||'点击画面证据核验人物与角色。';
 const rows=evidenceFor(p,e);renderEvidenceCards(rows,e);$('frame-count').textContent='点画面定位 · 点区间回放';
 $('timeline').innerHTML=rows.map((o,i)=>`<button data-jump="${o.time}" aria-label="跳转证据 ${num(o.time,2)}秒" title="${['观察起点','关键时刻','后续状态'][i]} · ${num(o.time,2)}s" class="evidence-tick" style="left:${o.time/selected().duration*100}%;width:1%"></button>`).join('');
 $('replay-btn').disabled=!rows.length;$('replay-btn').textContent='↻ 回放这段证据';$('play-range').textContent=e?`${num(e.start,2)} – ${num(e.end,2)} 秒`:`${rows.length} 个观察时刻`;
 const alignment=r.vision?.semanticContext?.timeAlignment;if(alignment)$('insight-meta').textContent+=` · 官方出手时钟已对齐至 ${num(alignment.shotTime,2)}s（约±${alignment.uncertaintySeconds}s）`;

 refreshEvidenceImages();
}
// Render markings only for identities participating in the selected explanation.
function storyRoles(e,p){
 return e?[[e.actorTrackId,'主角','actor','#ffdc79'],...(e.supportTrackIds||[]).map(id=>[id,'协同队友','support','#b0a4f4']),[e.beneficiaryTrackId,'收益队友','beneficiary','#87d9ff'],...(e.defenderTrackIds||[e.defenderTrackId]).map((id,i)=>[id,e.defenderTrackIds?('防守者'):'防守者','defender','#ff9e8b'])]:p?[[p.id,'观察球员','actor','#ffdc79']]:[];
}
function focusMarks(people,e,p,px,py,labels=true,active=true){
 if(!$('relation-toggle').checked)e=null;
 const roles=new Map(storyRoles(e,p).map(([id,label,type,color])=>[id,{color,label}]));
 const list=people.filter(q=>roles.has(q.trackId));let out='';
 const a=list.find(q=>q.trackId===e?.defenderTrackId),b=list.find(q=>q.trackId===e?.beneficiaryTrackId);
 if(active&&a&&b&&!result()?.presentationMotion&&!e?.supportTrackIds?.length)out+=`<line x1="${px(a.x+a.w/2)}" y1="${py(a.y+a.h)}" x2="${px(b.x+b.w/2)}" y2="${py(b.y+b.h)}" stroke="#87d9ff" stroke-width="2" stroke-dasharray="6 6" opacity=".8"/>`;
 for(const q of list){const role=roles.get(q.trackId);if(q.positionSource==='unlocalized'){out+=`<text x="${px(q.x)}" y="${py(.96)}" font-size="12" fill="${role.color}">${esc(role.label)} · 定位中</text>`;continue;}const x=px(q.x+q.w/2),y=py(q.y+q.h),ly=Math.max(26,py(q.y)-(q.trackId===p?.id?40:12)),lx=Math.max(65,Math.min(935,x));out+=`<g data-focus="${esc(q.trackId)}"><ellipse cx="${x}" cy="${y}" rx="22" ry="7" fill="${role.color}" fill-opacity=".2" stroke="${role.color}" stroke-width="3"/>${labels?`<rect x="${lx-86}" y="${ly-19}" width="172" height="24" rx="6" fill="#12262a" fill-opacity=".94"/><text x="${lx}" y="${ly-2}" text-anchor="middle" font-size="13" font-weight="600" fill="${role.color}">${esc(result()?.displayNames?.[q.trackId]||role.label)}</text>`:''}</g>`;}
 return out;
}
function renderBasketballOverlay(){
 const v=$('video'),r=result(),p=activePlayer(),event=currentEvent(),svg=$('overlay');svg.innerHTML='';$('frame-label').hidden=true;
 if(!r?.vision||!v.videoWidth||!p)return;
 const t=v.currentTime,e=event,active=!!e&&t>=e.start-.04&&t<=e.end+.04;
 // Role identity persists through the play; relationship effects are limited to evidence.
 const presentationActive=!!r.presentationMotion&&(r.presentationScore||r.presentation?.eventId===e?.id),motion=presentationActive?r.presentationMotion.frames[Math.min(r.presentationMotion.frames.length-1,Math.round(t*r.presentationMotion.fps))]:null,people=motion?.people||visiblePeople(r.vision,t),box=$('video-stage').getBoundingClientRect(),ratio=v.videoWidth/v.videoHeight,w=Math.min(box.width,box.height*ratio),h=w/ratio,ox=(box.width-w)/2,oy=(box.height-h)/2;
 const px=x=>(ox+x*w)/box.width*1000,py=y=>(oy+y*h)/box.height*562.5;
 updateRoleStrip(r,p,e,t,people);
 if($('overlay-toggle').checked){let shapes=focusMarks(people,e,p,px,py,true,active);
  if($('trail-toggle').checked&&e&&!r.presentationMotion&&r.scoringVersion!=='temporal-impact-v5'){let points=[];const recent=r.vision.frames.filter(f=>f.time<=t&&f.time>=Math.max(e.start,t-1.2)),scene=recent.at(-1)?.scene;let previous=null;for(const f of recent){const q=f.people.find(q=>q.trackId===p.id);if(f.scene!==scene||!q||(previous!==null&&f.time-previous>.4))points=[];if(q&&f.scene===scene)points.push(`${px(q.x+q.w/2)},${py(q.y+q.h)}`);previous=f.time;}if(points.length>1)shapes=`<polyline points="${points.join(' ')}" fill="none" stroke="#ffdc79" stroke-width="3" opacity=".75"/>`+shapes;}
  if(presentationActive&&e)shapes=reviewedDirections(r,e,t,people,px,py)+shapes;else if(r.scoringVersion==='temporal-impact-v5')shapes=motionShapes(r,p,active?e:null,t,people,px,py)+shapes;
  svg.innerHTML=shapes;$('frame-label').hidden=false;$('frame-label').textContent=e&&$('relation-toggle').checked?(active?'关键动作 · 观察空间变化':'全程跟随 · 角色保持不变'):people.some(q=>q.trackId===p.id)?`${playerName(p)} · 球员观察`:'此刻定位不足 · 点击下方证据时刻';
 }
 updateEvidenceTimeline(t);
 const rows=evidenceFor(p,event);let nearest=-1;if(rows.length){nearest=rows.reduce((best,o,i)=>Math.abs(o.time-t)<Math.abs(rows[best].time-t)?i:best,0);if(Math.abs(rows[nearest].time-t)>.5)nearest=-1;}
 document.querySelectorAll('#frame-list .frame-card').forEach((el,i)=>{el.classList.toggle('selected',i===nearest);el.setAttribute('aria-current',i===nearest?'true':'false');});
}

function updateRoleStrip(r,p,e,t,people){
 const roles=storyRoles(e,p);
 $('role-strip').hidden=!roles.length;
 $('role-strip').innerHTML=roles.map(([id,label,role])=>{
 const visible=people.some(q=>q.trackId===id),seen=r.vision.frames.filter(f=>f.people.some(q=>q.trackId===id));
 const status=people.find(q=>q.trackId===id)?.offscreen?'画面外':visible?'跟随中':seen.length&&t<seen[0].time?'尚未定位':'暂未定位';
 const player=r.players.find(q=>q.id===id);
 return `<div class="role-chip role-${role}${visible?'':' unavailable'}"><i></i><span><b>${label}</b><strong>${esc(playerName(player))}</strong></span><small>${status}</small></div>`;
 }).join('');
}

function projection(h,x,y){const d=h[2][0]*x+h[2][1]*y+h[2][2];return d?[(h[0][0]*x+h[0][1]*y+h[0][2])/d,(h[1][0]*x+h[1][1]*y+h[1][2])/d]:null;}
function currentVisionFrame(r,t){return r?.vision?.frames?.reduce((a,b)=>!a||Math.abs(b.time-t)<Math.abs(a.time-t)?b:a,null);}
function reviewedDirections(r,e,t,people,px,py){
 if(r.presentationMotion){const motion=r.presentationMotion.frames[Math.min(r.presentationMotion.frames.length-1,Math.round(t*r.presentationMotion.fps))];if(!motion?.heroArrow)return '';return `<defs><marker id="direction-actor-${e.actorTrackId}" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#ffdc79"/></marker></defs><polyline points="${motion.heroArrow.points.map(([x,y])=>`${px(x/(r.presentationMotion.width||1280))},${py(y/(r.presentationMotion.height||720))}`).join(' ')}" fill="none" stroke="#ffdc79" stroke-width="5" stroke-linecap="round" marker-end="url(#direction-actor-${e.actorTrackId})"/>`;}

 const frame=currentVisionFrame(r,t),h=frame?.calibration?.courtToImage;if(!h)return '';
 let out='';
 for(const [id,label,type,color] of storyRoles(e,null)){
  if(type!=='actor')continue;
  const person=people.find(q=>q.trackId===id);if(!person?.court)continue;
  const origin=projection(h,...person.court);if(!origin)continue;
  const points=[[px(person.x+person.w/2),py(person.y+person.h*.4)]];let previous=t,last=person.court;
  for(const f of r.vision.frames){
   if(f.time<=t)continue;if(f.time>t+1.6||f.scene!==frame.scene)break;
   const q=f.people.find(q=>q.trackId===id);if(!q?.court||q.association<.65)continue;
   const dt=f.time-previous;if(dt>.4||Math.hypot(q.court[0]-last[0],q.court[1]-last[1])>Math.max(1.2,dt*9))break;
   const dest=projection(h,...q.court);if(!dest)break;
   points.push([px(person.x+person.w/2+dest[0]-origin[0]),py(person.y+person.h*.4+dest[1]-origin[1])]);previous=f.time;last=q.court;
  }
  if(points.length<3||previous-t<.4||Math.hypot(points.at(-1)[0]-points[0][0],points.at(-1)[1]-points[0][1])<10)continue;
  const marker='direction-'+type+'-'+id.replace(/[^a-z0-9]/gi,'');
  out+=`<defs><marker id="${marker}" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="${color}"/></marker></defs><polyline points="${points.map(q=>q.join(',')).join(' ')}" fill="none" stroke="${color}" stroke-width="${type==='actor'?5:2.5}" stroke-linecap="round" marker-end="url(#${marker})"/>`;
 }
 return out;
}
function motionShapes(r,p,e,t,people,px,py){
 const f=currentVisionFrame(r,t),actor=people.find(q=>q.trackId===p.id);if(!f||!actor||Math.abs(f.time-t)>.3)return '';
 const h=f.calibration?.courtToImage;let out='<defs><marker id="motion-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#ffe399"/></marker></defs>';
 const project=q=>h&&q.court?projection(h,...q.court):[q.x+q.w/2,q.y+q.h];
 if($('trail-toggle').checked){for(const [id,color] of [[p.id,'#ffe399'],...e&&$('relation-toggle').checked?[[e.defenderTrackId,'#ff9e8b']]:[]]){
  let prev=null;const past=r.vision.frames.filter(q=>q.scene===f.scene&&q.time<=t&&q.time>=Math.max(e?.start||0,t-2.3));
  for(const q of past){const person=q.people.find(x=>x.trackId===id),pt=person?project(person):null;if(pt&&prev&&q.time-prev.time<.4){const opacity=.12+.68*(1-(t-q.time)/2.3);out+=`<line x1="${px(prev.pt[0])}" y1="${py(prev.pt[1])}" x2="${px(pt[0])}" y2="${py(pt[1])}" stroke="${color}" stroke-width="${id===p.id?7:3}" stroke-linecap="round" opacity="${opacity}"/>`;}prev=pt?{pt,time:q.time}:null;}
  if(past.length>2){const first=past[0].people.find(q=>q.trackId===id);if(first){const pt=project(first);if(pt)out+=`<ellipse cx="${px(pt[0])}" cy="${py(pt[1])}" rx="15" ry="5" fill="none" stroke="${color}" opacity=".5" stroke-dasharray="3 3"/>`;}}
 }}
 // Openness is a measured nearest-defender distance, not an inferred influence region.
 const beneficiary=people.find(q=>q.trackId===e?.beneficiaryTrackId);
 if(h&&beneficiary?.court&&e&&$('relation-toggle').checked){const opp=people.filter(q=>q.team!==beneficiary.team&&q.court);const radius=Math.min(2.4,...opp.map(q=>Math.hypot(q.court[0]-beneficiary.court[0],q.court[1]-beneficiary.court[1])));if(Number.isFinite(radius)&&opp.length){const pts=Array.from({length:41},(_,i)=>projection(h,beneficiary.court[0]+radius*Math.cos(i*Math.PI/20),beneficiary.court[1]+radius*Math.sin(i*Math.PI/20))).filter(Boolean);out=`<polygon points="${pts.map(q=>`${px(q[0])},${py(q[1])}`).join(' ')}" fill="#87d9ff" fill-opacity=".13" stroke="#87d9ff" stroke-opacity=".4" stroke-width="1"/>`+out;}}
 return out;
}
function intervalExplanation(e,start,end){
 if(['review','presentation'].includes(e?.actionType)&&result()?.presentationMotion)return start<e.keyTime?'44号接球后向左前方推进，防守者向持球区域靠近。':'44号把球分向左侧，阿努诺比接球起跳；最终三分命中。';
 if(!e){
  const p=activePlayer(),rows=(p?.series||[]).filter(q=>q.time>=start-.04&&q.time<=end+.04&&Number.isFinite(q.separation));
  if(rows.length<2)return `${playerName(p)} 在这段画面中的连续定位不足，无法可靠比较空间变化。`;
  const a=rows[0].separation,b=rows.at(-1).separation,change=b-a>.2?'增大':b-a<-.2?'缩小':'基本不变';
  return `${playerName(p)} 与最近防守者的间距${change}（${num(a)} → ${num(b)}，参考距离）。这是该球员自身的空间变化，尚无充分证据证明他为队友创造了机会。`;
 }
 const rows=(e.measurement?.series||[]).filter(q=>q.time>=start-.04&&q.time<=end+.04);
 const name=id=>playerName(result()?.players?.find(p=>p.id===id));
 const actor=name(e.actorTrackId),mate=name(e.beneficiaryTrackId),defender=name(e.defenderTrackId);
 if(rows.length<2)return `${actor} 的动作片段。连续位置不足，请结合视频核验。`;
 const a=rows[0],b=rows.at(-1),moved=(key)=>a[key]&&b[key]?Math.hypot(b[key][0]-a[key][0],b[key][1]-a[key][1]):null;
 const movement=moved('a'),response=moved('d'),delta=b.separation-a.separation;
 const action=e.actionType==='draw-kick'?'持球牵动后转移球权':e.actionType==='screen'&&rows.some(q=>q.pathBlock)?'接近防守路径':movement===null?'参与无球动作':movement>.35?'进行无球跑位':'保持无球站位';
 const reaction=response!==null&&response>.3?`${defender} 同时移动`:`${defender} 保持相邻防守位置`;
 const change=delta>.2?'拉大':delta<-.2?'缩小':'基本稳定';
 let text=`主角 ${actor} ${action}，${reaction}；与收益队友 ${mate} 的间距${change}（${num(a.separation)} → ${num(b.separation)}）。`;
 if(Number.isFinite(a.openness)&&Number.isFinite(b.openness))text+=b.openness-a.openness>.25?'队友与最近防守人的距离也增大，出现更多接球或处理球空间。':b.openness-a.openness<-.25?'但其他防守者更靠近队友，整体空间并未同步改善。':'最近防守距离变化不大，尚不能认定形成了新的出手机会。';
 return text;
}
function renderEvidenceIntervals(rows,e){
 const intervals=rows.slice(0,-1).map((o,i)=>({start:o.time,end:rows[i+1].time}));
 $('evidence-intervals').innerHTML=intervals.map((q,i)=>`<button class="interval-note" data-interval="${i}" data-start="${q.start}" data-end="${q.end}" aria-label="回放解析 ${num(q.start,2)} 至 ${num(q.end,2)} 秒"><span class="interval-heading"><b>${i===0?'动作展开':'后续变化'}</b><time>${num(q.start,2)}—${num(q.end,2)}s</time><i>▶ 回放</i></span><p>${esc(intervalExplanation(e,q.start,q.end))}</p></button>`).join('');
 $('evidence-caption').textContent=e?'点击关键帧定位 · 点击区间回放':'点击画面定位，点击区间回放';
 updateEvidenceTimeline($('video').currentTime);
}
function updateEvidenceTimeline(t){
 document.querySelectorAll('#evidence-intervals [data-interval]').forEach(el=>{const active=t>=Number(el.dataset.start)&&t<Number(el.dataset.end);el.classList.toggle('active',active);el.setAttribute('aria-current',active?'step':'false');});
}
$('evidence-intervals').onclick=async ev=>{const b=ev.target.closest('[data-interval]');if(!b||state.busy)return;try{state.stopAt=Number(b.dataset.end);await seek($('video'),Number(b.dataset.start));await $('video').play();}catch(err){toast(err.message);}};
$('motion-speed').onchange=ev=>{$('video').playbackRate=Number(ev.target.value);};

const evidenceImageCache=new WeakMap();let evidenceRequest=0;
function renderEvidenceCards(rows,e){
 const r=result(),p=activePlayer(),cache=evidenceImageCache.get(r)||new Map(),sources=state.frames.get(state.id)||r.thumbnails||[];
 $('frame-list').innerHTML=rows.map((o,i)=>{
  const exact=cache.get(o.time),near=sources.length?sources.reduce((a,b)=>Math.abs(b.time-o.time)<Math.abs(a.time-o.time)?b:a):null,sourceTime=exact?o.time:near?.time,src=exact|| (near?.image?'data:image/jpeg;base64,'+near.image:near?.url),precise=!!src&&Number.isFinite(sourceTime)&&Math.abs(sourceTime-o.time)<.05;
  const people=Number.isFinite(sourceTime)&&r.vision?visiblePeople(r.vision,sourceTime):[],marks=src?focusMarks(people,e,p,x=>x*1000,y=>y*562.5,false):'';
  const actor=people.find(q=>q.trackId===p.id),zoom=actor&&!$('relation-toggle').checked,cropWidth=550,cropHeight=309.375,cropX=actor?Math.max(0,Math.min(1000-cropWidth,(actor.x+actor.w/2)*1000-cropWidth/2)):0,cropY=actor?Math.max(0,Math.min(562.5-cropHeight,(actor.y+actor.h/2)*562.5-cropHeight/2)):0;
  const view=zoom?`${cropX} ${cropY} ${cropWidth} ${cropHeight}`:'0 0 1000 562.5';
  const row=e?.measurement?.series?.reduce((best,x)=>!best||Math.abs(x.time-o.time)<Math.abs(best.time-o.time)?x:best,null);
  const caption=row?`防守者距${e.actionType==='spacing'?'持球者':'队友'} ${num(row.separation)} ${e?.measurement?.units||'倍人物高度'}`:(p.role==='defense'?'查看防守位置与人物身份':'查看无球状态与人物身份');
  return `<button class="frame-card" data-time="${o.time}" aria-label="${['观察起点','关键时刻','后续状态'][i]} ${num(o.time,2)}秒"><div class="evidence-step"><b>0${i+1}</b><span>${['观察起点','关键时刻','后续状态'][i]}</span><time>${num(o.time,2)}s ↗</time></div><div class="frame-image">${src?`<svg viewBox="${view}" role="img" aria-label="${precise?'证据':'邻近预览'}画面 ${num(sourceTime,2)}秒${zoom?' · 主角局部放大':''}"><image href="${esc(src)}" width="1000" height="562.5" preserveAspectRatio="none"/>${marks}</svg><span class="crop-label">${zoom?'聚焦 '+esc(p.id):'全景关系'}</span>`:'<span>载入原片后生成画面</span>'}</div><p>${esc(caption)}</p><small>${precise?'精确时刻 · 点击回放':src?`预览 ${num(sourceTime,2)}s · 点击跳至 ${num(o.time,2)}s`:'点击跳转视频证据'}</small></button>`;
 }).join('')||'<p class="inline-empty">当前没有可定位的画面证据。</p>';
 renderEvidenceIntervals(rows,e);
}
async function refreshEvidenceImages(){
 const r=result(),p=activePlayer(),e=currentEvent(),source=$('video').src;if(!r||!p||!source||!document.createElement)return;
 const rows=evidenceFor(p,e);if(!rows.length)return;let cache=evidenceImageCache.get(r);if(!cache){cache=new Map();evidenceImageCache.set(r,cache);}if(rows.every(o=>cache.has(o.time)))return;
 const token=++evidenceRequest,video=document.createElement('video');video.crossOrigin='anonymous';video.muted=true;video.preload='auto';video.src=source;
 try{await mediaReady(video);const canvas=document.createElement('canvas');canvas.width=720;canvas.height=Math.round(720*video.videoHeight/video.videoWidth);for(const o of rows){if(token!==evidenceRequest||r!==result()||p!==activePlayer())return;if(cache.has(o.time))continue;await seek(video,o.time);canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);cache.set(o.time,canvas.toDataURL('image/jpeg',.8));}if(r===result()&&p===activePlayer()){renderEvidenceCards(rows,e);renderOverlay();}}catch{/* Labeled neighboring previews remain usable if CORS/media decoding fails. */}finally{video.pause();video.removeAttribute('src');video.load();}
}
async function jumpToEvidence(t){if(state.busy)return;try{$('video').pause();state.stopAt=null;await seek($('video'),Number(t));renderOverlay();}catch(e){toast(e.message);}}
$('player-roster').onclick=async e=>{const b=e.target.closest('[data-player]');if(!b)return;state.playerId=b.dataset.player;state.eventId=null;render();const p=activePlayer();if(p?.evidence.length)await jumpToEvidence(p.evidence[Math.min(1,p.evidence.length-1)].time);};
$('impact-details').onclick=e=>{const b=e.target.closest('[data-jump]');if(b)jumpToEvidence(b.dataset.jump);};
$('timeline').onclick=e=>{const jump=e.target.closest('[data-jump]');if(jump)return jumpToEvidence(jump.dataset.jump);const b=e.target.closest('[data-event]');if(b){state.eventId=b.dataset.event;render();}};
$('replay-btn').onclick=async()=>{const p=activePlayer(),e=currentEvent(),start=e?.start??p?.evidence?.[0]?.time,end=e?.end??p?.evidence?.at(-1)?.time;if(start===undefined)return;try{state.stopAt=end;await seek($('video'),start);await $('video').play();}catch(err){toast(err.message);}};

$('import-result').onclick=()=>$('result-file').click();
$('result-file').onchange=async ev=>{try{const file=ev.target.files[0];if(!file)return;if(file.size>5000000)throw new Error('分析文件不超过5MB');const data=JSON.parse(await file.text()),r=data.analysis||data.result;if(!r||r.version!=='basketball-roster-v3'||!Array.isArray(r.players)||!Array.isArray(r.vision?.frames)||!r.video?.id)throw new Error('请选择本工作台导出的逐人分析JSON');const v=data.video||r.video;if(!Number.isFinite(v.duration)||v.duration<=0||v.duration>40)throw new Error('视频信息无效');$('history-dialog').close();newProject();state.results.set(v.id,reviewed(r));if(data.companion)state.companion.set(v.id,data.companion);await addVideo(v);toast('已恢复分析；视频需要仍在当前团队云端。');}catch(e){toast(e.message);}finally{ev.target.value='';}};

$('identity-form').onsubmit=ev=>{ev.preventDefault();const r=result(),p=activePlayer();if(!r||!p)return;const name=$('identity-name').value.trim();r.confirmedNames={...r.confirmedNames};if(name)r.confirmedNames[p.id]=name;else delete r.confirmedNames[p.id];saveProject();$('identity-dialog').close();render();};
$('export-text').onclick=()=>{const r=result();download('hidden-impact-'+state.id+'.txt',`${selected().title}\n\n${(r.narration?.segments||[]).map(s=>`${s.start.toFixed(2)}–${s.end.toFixed(2)}s · ${s.title}\n${s.text}`).join('\n\n')}\n\n${(r.players||[]).map(p=>{const e=r.events?.find(e=>e.actorTrackId===p.id),s=storyFor(p,e);return `${playerName(p)} · 观察指数 ${num(p.score,0)}\n${s.summary}\n${s.limit||''}`;}).join('\n\n')}`,'text/plain');};
start();

// Local preview is deliberately separate from production inference and never creates a cloud job.
async function importOffline(file){let url;try{if(file.size>300*1024*1024)throw new Error('视频最大300MB');url=URL.createObjectURL(file);const v=document.createElement('video');v.preload='auto';v.src=url;await mediaReady(v);if(!Number.isFinite(v.duration)||v.duration<=.5||v.duration>40)throw new Error('请导入0.5–40秒的单回合视频。');const id='local-'+crypto.randomUUID();state.localURLs.set(id,url);await addVideo({id,title:file.name,duration:v.duration,source:'本地导入'});url=null;toast('视频保留在当前浏览器会话中，未上传云端。');}catch(e){status(e.message,0,true);}finally{if(url)URL.revokeObjectURL(url);$('video-file').value='';}}
async function analyzeOffline(){if(state.busy||!selected())return;try{setBusy(true);step(2);if(!$('video').src)await loadVideo();const frames=selected()?.originalUrl||state.id==='nba-0042500404-197'?[]:await extractFrames();state.frames.set(state.id,frames);if(selected()?.originalUrl||state.id==='nba-0042500404-197'){const response=await fetch(state.id.endsWith('-197')?'demo/analysis.json':'demo/game/'+state.id.split('-').at(-1)+'/analysis.json');if(!response.ok)throw new Error('结果文件加载失败');const r=await response.json();r.presentation=await (await fetch('demo/game/'+state.id.split('-').at(-1)+'/showcase.json')).json();state.results.set(state.id,r);state.playerId=null;saveProject(null);render();await seek($('video'),r.events?.[0]?.start||0);$('offline-preview').hidden=true;status('结果已就绪',100);}else{state.results.delete(state.id);render();$('analyze-btn').textContent='重新预览';$('impact-content').innerHTML='<div class=empty-next><b>画面已就绪</b>点击关键画面回看视频。</div>';$('offline-preview').hidden=false;$('offline-preview').innerHTML='<h2>关键帧预览</h2><p>点击画面跳转到对应时刻。</p><div class="offline-frames">'+frames.filter((_,i)=>i%3===0).map(f=>`<button data-preview-time="${f.time}"><img src="data:image/jpeg;base64,${f.image}" alt="${f.time} 秒视频画面"><span>${f.time.toFixed(2)}s</span></button>`).join('')+'</div>';$('offline-preview').onclick=e=>{const b=e.target.closest('[data-preview-time]');if(b)jumpToEvidence(b.dataset.previewTime);};status('画面准备完成',100);await seek($('video'),frames[0].time);}step(3);}catch(e){status(e.message,0,true);}finally{setBusy(false);}}

// A project is a collection of independently analyzed possessions.
async function importFiles(files){if(state.busy||state.batch)return; if(files.length>30)return toast('一次最多导入30段视频。');state.batch=true;try{for(const file of files)await importFile(file);}finally{state.batch=false;setBusy(false);}}
let gameEntries=[];
$('game-summary').onclick=async()=>{
 if(state.busy||state.batch)return toast('请等待视频处理完成。');
 gameEntries=state.videos.filter(v=>state.results.get(v.id)?.presentation?.rendered||(state.offline&&v.originalUrl&&state.results.has(v.id)));
 if(!gameEntries.length)return toast('先分析视频并生成完整回放，再汇总本场。');
 const presets=state.offline?await (await fetch('demo/game.json')).json():{rounds:[]};
 const first=state.results.get(gameEntries[0].id),official=first.deepData?.official||gameEntries[0].official||{};
 $('game-id').value=official.gameId||first.presentation?.gameId||'';$('game-team').value=official.team||first.presentation?.team||'';
 $('game-identities').innerHTML=gameEntries.map((v,i)=>{const r=state.results.get(v.id),p=r.presentation||presets.rounds.find(p=>p.videoId===v.id),actor=r.events?.[0]?.actorTrackId;return `<label class="game-identity"><span>回合 ${i+1} · ${esc(p?.actor?.label||r.players?.find(p=>p.id===actor)?.label||actor||v.title)}</span><input data-game-jersey="${i}" inputmode="numeric" pattern="[0-9]{1,2}" maxlength="2" placeholder="球衣号码" value="${esc(p?.identity?.jersey||'')}"></label>`;}).join('');
 $('game-error').textContent=`本项目 ${state.videos.length} 段，${gameEntries.length} 段可汇总。`;$('game-link').hidden=true;$('game-dialog').showModal();
};
$('game-form').onsubmit=async e=>{
 e.preventDefault();$('game-submit').disabled=true;$('game-link').hidden=true;
 try{
 const gameId=$('game-id').value.trim(),team=$('game-team').value.trim(),jerseys=[...$('game-identities').querySelectorAll('[data-game-jersey]')].map(x=>x.value.trim());
 let url;
 if(state.offline){
  const demo=await (await fetch('demo/game.json')).json();
  const rounds=gameEntries.map((v,i)=>{const r=state.results.get(v.id),preset=demo.rounds.find(d=>d.videoId===v.id),p=structuredClone(preset||r.presentation);
   if(!p?.rendered&& !preset)throw Error('回合尚未生成完整展示结果。');
   if((p.gameId&&p.gameId!==gameId)||(p.team&&p.team!==team))throw Error('请只选择同场、同队的视频。');
   p.gameId=gameId;p.team=team;p.identity=jerseys[i]?{jersey:jerseys[i],confirmed:true,source:'user-confirmed-jersey'}:{confirmed:false};
   if(preset){const base=new URL('demo/game.json',location.href);for(const k of ['video','original','poster'])if(p[k])p[k]=new URL(p[k],base).href;for(const f of p.evidence)f.image=new URL(f.image,base).href;}
   return p;
  });
  const summary=await api('/game-summary',{method:'POST',body:JSON.stringify({gameId,team,rounds})}),id=crypto.randomUUID();sessionStorage.setItem('hi-game-'+id,JSON.stringify(summary));url='./?local-game='+id;
 }else{
  const jobIds=gameEntries.map(v=>state.results.get(v.id).job);if(jobIds.some(x=>!x))throw Error('请重新分析未保存到云端的回合。');
  const identities=Object.fromEntries(jobIds.map((id,i)=>[id,jerseys[i]]));
  const response=await api('/games',{method:'POST',body:JSON.stringify({gameId,team,jobIds,identities})});url='./?game='+encodeURIComponent(response.id);
 }
 $('game-link').href=url;$('game-link').hidden=false;$('game-error').textContent='本场汇总已生成，点击查看结果。';
 }catch(err){$('game-error').textContent=err.message;}finally{$('game-submit').disabled=false;}
};
