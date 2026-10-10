const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx=vm.createContext({});vm.runInContext(fs.readFileSync(__dirname+'/../web/story-playback.js','utf8').replace(/export /g,''),ctx);
const timeline={beats:[{sourceTime:2,start:2,end:4,duration:2},{sourceTime:6,start:8,end:10.5,duration:2.5}]};
for(const [src,edited] of [[0,0],[1.5,1.5],[2,2],[3,5],[6,8],[7,11.5]]){
 assert.equal(ctx.replayTime(src,timeline),edited);assert.equal(ctx.sourceTime(edited,timeline),src);
}
assert.equal(ctx.sourceTime(3.5,timeline),2);assert.equal(ctx.sourceTime(9.5,timeline),6);
assert.equal(ctx.sourceTime(10.5,timeline),6);assert.equal(ctx.sourceTime(12,timeline),7.5);
assert.equal(ctx.replayTime(4,null),4);assert.equal(ctx.sourceTime(4,null),4);
console.log('PASS: freeze seeks, replay/original synchronization and legacy replay compatibility.');
