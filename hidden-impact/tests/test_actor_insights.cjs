const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const view=fs.readFileSync(path.join(__dirname,'../web/insights-view.js'),'utf8').replace(/export /g,'');
const ctx=vm.createContext({});vm.runInContext(view,ctx);
const html=ctx.gravityMarkup({actorProfile:{name:'主角<script>',scope:'赛季',games:55,creation:.33,scoring:.24,finishing:{made:7,sampleCount:8,actual:.875,expected:.741375}},gravity:{player:'other',axes:[]}});
assert(html.includes('创造机会影响力'));assert(html.includes('+0.33'));assert(html.includes('8 投 7 中'));assert(html.includes('74.1%'));assert(!html.includes('other'));assert(!html.includes('<script>'));
const missing=ctx.gravityMarkup({actorProfile:{name:'主角',scope:'赛季',creation:null,scoring:null,finishing:null}});assert(!missing.includes('NaN'));assert(!missing.includes('0.00'));
console.log('PASS: actor evidence, source values, escaping and missing values');
