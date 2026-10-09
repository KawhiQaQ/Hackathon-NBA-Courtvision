const $=id=>document.getElementById(id);
const video=$('replay');let data,stopAt=null,version=0;
const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function sync(){if(!data)return;const t=video.currentTime;document.querySelectorAll('.frame').forEach((node,i)=>{const next=data.evidence[i+1]?.time??Infinity;node.classList.toggle('active',t>=data.evidence[i].time&&t<next);});document.querySelectorAll('.interval').forEach((node,i)=>node.classList.toggle('active',t>=data.intervals[i].start&&t<data.intervals[i].end));}
async function playRange(start,end){stopAt=end;video.currentTime=start;try{await video.play();}catch{stopAt=null;}}
video.addEventListener('timeupdate',()=>{if(stopAt!==null&&video.currentTime>=stopAt){const end=stopAt;stopAt=null;video.pause();video.currentTime=end;}sync();});
video.addEventListener('error',()=>$('video-error').hidden=false);
$('speed').onchange=()=>video.playbackRate=Number($('speed').value);
$('key-replay').onclick=()=>{if(data)playRange(data.evidence[0].time,data.evidence.at(-1).time);};
async function switchVideo(original){if(!data)return;const token=++version,t=video.currentTime,playing=!video.paused;stopAt=null;video.pause();$('video-error').hidden=true;video.src=original?data.original:data.video;for(const id of ['original','annotated']){$(id).classList.toggle('selected',(id==='original')===original);$(id).setAttribute('aria-pressed',String((id==='original')===original));}video.onloadedmetadata=()=>{if(token!==version)return;video.currentTime=Math.min(t,video.duration);video.playbackRate=Number($('speed').value);if(playing)video.play().catch(()=>{});};video.load();}
$('original').onclick=()=>switchVideo(true);$('annotated').onclick=()=>switchVideo(false);
try{const response=await fetch('demo/showcase.json');if(!response.ok)throw Error('manifest');data=await response.json();if(data.mode!=='demo'||data.schema!=='hidden-impact/showcase-v1')throw Error('Unexpected showcase schema');
$('score').textContent=data.score;
$('components').innerHTML=data.components.map(c=>`<div class="component"><div><span>${esc(c.label)}</span><b>${c.points} / ${c.weight}</b></div><div class="bar"><i style="width:${Math.max(0,Math.min(100,c.points/c.weight*100))}%"></i></div></div>`).join('');
$('frames').innerHTML=data.evidence.map((f,i)=>`<button class="frame" data-frame="${i}" aria-label="定位到 ${f.time} 秒：${esc(f.label)}"><span class="frame-top"><i>${i+1}</i>${f.time.toFixed(2)}s</span><img src="${esc(f.image)}" alt="${esc(f.label)}"><span class="frame-title"><span>0${i+1}</span>${esc(f.label)}</span></button>`).join('');
$('intervals').innerHTML=data.intervals.map((x,i)=>`<button class="interval" data-interval="${i}"><span>${x.start.toFixed(2)} — ${x.end.toFixed(2)}s　▶ 区间回放</span><h3>${esc(x.title)}</h3><p>${esc(x.text)}</p></button>`).join('');
$('frames').onclick=e=>{const b=e.target.closest('[data-frame]');if(b){stopAt=null;video.pause();video.currentTime=data.evidence[Number(b.dataset.frame)].time;sync();}};
$('intervals').onclick=e=>{const b=e.target.closest('[data-interval]');if(b){const x=data.intervals[Number(b.dataset.interval)];playRange(x.start,x.end);}};
sync();}catch{$('load-error').hidden=false;}
