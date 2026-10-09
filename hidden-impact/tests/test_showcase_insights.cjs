// Numeric rendering + playback integration; a DOM stub is not a browser visual test.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'..');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'web/demo/showcase.json'),'utf8'));
const view=fs.readFileSync(path.join(root,'web/insights-view.js'),'utf8').replace(/export /g,'');
const ctx=vm.createContext({});vm.runInContext(view,ctx);
assert.equal(ctx.cueAt(manifest.insights,0).phase,'接应');
assert.equal(ctx.cueAt(manifest.insights,8.1).phase,'分球');
assert.equal(ctx.cueAt(manifest.insights,9.5).phase,'出手');
assert.equal(ctx.cueAt(manifest.insights,13.49).phase,'命中');
const opportunity=ctx.opportunityMarkup(manifest.insights),gravity=ctx.gravityMarkup(manifest.insights);
assert(opportunity.includes('42%'));assert(opportunity.includes('39%'));assert(opportunity.includes('+3.0'));
assert(gravity.includes('-16.10'));assert(gravity.includes('+6.47'));
for(const m of gravity.matchAll(/(?:width|left):([\d.-]+)%/g)){assert(Number(m[1])>=0);assert(Number(m[1])<=100);}
const missing=structuredClone(manifest.insights);missing.gravity.axes.forEach(a=>{a.value=null;a.teamMedian=null});
assert(!ctx.gravityMarkup(missing).includes('NaN'));assert(!ctx.gravityMarkup(missing).includes('Infinity'));
assert(!ctx.opportunityMarkup({...manifest.insights,shooter:'<script>bad</script>'}).includes('<script>'));
(async()=>{
 const html=fs.readFileSync(path.join(root,'web/index.html'),'utf8'),nodes=new Map(),events=new Map();
 function node(){return {innerHTML:'',textContent:'',value:'1',hidden:true,dataset:{},style:{},currentTime:0,duration:13.49,readyState:2,paused:true,scrollLeft:0,clientWidth:500,scrollWidth:1000,classList:{toggle(){}},setAttribute(k,v){this[k]=v},addEventListener(k,f){events.set(k,f)},querySelectorAll(){return []},querySelector(){return null},pause(){this.paused=true},play(){this.paused=false;return Promise.resolve()},load(){},scrollBy(){}};}
 for(const m of html.matchAll(/id="([^"]+)"/g))nodes.set(m[1],node());
 const buttons=manifest.insights.cues.map(node);nodes.get('phase-rail').querySelectorAll=()=>buttons;
 const doc={getElementById:id=>{assert(nodes.has(id),'Missing DOM node '+id);return nodes.get(id)},querySelectorAll:()=>[],addEventListener(){}};
 const context=vm.createContext({document:doc,window:{addEventListener(){}},fetch:async()=>({ok:true,json:async()=>manifest}),URL,console});
 const source=fs.readFileSync(path.join(root,'web/showcase.js'),'utf8').replace(/^import .*;\n/,'');
 await vm.runInContext(view+'\n(async()=>{'+source+'})()',context);
 assert.equal(nodes.get('load-error').hidden,true);
 assert.equal(nodes.get('data-insights').hidden,false);
 assert(nodes.get('frames').innerHTML.includes('42% 预期命中率'));
 const video=nodes.get('replay');video.currentTime=9.5;events.get('timeupdate')();
 assert(nodes.get('cue-title').textContent.includes('42%'));
 assert.equal(buttons[2]['aria-pressed'],'true');
 nodes.get('phase-rail').onclick({target:{closest:()=>({dataset:{cue:'3'}})}});
 assert.equal(video.currentTime,11.1);assert.equal(video.paused,true);
 assert(nodes.get('cue-evidence').textContent.includes('+3'));
 video.currentTime=0;events.get('timeupdate')();assert.equal(buttons[0]['aria-pressed'],'true');
 assert.equal(nodes.get('frames').scrollLeft,0,'Playback must never scroll the static filmstrip');
 console.log('PASS: signed gravity, missing values, full-sample comparison, synchronized cues, seek and stationary filmstrip.');
})().catch(e=>{console.error(e);process.exitCode=1});
