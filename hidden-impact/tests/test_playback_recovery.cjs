const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx=vm.createContext({setTimeout,clearTimeout});vm.runInContext(fs.readFileSync('web/playback-recovery.js','utf8').replace('export ',''),ctx);
(async()=>{
 let events={},calls=0,reloads=[],messages=[],resolve;
 const video={currentTime:6,paused:false,addEventListener:(k,f)=>events[k]=f};
 const recovery=ctx.createPlaybackRecovery(video,{refresh:async()=>{calls++;return 'fresh-'+calls},reload:(...a)=>reloads.push(a),message:(...a)=>messages.push(a)});
 events.play();await events.error();await new Promise(r=>setImmediate(r));
 assert.equal(calls,1);assert.deepEqual(reloads[0],['fresh-1',6,true]);
 await events.error();await new Promise(r=>setImmediate(r));await events.error();await new Promise(r=>setImmediate(r));assert.equal(calls,2);
 assert.equal(messages.at(-1)[1],true);
 recovery.reset();events={};reloads=[];
 const second=ctx.createPlaybackRecovery(video,{refresh:()=>new Promise(r=>resolve=r),reload:(...a)=>reloads.push(a),message:()=>{}});
 events.error();second.reset();resolve('old-round');await new Promise(r=>setImmediate(r));assert.equal(reloads.length,0);
 console.log('PASS: bounded URL recovery resumes time; stale callbacks cannot replace a new round.');
})().catch(e=>{console.error(e);process.exitCode=1});
