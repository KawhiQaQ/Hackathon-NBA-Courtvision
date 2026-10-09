import {cueAt,narrationAt,phaseMarkup,opportunityMarkup,gravityMarkup,storyFact} from './insights-view.js?v=12';
const $=id=>document.getElementById(id);
const video=$('replay');if(new URLSearchParams(location.search).has('job')||new URLSearchParams(location.search).has('result')){video.removeAttribute('src');video.removeAttribute('poster');video.load();document.querySelector('.layout').hidden=true;document.querySelector('.story-section').hidden=true;}let data,stopAt=null,version=0,initialPositionSet=false;
function initialPosition(){if(!initialPositionSet&&data&&video.readyState>=1){initialPositionSet=true;video.currentTime=data.evidence[0].time;}}
const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let currentCue=null;
function syncInsight(){if(!data?.insights)return;const cue=cueAt(data.insights,video.currentTime),line=narrationAt(data.insights,video.currentTime);if(line===currentCue)return;currentCue=line;$('cue-title').textContent=line.title;$('cue-text').textContent=line.text;$('cue-evidence').textContent=cue.evidence;$('phase-rail').querySelectorAll('[data-cue]').forEach((button,i)=>{const active=data.insights.cues[i]===cue;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});}
function sync(){syncInsight();if(Number.isFinite(video.duration)){$('scrub').max=video.duration;$('scrub').value=video.currentTime;const fmt=t=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;$('elapsed').textContent=fmt(video.currentTime)+' / '+fmt(video.duration);}}
function storyPosition(){const track=$('frames'),cards=[...track.querySelectorAll('.story-card')];if(!cards.length)return;const index=cards.reduce((best,node,i)=>Math.abs(node.offsetLeft-cards[0].offsetLeft-track.scrollLeft)<Math.abs(cards[best].offsetLeft-cards[0].offsetLeft-track.scrollLeft)?i:best,0);$('story-position').textContent=String(index+1).padStart(2,'0')+' / '+String(cards.length).padStart(2,'0');$('story-prev').disabled=track.scrollLeft<=2;$('story-next').disabled=track.scrollLeft+track.clientWidth>=track.scrollWidth-2;}
function moveStory(direction){const track=$('frames'),card=track.querySelector('.story-card');if(card)track.scrollBy({left:direction*(card.offsetWidth+18),behavior:'smooth'});}
$('story-prev').onclick=()=>moveStory(-1);$('story-next').onclick=()=>moveStory(1);$('frames').addEventListener('scroll',storyPosition,{passive:true});window.addEventListener('resize',storyPosition);
$('frames').addEventListener('keydown',e=>{if(e.target!==$('frames'))return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();moveStory(e.key==='ArrowRight'?1:-1);}});

async function playRange(start,end){stopAt=end;video.currentTime=start;try{await video.play();}catch{stopAt=null;}}
video.addEventListener('timeupdate',()=>{if(stopAt!==null&&video.currentTime>=stopAt){const end=stopAt;stopAt=null;video.pause();video.currentTime=end;}sync();});
function transport(){const playing=!video.paused;$('play-pause').textContent=playing?'Ⅱ 暂停':'▶ 播放';$('play-pause').setAttribute('aria-label',playing?'暂停视频':'播放视频');}
function ready(){initialPosition();video.controls=false;$('transport').hidden=false;sync();}
video.addEventListener('loadeddata',ready);if(video.readyState>=2)ready();
video.addEventListener('play',transport);video.addEventListener('pause',transport);video.addEventListener('ended',transport);
$('play-pause').onclick=()=>{stopAt=null;if(video.paused)video.play().catch(()=>{$('video-error').hidden=false;});else video.pause();};
$('scrub').oninput=()=>{stopAt=null;video.currentTime=Number($('scrub').value);sync();};
$('expand-video').onclick=()=>{video.controls=true;if(video.webkitEnterFullscreen)video.webkitEnterFullscreen();else if(video.requestFullscreen)video.requestFullscreen().catch(()=>{video.controls=false;});else video.controls=false;};
document.addEventListener('fullscreenchange',()=>{video.controls=document.fullscreenElement===video;});video.addEventListener('webkitendfullscreen',()=>{video.controls=false;});
video.addEventListener('error',()=>$('video-error').hidden=false);
$('speed').onchange=()=>video.playbackRate=Number($('speed').value);
$('key-replay').onclick=()=>{if(data){$('speed').value='0.5';video.playbackRate=.5;playRange(data.evidence[0].time,data.evidence.at(-1).time);}};
async function switchVideo(original){if(!data)return;const token=++version,t=video.currentTime,playing=!video.paused;stopAt=null;video.pause();$('video-error').hidden=true;video.src=original?data.original:data.video;for(const id of ['original','annotated']){$(id).classList.toggle('selected',(id==='original')===original);$(id).setAttribute('aria-pressed',String((id==='original')===original));}video.onloadedmetadata=()=>{if(token!==version)return;video.currentTime=Math.min(t,video.duration);video.playbackRate=Number($('speed').value);if(playing)video.play().catch(()=>{});};video.load();}
$('original').onclick=()=>switchVideo(true);$('annotated').onclick=()=>switchVideo(false);
try{
const params=new URLSearchParams(location.search),job=params.get('job');
const manifestURL=new URL(params.get('result')||'demo/showcase.json',location.href);
if(manifestURL.origin!==location.origin)throw Error('Only same-origin result manifests are supported');
if(job){
 const response=await fetch('/api/jobs/'+encodeURIComponent(job),{headers:{'X-Team-Key':sessionStorage.getItem('hi-team-key')||''}});
 if(!response.ok)throw Error(response.status===401?'请先在分析工作台连接团队工作区，再打开结果。':'结果加载失败。');
 const payload=await response.json();data=payload.result?.presentation;
 if(!data?.rendered)throw Error('结果视频仍在生成，或没有可展示的核验结果。');
}else{
 const response=await fetch(manifestURL);if(!response.ok)throw Error('结果文件加载失败');data=await response.json();
 if(data.mode==='analysis')for(const key of ['original','video'])data[key]=new URL(data[key],manifestURL).href;
 if(data.mode==='analysis')data.evidence.forEach(f=>f.image=new URL(f.image,manifestURL).href);
}
if(!['demo','analysis'].includes(data.mode)||data.schema!=='hidden-impact/showcase-v1'||!data.evidence?.length)throw Error('不支持的结果格式');
if(data.mode==='analysis'){
 $('data-heading').textContent='这次进攻留下怎样的机会？';$('matchup').textContent=data.matchup;$('action-title').textContent=data.actionTitle;
 $('actor-detail').textContent='主角';$('team-badge').textContent='★';$('story-heading').textContent=data.storyTitle;
 $('impact-thesis').innerHTML=`<span>本回合的幕后价值</span><p>${esc(data.summary)}</p><div><b>${esc(data.actor.label)}</b><i>配合</i><b>${esc(data.roles[1].name)}</b></div>`;
 document.querySelector('.story-section .eyebrow').textContent='03 / THE PLAY IN FRAMES';
 initialPositionSet=false;video.src=data.video;video.poster=data.evidence[0].image;video.load();
 $('download-replay').href=data.video;
 const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});$('download-summary').href=URL.createObjectURL(blob);
}

$('score').textContent=Number.isFinite(data.score)?data.score:'—';$('actor-name').textContent=data.actor.label;$('roles').innerHTML=data.roles.map(r=>`<span><i style="--color:${esc(r.color)}"></i>${esc(r.displayName||r.label)}</span>`).join('');
$('components').innerHTML=data.components.length?data.components.map(c=>`<div class="component"><div><span>${esc(c.label)}</span><b>${c.points} / ${c.weight}</b></div><div class="bar"><i style="width:${Math.max(0,Math.min(100,c.points/c.weight*100))}%"></i></div></div>`).join(''):'';
if(data.insights){const insight=data.insights;$('live-insight').hidden=!insight.cues.length&&!insight.narration?.segments?.length;$('data-insights').hidden=!insight.shot&&!insight.gravity;$('phase-rail').innerHTML=phaseMarkup(insight);$('opportunity').innerHTML=opportunityMarkup(insight);$('gravity').innerHTML=gravityMarkup(insight);$('source-caption').textContent=insight.gameId?`${insight.gameId} · Q${insight.period??'—'} ${insight.gameClock??''} · 出手 #${insight.eventId??'—'}`:'';$('official-source').hidden=true;if(insight.sourceUrl){const source=new URL(insight.sourceUrl);if(source.protocol==='https:'&&source.hostname==='china.nba.cn'){$('official-source').href=source.href;$('official-source').hidden=false;}}$('opportunity').hidden=!insight.shot;$('gravity').hidden=!insight.gravity;$('phase-rail').onclick=e=>{const b=e.target.closest('[data-cue]');if(b){stopAt=null;video.pause();video.currentTime=insight.cues[Number(b.dataset.cue)].seek;sync();}};}
$('frames').innerHTML=data.evidence.map((f,i)=>`<article class="story-card"><button class="film-image" data-frame="${i}" aria-label="回看 ${f.time} 秒：${esc(f.label)}"><img src="${esc(f.image)}" alt="${esc(f.label)}：${esc(f.text)}" draggable="false"><span class="film-time">${f.time.toFixed(2)}s ↗</span></button><div class="story-caption"><div class="story-chapter"><span>SCENE ${String(i+1).padStart(2,'0')}</span><b>${esc(f.chapter)}</b></div><h3>${esc(f.label)}</h3><p>${esc(f.text)}</p>${data.insights?`<div class="story-fact"><span>${esc(storyFact(data.insights,f).label)}</span><b>${esc(storyFact(data.insights,f).value)}</b></div>`:''}</div></article>`).join('');
$('frames').onclick=e=>{const b=e.target.closest('[data-frame]');if(b){stopAt=null;video.pause();video.currentTime=data.evidence[Number(b.dataset.frame)].time;document.querySelectorAll('.film-image').forEach(el=>el.classList.toggle('selected',el===b));sync();}};
document.querySelector('.layout').hidden=false;document.querySelector('.story-section').hidden=false;storyPosition();
initialPosition();sync();}catch(error){$('load-error').hidden=false;$('load-error').textContent=error.message||'内容加载失败，请刷新重试。';if(new URLSearchParams(location.search).has('job')||new URLSearchParams(location.search).has('result')){video.pause();video.removeAttribute('src');video.load();document.querySelector('.layout').hidden=true;document.querySelector('.story-section').hidden=true;}}
