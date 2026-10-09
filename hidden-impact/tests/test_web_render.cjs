// DOM-stub integration check for real analysis rendering; not a browser visual test.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert'),path=require('node:path');
const root=path.join(__dirname,'..'),html=fs.readFileSync(path.join(root,'web/workbench.html'),'utf8'),nodes=new Map();
for(const match of (html+fs.readFileSync(path.join(root,'web/app.js'),'utf8')).matchAll(/id="([^"]+)"/g))nodes.set(match[1],{innerHTML:'',textContent:'',value:'0',checked:true,hidden:false,dataset:{},classList:{toggle(){},add(){},remove(){}},getBoundingClientRect:()=>({width:960,height:540}),addEventListener(){},removeEventListener(){},pause(){},load(){},removeAttribute(){},setAttribute(k,v){this[k]=v},showModal(){},close(){},videoWidth:960,videoHeight:540,readyState:2,currentTime:2});
const storage={getItem:()=>null,setItem(){}};
const context=vm.createContext({console,document:{getElementById:id=>{assert(nodes.has(id),'Unknown DOM id '+id);return nodes.get(id)},querySelectorAll:()=>[]},window:{addEventListener(){}},sessionStorage:storage,localStorage:storage,history:{replaceState(){}},location:{pathname:'/'},fetch:async()=>({ok:true,json:async()=>({})}),AbortSignal,Map,Set,Date,JSON,Math,Number,String,Array,Promise,setTimeout,clearTimeout,cancelAnimationFrame(){},requestAnimationFrame(){}});
vm.runInContext(fs.readFileSync(path.join(root,'web/app.js'),'utf8'),context);
const input=path.join(root,'tests/fixtures/roster-reviewed-export.json');assert(fs.existsSync(input),'Real verification result required');context.fixture=JSON.parse(fs.readFileSync(input,'utf8')).analysis;
vm.runInContext("state.videos=[fixture.video];state.id=fixture.video.id;state.results.set(state.id,fixture);",context);
nodes.get('relation-toggle').checked=false;
for(const player of context.fixture.players){context.pid=player.id;vm.runInContext("state.playerId=pid;render();",context);assert(nodes.get('player-roster').innerHTML.includes(player.label));assert(nodes.get('impact-content').innerHTML.includes(player.label));assert(nodes.get('frame-list').innerHTML.includes('data-time='));assert(!nodes.get('overlay').innerHTML.includes('<polygon'));}
vm.runInContext("state.playerId=null;render();",context);
assert.equal(vm.runInContext('state.playerId',context),'P3');
assert(nodes.get('story-hero').innerHTML.includes('空间支撑线索'));
assert(!nodes.get('overlay').innerHTML.includes('data-focus="P1"'));
assert(!nodes.get('overlay').innerHTML.includes('data-focus="P5"'));
assert(nodes.get('overlay').innerHTML.includes('data-focus="P3"'));
nodes.get('relation-toggle').checked=true;vm.runInContext('renderOverlay()',context);
assert(nodes.get('overlay').innerHTML.includes('data-focus="P1"'));
assert(nodes.get('overlay').innerHTML.includes('data-focus="P5"'));
nodes.get('video').currentTime=8;vm.runInContext('renderOverlay()',context);
assert(!nodes.get('overlay').innerHTML.includes('stroke-dasharray="6 6"'),'Relationship link stays limited to the evidence window');
assert(nodes.get('role-strip').innerHTML.includes('收益队友'));assert(nodes.get('role-strip').innerHTML.includes('防守者'));
vm.runInContext("state.playerId='P2';render();",context);
assert(nodes.get('narrative').textContent.includes('0不是实际比赛贡献为零'));
assert(!nodes.get('narrative').textContent.includes('创造投篮空间'),'Unsupported VLM attribution must not leak into narrative');
context.old={...context.fixture,cropClassification:false};
assert.equal(vm.runInContext('reviewed(old).players',context),undefined);
vm.runInContext("state.results.set(state.id,{...fixture,players:[],events:[]});state.playerId=null;render();",context);
assert(nodes.get('story-hero').innerHTML.includes('不足以选出'));
assert.equal(nodes.get('frame-list').innerHTML,'');
console.log('PASS: six real reports, single-person focus, optional relationship, evidence-window gating, weak/zero/empty results and legacy data.');
// A zero-score-only result must never be promoted merely because it is first in a list.
vm.runInContext("state.results.set(state.id,{...fixture,players:fixture.players.map(p=>({...p,score:p.role==='offense'?0:null,status:p.role==='offense'?'observed':'defense'})),events:[]});state.playerId=null;render();",context);
assert.equal(vm.runInContext('rankedPlayers(result()).length',context),0);
assert(nodes.get('player-roster').innerHTML.includes('暂未选出幕后 MVP'));
assert(!nodes.get('player-roster').innerHTML.includes('>01</span>'));
assert(!nodes.get('player-roster').innerHTML.includes('>02</span>'));
console.log('PASS: no MVP winner or ordinal ranking from an all-zero result.');

context.temporalFixture=JSON.parse(fs.readFileSync(path.join(root,'tests/fixtures/temporal-197.json'),'utf8')).analysis;
vm.runInContext("state.results.set(state.id,temporalFixture);state.playerId=null;render();",context);
assert(nodes.get('spatial-panel').hidden,'Removed mini court must remain hidden');
const event=context.temporalFixture.events[0];
nodes.get('video').currentTime=(event.start+event.end)/2;vm.runInContext('renderOverlay()',context);
assert(nodes.get('overlay').innerHTML.includes('motion-arrow'));
assert(nodes.get('evidence-intervals').innerHTML.includes('data-start='));
assert.equal((nodes.get('evidence-intervals').innerHTML.match(/class="interval-note"/g)||[]).length,2);
assert(!nodes.get('video-title').textContent.includes('跳投'),'Source title must not stand in for the selected protagonist');
console.log('PASS: projected video motion, two interval explanations, and separate source/protagonist titles.');
assert.equal(vm.runInContext('reviewed(temporalFixture).events.length',context),0,'Unverified intermediate results must not become ranked MVPs');
// Real three-role identity must persist outside the scoring interval.
context.cloudFixture=JSON.parse(fs.readFileSync(path.join(root,'tests/fixtures/temporal-cloud.json'),'utf8')).result;
vm.runInContext("state.results.set(state.id,cloudFixture);state.playerId=null;render();",context);
nodes.get('video').currentTime=6.31;vm.runInContext('renderOverlay()',context);
for(const id of ['P13','P2','P3'])assert(nodes.get('overlay').innerHTML.includes(`data-focus="${id}"`),`Role ${id} must remain before the event`);
assert(!nodes.get('overlay').innerHTML.includes('stroke-dasharray="6 6"'));
nodes.get('video').currentTime=.1;vm.runInContext('renderOverlay()',context);
assert(nodes.get('role-strip').innerHTML.includes('尚未定位'),'Missing identity gets explicit status, not a guessed position');
// A brief individual dropout is interpolated; long gaps and camera cuts are not.
context.gap={frames:[{time:0,scene:0,people:[{trackId:'a',x:0,y:0,w:.1,h:.2,association:.9}]},{time:.16,scene:0,people:[]},{time:.33,scene:0,people:[{trackId:'a',x:.1,y:0,w:.1,h:.2,association:.9}]}]};
assert.equal(vm.runInContext('visiblePeople(gap,.16).length',context),1);
vm.runInContext('gap.frames[2].scene=1',context);
assert.equal(vm.runInContext('visiblePeople(gap,.16).length',context),0);
console.log('PASS: stable trio before the event, explicit missing-identity status and bounded interpolation.');
// The reviewed collaboration keeps five distinct identities and gives both defenders directions.
context.cooperation=JSON.parse(fs.readFileSync(path.join(root,'web/demo/analysis.json'),'utf8'));
vm.runInContext('state.offline=true;state.results.set(state.id,cooperation);state.playerId=null;render();',context);
nodes.get('video').currentTime=8.63;vm.runInContext('renderOverlay()',context);
for(const id of ['P6','P2','P1','P21','P30'])assert(nodes.get('overlay').innerHTML.includes(`data-focus="${id}"`));
for(const id of ['actor-P6','support-P2','defender-P21','defender-P30'])assert(nodes.get('overlay').innerHTML.includes(`direction-${id}`),`Expected future direction for ${id}`);
assert(!nodes.get('overlay').innerHTML.includes('direction-beneficiary-P1'));
assert(!nodes.get('overlay').innerHTML.includes('stroke-dasharray="6 6"'));
assert(nodes.get('role-strip').innerHTML.includes('协同队友'));
assert(nodes.get('impact-content').innerHTML.includes('63'));
assert.equal(context.cooperation.events[0].score,null);
console.log('PASS: five-person collaboration, four movement arrows, and presentation score separate from algorithm output.');
