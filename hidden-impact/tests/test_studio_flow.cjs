const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'../web',name),'utf8');
function element(){return {hidden:true,attrs:{},listeners:{},dataset:{},textContent:'',setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this.attrs[k];if(k==='href')delete this.href},getAttribute(k){return k==='href'?this.href??null:this.attrs[k]??null},addEventListener(k,fn){this.listeners[k]=fn},pause(){this.paused=true}};}
// A completed result must route to the same job across all three views. Clearing it
// for a new upload must disable every forward link, rather than expose the old job.
{
 const nodes={'view-presentation':element(),'upload-next':element()},links=Array.from({length:4},element);let observer;
 vm.runInNewContext(read('upload-flow.js'),{document:{getElementById:id=>nodes[id],querySelectorAll:()=>links},URL,location:{href:'https://example.com/workbench.html'},MutationObserver:class{constructor(fn){observer=fn}observe(){}}});
 assert.equal(nodes['upload-next'].getAttribute('aria-disabled'),'true');
 nodes['view-presentation'].hidden=false;nodes['view-presentation'].href='https://example.com/?job=actual-job';observer();
 assert.equal(nodes['upload-next'].href,'https://example.com/?job=actual-job#video');
 for(const [i,view] of ['video','story','data'].entries())assert.equal(links[i+1].href,`https://example.com/?job=actual-job#${view}`);
 nodes['view-presentation'].hidden=true;observer();
 for(const link of [nodes['upload-next'],...links.slice(1)]){assert.equal(link.getAttribute('aria-disabled'),'true');assert.equal(link.getAttribute('href'),null);}
}
// Same-document steps preserve the loaded result, pause playback when leaving,
// and handle browser Back plus optional game summary routing.
{
 const ids=['awards','awards-link','next-page','next-label','previous-page','page-count','data-notes-open','replay','frames','leaderboard','data-notes-close','data-notes'];
 const nodes=Object.fromEntries(ids.map(id=>[id,element()])),links=['video','story','data'].map(view=>Object.assign(element(),{dataset:{viewLink:view}}));
 const body={dataset:{}},handlers={},location={hash:''};let observer;
 const document={body,getElementById:id=>nodes[id],querySelectorAll:()=>links};
 vm.runInNewContext(read('flow-view.js'),{document,location,window:{addEventListener:(key,fn)=>handlers[key]=fn,dispatchEvent(){}},requestAnimationFrame:fn=>fn(),Event:class{},MutationObserver:class{constructor(fn){observer=fn}observe(){}}});
 assert.equal(body.dataset.view,'video');assert.equal(nodes['next-page'].href,'#story');
 location.hash='#story';handlers.hashchange();assert.equal(nodes.replay.paused,true);assert.equal(nodes['next-page'].href,'#data');assert.equal(links[1].attrs['aria-current'],'step');
 location.hash='#data';handlers.hashchange();assert.equal(nodes['next-page'].href,'workbench.html');assert.equal(nodes['data-notes-open'].hidden,false);
 nodes.awards.hidden=false;observer();assert.equal(nodes['next-page'].href,'#awards');
 location.hash='#video';handlers.hashchange();assert.equal(body.dataset.view,'video');assert.equal(nodes['data-notes-open'].hidden,true);
 location.hash='#unknown';handlers.hashchange();assert.equal(body.dataset.view,'video');
}
console.log('PASS: four-step navigation, same-job handoff, reset gating, playback pause and game summary.');
