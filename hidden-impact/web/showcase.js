const $=id=>document.getElementById(id);
const video=$('replay');let data,stopAt=null,version=0,initialPositionSet=false;
function initialPosition(){if(!initialPositionSet&&data&&video.readyState>=1){initialPositionSet=true;video.currentTime=data.evidence[0].time;}}
const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function sync(){if(Number.isFinite(video.duration)){$('scrub').max=video.duration;$('scrub').value=video.currentTime;const fmt=t=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;$('elapsed').textContent=fmt(video.currentTime)+' / '+fmt(video.duration);}if(!data)return;const t=video.currentTime;document.querySelectorAll('.frame').forEach((node,i)=>{const next=data.evidence[i+1]?.time??Infinity;node.classList.toggle('active',t>=data.evidence[i].time&&t<next);});document.querySelectorAll('.interval').forEach((node,i)=>node.classList.toggle('active',t>=data.intervals[i].start&&t<data.intervals[i].end));}
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
try{const response=await fetch('demo/showcase.json');if(!response.ok)throw Error('manifest');data=await response.json();if(data.mode!=='demo'||data.schema!=='hidden-impact/showcase-v1')throw Error('Unexpected showcase schema');
$('score').textContent=Number.isFinite(data.score)?data.score:'—';$('actor-name').textContent=data.actor.label;$('roles').innerHTML=data.roles.map(r=>`<span><i style="--color:${esc(r.color)}"></i>${esc(r.displayName||r.label)}</span>`).join('');
$('components').innerHTML=data.components.length?data.components.map(c=>`<div class="component"><div><span>${esc(c.label)}</span><b>${c.points} / ${c.weight}</b></div><div class="bar"><i style="width:${Math.max(0,Math.min(100,c.points/c.weight*100))}%"></i></div></div>`).join(''):'<p class=score-caption>金色 · 主角<br>紫色 · 右侧协同队友<br>青色 · 最终出手者<br>珊瑚色 · 两名相关防守者</p>';
$('frames').innerHTML=data.evidence.map((f,i)=>`<button class="frame" data-frame="${i}" aria-label="定位到 ${f.time} 秒：${esc(f.label)}"><span class="frame-top"><i>${i+1}</i>${f.time.toFixed(2)}s</span><img src="${esc(f.image)}" alt="${esc(f.label)}"><span class="frame-title"><span>0${i+1}</span>${esc(f.label)}</span></button>`).join('');
$('intervals').innerHTML=data.intervals.map((x,i)=>`<button class="interval" data-interval="${i}"><span>${x.start.toFixed(2)} — ${x.end.toFixed(2)}s　▶ 区间回放</span><h3>${esc(x.title)}</h3><p>${esc(x.text)}</p></button>`).join('');
$('frames').onclick=e=>{const b=e.target.closest('[data-frame]');if(b){stopAt=null;video.pause();video.currentTime=data.evidence[Number(b.dataset.frame)].time;sync();}};
$('intervals').onclick=e=>{const b=e.target.closest('[data-interval]');if(b){const x=data.intervals[Number(b.dataset.interval)];playRange(x.start,x.end);}};
initialPosition();sync();}catch{$('load-error').hidden=false;}
