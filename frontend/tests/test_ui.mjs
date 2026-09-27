// Browserless behavior checks; no network or package installation required.
import assert from 'node:assert/strict';
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
let sequence=0;
async function boot(saved,responses){
  const calls=[];const listeners={};const callbacks={};const app={innerHTML:''};const main={innerHTML:''};const notice={};
  globalThis.document={querySelector(selector){return selector==='#app'?app:selector==='#notice'?notice:selector==='#main'?main:null},querySelectorAll(){return[]},addEventListener(type,callback){(callbacks[type]||=[]).push(callback);listeners[type]=async event=>{await Promise.all(callbacks[type].map(fn=>fn(event)))}}};
  globalThis.localStorage={getItem(){return saved?JSON.stringify(saved):null},setItem(){}};
  globalThis.fetch=async(url,options)=>{calls.push({url,options});const data=responses[url];assert.notEqual(data,undefined,'Unexpected API request: '+url);return{ok:true,status:200,json:async()=>data}};
  await import('../app/app.mjs?test='+sequence++);await tick();
  return{app,main,calls,listeners,async click(action,id){const button={dataset:{action,id}};await listeners.click({target:{closest(){return button}}});await tick()}};
}
let ui=await boot(null,{});
assert.match(ui.app.innerHTML,/Two people/);
assert.doesNotMatch(ui.app.innerHTML,/aria-label="Main navigation"/);
assert.equal(ui.calls.length,0);
const members=[{id:'a',name:'Alex',role:'A',token:'token-a'},{id:'b',name:'Blair',role:'B',token:'token-b'}];
ui=await boot({couple_id:'c',members,active:'a'},{'/api/v2/onboarding/status?couple_id=c':{couple_id:'c',completed:false,members:[{...members[0],status:'completed'},{...members[1],status:'in_progress',current_step:3}]},'/api/v2/onboarding/couples/c/members/b':{current_step:3,answers:[{step:3,value:{values:['crowds']},privacy_scope:'PRIVATE'}]}});
assert.match(ui.app.innerHTML,/Pass the device to Blair/);
assert.doesNotMatch(ui.app.innerHTML,/aria-label="Main navigation"/);
assert.equal(ui.calls.length,1,'Handoff must fetch status only, never completed partner answers');
await ui.click('interview','b');
assert.match(ui.app.innerHTML,/3 of 7/);
assert.match(ui.app.innerHTML,/BLAIR|Blair/);
assert.match(ui.app.innerHTML,/value="crowds" checked/);
assert.equal(ui.calls.at(-1).options.headers['X-Member-Token'],'token-b');
assert.ok(ui.calls.every(c=>!c.url.includes('/members/a')),'Never retrieve Person A answers while Person B resumes');
ui=await boot({couple_id:'c',members,active:'b'},{'/api/v2/onboarding/status?couple_id=c':{completed:false,members:[{...members[0],status:'not_started'},{...members[1],status:'not_started'}]}});
assert.match(ui.app.innerHTML,/Pass the device to Alex/);
assert.doesNotMatch(ui.app.innerHTML,/crowds/,'Prior private screen must not survive a handoff');
ui=await boot(null,{'/api/v2/health':{schema_version:1},'/api/v2/integrations':{openai:{enabled:false},developer_mode:false}});
await ui.click('settings');
assert.match(ui.app.innerHTML,/Return to onboarding/);
assert.doesNotMatch(ui.app.innerHTML,/data-action="seed"|Load developer demo/);
await ui.click('seed'); // An old/stale button cannot inject or switch to a demo profile.
assert.ok(ui.calls.every(c=>!c.url.endsWith('/dev/seed')));
assert.equal(ui.calls.filter(c=>c.url==='/api/v2/integrations').length,1,'One settings action must issue one integration request, even with multiple listeners');
assert.doesNotMatch(ui.app.innerHTML,/aria-label="Main navigation"/,'Pre-onboarding settings must never mount main navigation');
const privateIdentity='SECRET PRIVATE IDENTITY';
ui=await boot({couple_id:'c',members,active:'a'},{'/api/v2/onboarding/status?couple_id=c':{completed:false,members:[{...members[0],status:'in_progress'},{...members[1],status:'not_started'}]},'/api/v2/onboarding/couples/c/members/a':{current_step:2,answers:[{step:1,value:{name:privateIdentity},privacy_scope:'PRIVATE'}]},'/api/v2/onboarding/couples/c/members/a/answers':{current_step:2}});
await ui.click('interview','a');
globalThis.HTMLFormElement=class {id='interview';dataset={step:'1'};querySelector(){return null}querySelectorAll(){return[]}};
const nativeFormData=globalThis.FormData;
globalThis.FormData=class {get(key){return {name:privateIdentity,pronouns:'',privacy_scope:'PRIVATE'}[key]}};
await ui.listeners.submit({target:new HTMLFormElement(),preventDefault(){},submitter:{}});
globalThis.FormData=nativeFormData;
assert.equal(ui.calls.filter(c=>c.url.endsWith('/answers')).length,1,'One interview submission must be saved once');
assert.doesNotMatch(ui.app.innerHTML,new RegExp(privateIdentity),'Private identity answer must not replace public device identity labels');
assert.match(ui.app.innerHTML,/Alex/);
console.log('Frontend browserless checks: welcome gate, partial completion gate, private handoff, server resume, active token isolation, old-screen removal, pre-onboarding settings gate, private identity labels PASS');

// Journal is loaded from owner-authenticated endpoints and escapes stored text.
ui=await boot({couple_id:'c',members,active:'a'},{
  '/api/v2/onboarding/status?couple_id=c':{completed:true,members},
  '/api/v2/suggestions':{items:[]}, '/api/v2/date-plans':{items:[]},
  '/api/v2/couples/c/profile':{},
  '/api/v2/conversations':{items:[{id:'s1',created_at:'2026-09-26'}]},
  '/api/v2/conversations/s1':{messages:[{content:'<script>PRIVATE JOURNAL</script>',created_at:'2026-09-26'}]},
});
await ui.listeners.click({target:{closest(){return {dataset:{route:'journal'}}}}});
assert.match(ui.main.innerHTML,/&lt;script&gt;PRIVATE JOURNAL/);
assert.doesNotMatch(ui.main.innerHTML,/<script>/);
assert.match(ui.main.innerHTML,/id="conversation-form"/);
assert.match(ui.main.innerHTML,/value="AUTO" selected/);
assert.ok(ui.calls.filter(c=>c.url.includes('/conversations')).every(c=>c.options.headers['X-Member-Token']==='token-a'));
await ui.click('switch','b');
assert.match(ui.app.innerHTML,/Pass the device to Blair/);
assert.doesNotMatch(ui.app.innerHTML,/PRIVATE JOURNAL/);
console.log('Journal UI PASS: real owner endpoints, escaped history, automatic privacy choice, handoff.');

// Ask is the default; Settings contains the secondary pages; idle UI makes no provider call.
ui=await boot({couple_id:'c',members,active:'a'},{
  '/api/v2/onboarding/status?couple_id=c':{completed:true,members},
  '/api/v2/integrations':{}, '/api/v2/health':{},
  '/api/v2/availability':{mode:'manual',own_slots:[],common_slots:[]},
  '/api/v2/inspirations':{items:[]},
  '/api/v2/memories?scope=PERSON&entity_id=a':{items:[]},
  '/api/v2/profiles/PERSON/a':{}, '/api/v2/history':{items:[]},
  '/api/v2/activities?query=&category=&limit=100':{items:[]},
  '/api/v2/activities/real':{items:[{id:'real-1',name:'Exposition test',type:'exposition',price_per_person:null,website:'https://example.org/expo'}]},
});
const visit=route=>ui.listeners.click({target:{closest(){return {dataset:{route}}}}});
assert.match(ui.app.innerHTML,/data-route="ask" class="active"/);
assert.deepEqual([...ui.app.innerHTML.matchAll(/data-route="([^"]+)"/g)].map(m=>m[1]),['ask','discover','settings']);
assert.match(ui.main.innerHTML,/data-action="voice-start"/);
assert.match(ui.main.innerHTML,/voice-candles/);
assert.doesNotMatch(ui.main.innerHTML,/Discuter avec Chandelle|web-discover|ask-planner|data-route="inspirations"|data-route="availability"/);
assert.deepEqual(ui.calls.map(c=>c.url),['/api/v2/onboarding/status?couple_id=c']);
const beforeDiscover=ui.calls.length;
await visit('discover');
assert.match(ui.app.innerHTML,/data-route="discover" class="active"/);
assert.match(ui.main.innerHTML,/Exposition test/);
assert.match(ui.main.innerHTML,/id="discover"/);
assert.doesNotMatch(ui.main.innerHTML,/voice-start|voice-panel|web-discover|ask-planner/);
assert.deepEqual(ui.calls.slice(beforeDiscover).map(c=>c.url).sort(),[
  '/api/v2/activities/real','/api/v2/activities?query=&category=&limit=100',
].sort());
await visit('settings');
assert.match(ui.app.innerHTML,/data-route="settings" class="active"/);
assert.deepEqual([...ui.main.innerHTML.matchAll(/data-route="([^"]+)"/g)].map(m=>m[1]),['availability','inspirations','memories','history','preferences']);
for(const [route,content] of [['availability',/calendar-import/],['inspirations',/reel-import/],['memories',/conversation-memory/],['history',/Good moments stay with you/],['preferences',/Who’s holding the device/]]){
 await visit(route);
 assert.match(ui.app.innerHTML,/data-route="settings" class="active"/);
 assert.match(ui.app.innerHTML,/← Settings/);
 assert.match(ui.main.innerHTML,content);
 await visit('settings');
}
await visit('planner');assert.match(ui.main.innerHTML,/id="ask"/);
await visit('web-search');assert.match(ui.main.innerHTML,/id="web-discover"/);
await visit('home'); // Historical links return to the new main page.
assert.match(ui.main.innerHTML,/data-action="voice-start"/);
assert.ok(ui.calls.every(c=>!c.url.endsWith('/chat')),'Navigation must not start a dialogue or paid provider call');
console.log('Ask/Discover/Settings navigation PASS: idle candle by default, three tabs, five settings pages with back navigation, preserved advanced tools, no automatic chat request.');
