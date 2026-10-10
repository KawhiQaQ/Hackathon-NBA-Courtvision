// Exercise real collection navigation, identity changes, media controls and award links.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'..'),game=JSON.parse(fs.readFileSync(path.join(root,'web/demo/game.json'),'utf8'));
const helpers=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(root,'web/game-view.js'),'utf8').replace(/export /g,''),helpers);
const insights=fs.readFileSync(path.join(root,'web/insights-view.js'),'utf8').replace(/export /g,'');
const source=fs.readFileSync(path.join(root,'web/showcase.js'),'utf8').replace(/^import .*;\n/gm,'')+'\n'+fs.readFileSync(path.join(root,'web/story-playback.js'),'utf8').replace(/export /g,'');
const nodes=new Map(),events=new Map();
function node(){return {innerHTML:'',textContent:'',value:'1',hidden:false,currentTime:0,duration:14,paused:true,scrollLeft:0,clientWidth:400,scrollWidth:1200,classList:{toggle(){}},setAttribute(k,v){this[k]=v},removeAttribute(k){delete this[k]},addEventListener(k,f){events.set(k,f)},querySelectorAll(){return []},querySelector(){return null},pause(){this.paused=true},play(){this.paused=false;return Promise.resolve()},load(){},scrollBy(){},scrollIntoView(){}}}
for(const m of fs.readFileSync(path.join(root,'web/index.html'),'utf8').matchAll(/id="([^"]+)"/g))nodes.set(m[1],node());
nodes.get('load-error').hidden=true;
const context=vm.createContext({document:{getElementById:id=>{assert(nodes.has(id),id);return nodes.get(id)},querySelector:()=>node(),addEventListener(){}},window:{addEventListener(){}},scoreMarkup:helpers.scoreMarkup,awardMarkup:helpers.awardMarkup,rankingMarkup:helpers.rankingMarkup,Blob,URL,URLSearchParams,location:{href:'http://localhost/',search:'',origin:'http://localhost'},console,fetch:async()=>({ok:true,json:async()=>structuredClone(game)})});
(async()=>{
 await vm.runInContext(insights+'\n(async()=>{'+source+'})()',context);
 assert(nodes.get('load-error').hidden);assert(nodes.get('round-prev').disabled);
 const video=nodes.get('replay');
 for(let i=0;i<5;i++){
  const r=game.rounds[i];assert.equal(nodes.get('actor-name').textContent,'尼克斯 '+r.identity.jersey+'号');assert.equal(nodes.get('score').textContent,r.impact.score);
  assert(video.src.endsWith(r.video));assert(nodes.get('frames').innerHTML.includes(r.evidence[0].label));assert.equal(nodes.get('download-replay').href,video.src);
  assert(nodes.get('components').innerHTML.includes(r.impact.components[0].label));
  video.onloadedmetadata();assert.equal(video.currentTime,0);
  video.currentTime=1.5;nodes.get('original').onclick();video.onloadedmetadata();assert.equal(video.currentTime,1.5);assert(video.src.endsWith(r.original));
  if(i<4)nodes.get('round-next').onclick();
 }
 assert(nodes.get('round-next').disabled);assert(nodes.get('award-hero').innerHTML.includes(game.winner.jersey));
 nodes.get('leaderboard').onclick({target:{closest:()=>({dataset:{round:'2'}})}});assert.equal(nodes.get('actor-name').textContent,'尼克斯 23号');
 assert(!nodes.get('leaderboard').innerHTML.includes('NaN'));
 console.log('PASS: five rounds switch media, scores, roles, stories and commentary; award links seek the correct round.');
})().catch(e=>{console.error(e);process.exitCode=1});
