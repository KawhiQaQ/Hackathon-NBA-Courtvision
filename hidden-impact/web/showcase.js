import {sourceTime,replayTime} from './story-playback.js?v=1';
import {cueAt,narrationAt,phaseMarkup,opportunityMarkup,gravityMarkup,storyFact} from './insights-view.js?v=actor-evidence-1';
import {scoreMarkup,awardMarkup,rankingMarkup} from './game-view.js?v=game-1';
const $=id=>document.getElementById(id),video=$('replay');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let data,game,index=0,stopAt=null,version=0,currentCue=null,summaryURL=null,originalMode=false;
const fmt=t=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
function sourceNow(){return originalMode?video.currentTime:sourceTime(video.currentTime,data?.playback);}
function seekTime(t){return originalMode?t:replayTime(t,data?.playback);}
function fitVideo(){
 const page=document.querySelector('.page-video'),wrap=document.querySelector('.video-wrap');
 if(!page?.clientHeight||!wrap?.clientHeight)return;
 const ratio=(video.videoWidth&&video.videoHeight)?video.videoWidth/video.videoHeight:(data?.width&&data?.height?data.width/data.height:16/9);
 page.style.width=Math.min(page.parentElement.clientWidth-94,wrap.clientHeight*ratio)+'px';
}
window.addEventListener('resize',fitVideo);
window.addEventListener('hashchange',()=>requestAnimationFrame(fitVideo));
if(typeof ResizeObserver!=='undefined')new ResizeObserver(fitVideo).observe(document.querySelector('.video-wrap'));
function sync(){
 if(data?.insights){const cue=cueAt(data.insights,sourceNow()),line=narrationAt(data.insights,sourceNow());if(line!==currentCue){currentCue=line;$('cue-title').textContent=line.title;$('cue-text').textContent=line.text;$('cue-evidence').textContent=cue.evidence;$('phase-rail').querySelectorAll('[data-cue]').forEach((b,i)=>{b.classList.toggle('active',data.insights.cues[i]===cue);b.setAttribute('aria-pressed',String(data.insights.cues[i]===cue));});}}
 if(Number.isFinite(video.duration)){$('scrub').max=video.duration;$('scrub').value=video.currentTime;$('elapsed').textContent=fmt(video.currentTime)+' / '+fmt(video.duration);}
}
function storyPosition(){const track=$('frames'),cards=[...track.querySelectorAll('.story-card')];if(!cards.length)return;const n=cards.reduce((best,node,i)=>Math.abs(node.offsetLeft-cards[0].offsetLeft-track.scrollLeft)<Math.abs(cards[best].offsetLeft-cards[0].offsetLeft-track.scrollLeft)?i:best,0);$('story-position').textContent=String(n+1).padStart(2,'0')+' / '+String(cards.length).padStart(2,'0');$('story-prev').disabled=track.scrollLeft<=2;$('story-next').disabled=track.scrollLeft+track.clientWidth>=track.scrollWidth-2;}
for(const [id,direction] of [['story-prev',-1],['story-next',1]])$(id).onclick=()=>{const card=$('frames').querySelector('.story-card');if(card)$('frames').scrollBy({left:direction*(card.offsetWidth+18),behavior:'smooth'});};
$('frames').addEventListener('scroll',storyPosition,{passive:true});window.addEventListener('resize',storyPosition);
$('frames').addEventListener('keydown',e=>{if(e.target===$('frames')&&['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();$(e.key==='ArrowLeft'?'story-prev':'story-next').click();}});
function loadVideo(src,t=0,playing=false){const token=++version;stopAt=null;video.pause();$('video-error').hidden=true;$('transport').hidden=true;video.onloadedmetadata=()=>{if(token!==version)return;video.currentTime=Math.min(t,video.duration||0);fitVideo();video.playbackRate=Number($('speed').value);if(playing)video.play().catch(()=>{});sync();};video.src=src;video.load();}
function transport(){const playing=!video.paused;$('play-pause').textContent=playing?'Ⅱ 暂停':'▶ 播放';$('play-pause').setAttribute('aria-label',playing?'暂停视频':'播放视频');}
video.addEventListener('timeupdate',()=>{if(stopAt!==null&&video.currentTime>=stopAt){const end=stopAt;stopAt=null;video.pause();video.currentTime=end;}sync();});
video.addEventListener('loadeddata',()=>{video.controls=false;$('transport').hidden=false;sync();});
for(const kind of ['play','pause','ended'])video.addEventListener(kind,transport);
video.addEventListener('error',()=>$('video-error').hidden=false);
$('play-pause').onclick=()=>{stopAt=null;if(video.paused)video.play().catch(()=>{$('video-error').hidden=false;});else video.pause();};
$('scrub').oninput=()=>{stopAt=null;video.currentTime=Number($('scrub').value);sync();};
$('speed').onchange=()=>video.playbackRate=Number($('speed').value);
$('expand-video').onclick=()=>{video.controls=true;if(video.webkitEnterFullscreen)video.webkitEnterFullscreen();else video.requestFullscreen?.().catch(()=>video.controls=false);};
document.addEventListener('fullscreenchange',()=>video.controls=document.fullscreenElement===video);
video.addEventListener('webkitendfullscreen',()=>video.controls=false);
$('key-replay').onclick=async()=>{if(!data?.evidence.length)return;video.currentTime=seekTime(data.evidence[0].time);const last=data.evidence.at(-1).time;stopAt=originalMode?last:(data.playback?.beats.find(b=>Math.abs(b.sourceTime-last)<.05)?.end??seekTime(last));$('speed').value='0.5';video.playbackRate=.5;try{await video.play();}catch{stopAt=null;}};
for(const [id,original] of [['original',true],['annotated',false]])$(id).onclick=()=>{if(!data)return;const t=sourceNow(),playing=!video.paused;originalMode=original;loadVideo(original?data.original:data.video,seekTime(t),playing);for(const which of ['original','annotated']){$(which).classList.toggle('selected',(which==='original')===original);$(which).setAttribute('aria-pressed',String((which==='original')===original));}};
function selectRound(n){
 if(!game?.rounds[n])return;index=n;data=game.rounds[n];currentCue=null;document.querySelector('.layout').hidden=false;$('data-insights').hidden=false;
 if(data.schema!=='hidden-impact/showcase-v1'||!data.evidence?.length)throw Error('该回合缺少完整展示数据。');
 $('round-select').value=String(n);$('round-position').textContent=String(n+1).padStart(2,'0')+' / '+String(game.rounds.length).padStart(2,'0');$('round-prev').disabled=n===0;$('round-next').disabled=n===game.rounds.length-1;
 $('round-tabs').querySelectorAll('[data-round]').forEach((b,i)=>{b.classList.toggle('active',i===n);b.setAttribute('aria-pressed',String(i===n));});
 $('matchup').textContent=data.actionTitle||data.matchup||'回合分析';$('play-label').textContent=`回合 ${String(n+1).padStart(2,'0')}${data.identity?.jersey?' · '+data.identity.jersey+'号':''}`;
 $('actor-name').textContent=data.identity?.jersey?`${data.team||game.team} ${data.identity.jersey}号`:data.actor.label;
 if($('narration-kind'))$('narration-kind').textContent=data.insights?.narration?.modelInvoked?'AI 解说':'回合解读';
 if($('contribution-kind'))$('contribution-kind').textContent=data.analysisStatus==='unconfirmed-mvp'?'本回合数据解读':data.analysisStatus==='reviewed-story'?'本回合幕后MVP':'本回合幕后 MVP';
 $('action-title').textContent=data.actionTitle||'配合观察';$('score').textContent=Number.isFinite(data.impact?.score)?data.impact.score: Number.isFinite(data.score)?data.score:'—';
 if($('value-number'))$('value-number').hidden=!Number.isFinite(data.score);if($('score-method'))$('score-method').hidden=!Number.isFinite(data.score);
 $('impact-thesis').textContent=data.summary||data.insights?.interpretation||'';$('components').innerHTML=scoreMarkup(data.impact);$('score-formula').textContent=data.impact?.formula||(data.analysisStatus==='unconfirmed-mvp'?'角色证据不足，本回合暂不计入幕后 MVP 排名。':'此回合仅有动作观察分，未提供完整机会对照。');
 $('roles').innerHTML=data.roles.map(r=>`<span><i style="--color:${esc(r.color)}"></i>${esc(r.displayName||r.label)}</span>`).join('');
 const insight=data.insights||{cues:[],narration:{segments:[]}};$('live-insight').hidden=!insight.cues.length&&!insight.narration?.segments?.length;
 $('phase-rail').innerHTML=phaseMarkup(insight);$('opportunity').innerHTML=opportunityMarkup(insight);$('gravity').innerHTML=gravityMarkup(insight);$('opportunity').hidden=!insight.shot;$('gravity').hidden=!insight.gravity&&!insight.actorProfile;
 $('source-caption').textContent=insight.gameId?`${insight.gameId} · Q${insight.period??'—'} ${insight.gameClock??''} · 回合 #${insight.eventId??'—'}`:'';
 $('official-source').hidden=true;if(insight.sourceUrl){const source=new URL(insight.sourceUrl);if(source.protocol==='https:'&&source.hostname==='china.nba.cn'){$('official-source').href=source.href;$('official-source').hidden=false;}}
 $('story-heading').textContent='关键配合';
 $('frames').innerHTML=data.evidence.map((f,i)=>{const fact=storyFact(insight,f);return `<article class="story-card"><button class="film-image" data-frame="${i}" aria-label="回看 ${f.time} 秒：${esc(f.label)}"><img src="${esc(f.image)}" alt="${esc(f.label)}：${esc(f.text)}" draggable="false"><span class="film-time">${f.time.toFixed(2)}s ↗</span></button><div class="story-caption"><div class="story-chapter"><span>SCENE ${String(i+1).padStart(2,'0')}</span><b>${esc(f.chapter)}</b></div><h3>${esc(f.label)}</h3><p>${esc(f.text)}</p>${fact.value!=='回合画面'?`<div class="story-fact"><span>${esc(fact.label)}</span><b>${esc(fact.value)}</b></div>`:''}</div></article>`;}).join('');
 $('frames').scrollLeft=0;$('download-replay').href=data.video;if(summaryURL)URL.revokeObjectURL(summaryURL);summaryURL=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));$('download-summary').href=summaryURL;
 $('speed').value='1';$('annotated').classList.toggle('selected',true);$('original').classList.toggle('selected',false);$('annotated').setAttribute('aria-pressed','true');$('original').setAttribute('aria-pressed','false');
 originalMode=false;video.poster=data.poster||data.evidence[0].image;loadVideo(data.video,0);storyPosition();sync();
}
$('round-select').onchange=()=>selectRound(Number($('round-select').value));
$('round-prev').onclick=()=>selectRound(index-1);$('round-next').onclick=()=>selectRound(index+1);
$('round-tabs').onclick=e=>{const b=e.target.closest('[data-round]');if(b)selectRound(Number(b.dataset.round));};
$('phase-rail').onclick=e=>{const b=e.target.closest('[data-cue]');if(b){stopAt=null;video.pause();video.currentTime=seekTime(data.insights.cues[Number(b.dataset.cue)].seek);sync();}};
$('frames').onclick=e=>{const b=e.target.closest('[data-frame]');if(b){stopAt=null;video.pause();video.currentTime=seekTime(data.evidence[Number(b.dataset.frame)].time);sync();}};
$('leaderboard').onclick=e=>{const b=e.target.closest('[data-round]');if(b){selectRound(Number(b.dataset.round));location.hash='video';}};
function resolveAssets(round,base){if(round.video?.startsWith('demo/')&&base.pathname.endsWith('/demo/showcase.json'))base=new URL('../',base);for(const key of ['video','original','poster'])if(round[key])round[key]=new URL(round[key],base).href;for(const f of round.evidence||[])f.image=new URL(f.image,base).href;return round;}
async function read(url,auth=false){const response=await fetch(url,{cache:'no-store',...(auth?{headers:{'X-Team-Key':sessionStorage.getItem('hi-team-key')||''}}:{})});if(!response.ok)throw Error(response.status===401?'请先在分析工作台连接团队工作区。':'结果加载失败。');return response.json();}
try{
 const params=new URLSearchParams(location.search);let payload,base=new URL('demo/game.json',location.href);
 if(params.has('game')){payload=await read('/api/games/'+encodeURIComponent(params.get('game')),true);base=new URL(location.href);}
 else if(params.has('local-game')){const saved=sessionStorage.getItem('hi-game-'+params.get('local-game'));if(!saved)throw Error('当前浏览器会话中没有这个汇总，请从工作台重新生成。');payload=JSON.parse(saved);base=new URL(location.href);}
 else if(params.has('job')){const job=await read('/api/jobs/'+encodeURIComponent(params.get('job')),true);payload=job.result?.presentation;if(!payload?.rendered)throw Error('尚无完整展示结果。');base=new URL(location.href);}
 else{if(params.has('result'))base=new URL(params.get('result'),location.href);if(base.origin!==location.origin)throw Error('仅支持同源结果文件');payload=await read(base);}
 if(payload.schema==='hidden-impact/game-showcase-v1')game=payload;
 else if(payload.schema==='hidden-impact/showcase-v1')game={rounds:[payload],ranking:[],team:payload.team||'',scope:'单回合'};
 else throw Error('不支持的结果格式');
 game.rounds.forEach(r=>resolveAssets(r,base));if(!game.rounds.length)throw Error('尚无可展示回合。');
 $('round-browser').hidden=false;$('game-scope').textContent=`${game.team||'比赛'} · ${game.rounds.length} 个同场回合`;
 $('round-select').innerHTML=game.rounds.map((r,i)=>`<option value="${i}">回合 ${String(i+1).padStart(2,'0')} · ${esc(r.actionTitle||r.matchup||'配合观察')}</option>`).join('');
 $('round-tabs').innerHTML=game.rounds.map((r,i)=>`<button data-round="${i}" aria-pressed="false"><span>${String(i+1).padStart(2,'0')}</span><div><b>${esc(r.identity?.jersey?`${r.identity.jersey}号 · 幕后MVP`:r.actor.label)}</b><small>${esc(r.actionTitle||r.matchup)}</small></div></button>`).join('');
 $('awards').hidden=game.schema!=='hidden-impact/game-showcase-v1';if(!$('awards').hidden){$('award-scope').textContent=`${game.team} · ${game.gameId} · 已上传 ${game.roundCount} 回合，${game.creditedRounds} 回合计入身份汇总`;$('award-hero').innerHTML=awardMarkup(game);$('leaderboard').innerHTML=rankingMarkup(game);$('game-formula').textContent=game.formula;}
 selectRound(0);
}catch(error){$('load-error').hidden=false;$('load-error').textContent=error.message;document.querySelector('.layout').hidden=true;document.querySelector('.story-section').hidden=true;$('data-insights').hidden=true;$('awards').hidden=true;video.pause();video.removeAttribute('src');video.load();}
