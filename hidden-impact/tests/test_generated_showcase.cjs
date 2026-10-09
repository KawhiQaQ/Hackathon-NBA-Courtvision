// Exercise both result-manifest and authenticated-job routes of the same viewer.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.join(__dirname,'..');
const view=fs.readFileSync(path.join(root,'web/insights-view.js'),'utf8').replace(/export /g,'');
const source=fs.readFileSync(path.join(root,'web/showcase.js'),'utf8').replace(/^import .*;\n/,'');
const html=fs.readFileSync(path.join(root,'web/index.html'),'utf8');
const result={schema:'hidden-impact/showcase-v1',mode:'analysis',rendered:true,video:'replay.mp4',original:'original.mp4',matchup:'甲队对乙队',actor:{id:'new-actor',label:'甲队接应者'},actionTitle:'持球牵动',summary:'球权转向外线。',storyTitle:'配合过程',score:48,components:[],roles:[{displayName:'甲队接应者 · 主角',name:'甲队接应者',color:'#f4c45e'},{displayName:'甲队终结者 · 收益队友',name:'甲队终结者',color:'#77cfe4'}],evidence:[{time:1,image:'frame-1.jpg',label:'迎球',text:'接应球员向外移动。',chapter:'接应',fact:{label:'画面证据',value:'1s'}}],insights:{shot:null,gravity:null,cues:[{start:0,end:3,seek:1,phase:'迎球',title:'迎球',text:'接应球员向外移动。',evidence:'1s'}],narration:{segments:[{start:0,end:3,title:'迎球',text:'接应球员向外移动。'}]}}};
function node(){return {innerHTML:'',textContent:'',value:'1',hidden:true,dataset:{},style:{},currentTime:0,duration:3,readyState:2,paused:true,scrollLeft:0,clientWidth:500,scrollWidth:1000,classList:{toggle(){}},setAttribute(k,v){this[k]=v},removeAttribute(k){delete this[k]},addEventListener(){},querySelectorAll(){return []},querySelector(){return null},pause(){this.paused=true},play(){return Promise.resolve()},load(){},scrollBy(){}};}
async function run(search,failed=false){
 const nodes=new Map();for(const m of html.matchAll(/id="([^"]+)"/g))nodes.set(m[1],node());
 const selectors=new Map();const document={getElementById:id=>{assert(nodes.has(id),id);return nodes.get(id)},querySelectorAll:()=>[],querySelector:s=>{if(!selectors.has(s))selectors.set(s,node());return selectors.get(s)},addEventListener(){}};
 const requests=[];const manifest=structuredClone(result);
 if(search.includes('job=')){manifest.video='https://assets.example/replay?sig=1';manifest.original='https://assets.example/original?sig=1';manifest.evidence[0].image='https://assets.example/frame?sig=1';}
 const context=vm.createContext({document,window:{addEventListener(){}},URL,URLSearchParams,Blob,console,location:{search,href:'http://localhost/'+search,origin:'http://localhost'},sessionStorage:{getItem:()=> 'key'},fetch:async(url,options)=>{requests.push({url:String(url),options});return {ok:!failed,status:failed?401:200,json:async()=>search.includes('job=')?{result:{presentation:manifest}}:manifest};}});
 await vm.runInContext(view+'\n(async()=>{'+source+'})()',context);
 if(failed){assert.equal(nodes.get('load-error').hidden,false);assert.equal(selectors.get('.layout').hidden,true);assert(!nodes.get('replay').src);return;}
 assert.equal(nodes.get('load-error').hidden,true);assert.equal(nodes.get('actor-name').textContent,'甲队接应者');assert.equal(nodes.get('score').textContent,48);
 assert.equal(nodes.get('matchup').textContent,'甲队对乙队');assert.equal(nodes.get('data-insights').hidden,true);assert.equal(nodes.get('cue-title').textContent,'迎球');
 assert.equal(selectors.get('.layout').hidden,false);assert(nodes.get('frames').innerHTML.includes('接应球员向外移动'));
 if(search.includes('job=')){assert.equal(requests[0].options.headers['X-Team-Key'],'key');assert.equal(nodes.get('replay').src,manifest.video);}
 else{assert.equal(nodes.get('replay').src,'http://localhost/results/example/replay.mp4');assert(nodes.get('frames').innerHTML.includes('http://localhost/results/example/frame-1.jpg'));}
}
(async()=>{await run('?result=results/example/showcase.json');await run('?job=new-job');await run('?job=new-job',true);console.log('PASS: generated manifest, authenticated job, timed commentary, missing data, relative assets and no demo fallback on failure.');})().catch(e=>{console.error(e);process.exitCode=1});
