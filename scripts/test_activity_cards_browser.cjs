/* Local API and mobile UI with an explicitly injected provider test double. */
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.DECK_TEST_URL||'http://127.0.0.1:8321';
if(!['127.0.0.1','localhost'].includes(new URL(base).hostname))throw Error('Local test only');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge',args:['--disable-background-networking']});
 try{
  const context=await browser.newContext({viewport:{width:375,height:812}});
  await context.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
  const seed=await context.request.post(base+'/api/v2/dev/seed');assert.equal(seed.status(),200);
  const couple=await seed.json(),member=couple.members[0],auth={'X-Member-Token':member.token};
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.evaluate(s=>localStorage.setItem('chandelle-v2',JSON.stringify(s)),{...couple,active:member.id});await page.reload();
  await page.locator('[data-route="ask"]').first().click();
  assert.equal(await page.locator('#mode').count(),0);assert.equal(await page.locator('[name="cloud_consent"]').count(),0);
  await page.locator('#query').fill('Une sortie à deux');await page.locator('#budget').fill('150');await page.locator('#date').fill('2026-10-02');
  const waiting=page.waitForResponse(r=>r.url().endsWith('/api/v2/dates/search'));
  await page.locator('#ask button[type="submit"]').click();const response=await waiting;assert.equal(response.status(),200);const data=await response.json();
  await page.locator('.activity-choice').waitFor();assert.equal(await page.locator('.activity-choice').count(),1);
  assert.ok(data.activities.length>3);assert.doesNotMatch(await page.locator('#main').innerText(),/OpenAI|ChatGPT|GPT/);
  const card=page.locator('.activity-choice');await card.focus();await page.keyboard.press('Enter');
  assert.match(await page.locator('.builder-toggle').innerText(),/1 gardée/);
  await page.locator('.activity-choice').focus();await page.keyboard.press('ArrowLeft');
  assert.match(await page.locator('.builder-toggle').innerText(),/1 gardée/);
  await page.locator('[data-activity-action="view"]').click();assert.ok(await page.locator('.activity-choice').count()>3);
  await page.locator('[data-activity-action="view"]').click();assert.match(await page.locator('.builder-toggle').innerText(),/1 gardée/);
  // A real pointer gesture, rather than synthetic pointercapture with an unknown ID.
  await page.locator('.activity-picture').evaluate(el=>el.scrollIntoView({block:'center'}));let box=await page.locator('.activity-picture').boundingBox();
  await page.mouse.move(box.x+box.width*.35,box.y+70);await page.mouse.down();await page.mouse.move(box.x+box.width*.8,box.y+75,{steps:8});await page.mouse.up();
  await page.waitForFunction(()=>document.querySelector('.builder-toggle')?.textContent.includes('2 gardées'));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('.activity-choice').evaluate(el=>el.scrollIntoView({block:'start'}));await page.screenshot({path:'.runtime/activity-mobile.png',fullPage:false});
  // Reset selection, then choose a known coherent pair from the same actual search.
  await page.locator('[data-activity-action="builder"]').click();
  while(await page.locator('.kept-list [data-activity-action="remove"]').count())await page.locator('.kept-list [data-activity-action="remove"]').first().click();
  await page.locator('[data-activity-action="builder"]').click();
  await page.locator('[data-activity-action="view"]').click();
  const wanted=data.proposals[0].activities.map(a=>a.id);
  for(const id of wanted){const button=page.locator(`.activity-choice [data-activity-action="keep"][data-id="${id}"]`);if(await button.count()===0){await page.locator('[data-activity-action="review"]').click();}await button.click();}
  // Failed composition preserves the entire selection and permits retry.
  await context.route('**/api/v2/dates/compose',route=>route.fulfill({status:503,json:{error:{message:'Interruption de test, réessayez.'}}}),{times:1});
  await page.locator('[data-activity-action="compose"]').click();await page.getByText('Interruption de test, réessayez.').waitFor();
  assert.equal(await page.locator('.kept-row').count(),2);
  const compose=page.waitForResponse(r=>r.url().endsWith('/dates/compose'));
  await page.locator('[data-activity-action="compose"]').click();const cr=await compose;assert.equal(cr.status(),200,await cr.text());const final=await cr.json();
  assert.deepEqual(final.activities.map(a=>a.id),wanted);assert.equal(final.status,'draft');
  await page.locator('dialog[open]').waitFor();assert.doesNotMatch(await page.locator('dialog[open]').innerText(),/OpenAI|ChatGPT/);
  // Existing replace and keep actions on final summary still work.
  const other=final.activities[1];const replaced=page.waitForResponse(r=>r.url().includes('/replace')&&r.request().method()==='POST');
  await page.locator('dialog[open] [data-action="replace"]').first().click();const rr=await replaced;assert.equal(rr.status(),200,await rr.text());
  assert.deepEqual((await rr.json()).activities[1],other);
  const confirmed=page.waitForResponse(r=>r.url().endsWith('/date-plans/'+final.id)&&r.request().method()==='PATCH');
  await page.locator('dialog[open] [data-action="plan-status"][data-value="accepted"]').click();assert.equal((await confirmed).status(),200);
  assert.equal((await (await context.request.get(base+'/api/v2/date-plans/'+final.id,{headers:auth})).json()).status,'accepted');
  await page.getByRole('heading',{name:'Ajouter cette sortie aux agendas'}).waitFor();await page.locator('dialog[open] [data-action="close"]').click();await page.locator('dialog[open]').waitFor({state:'hidden'});
  await page.setViewportSize({width:1440,height:1000});await page.locator('.activity-discovery').evaluate(el=>el.scrollIntoView({block:'start'}));await page.screenshot({path:'.runtime/activity-desktop.png',fullPage:false});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  // Brand/engine selectors must also be absent in memory, inspirations, settings, calendar.
  for(const target of ['memories','inspirations','availability','settings']){
   await page.goto(base);await page.locator('#main').waitFor();await page.waitForFunction(()=>!document.querySelector('#main .loading'));await page.evaluate(target=>{const button=document.createElement('button');button.dataset.route=target;document.body.append(button);button.click();button.remove();},target);
   await page.waitForFunction(()=>!document.querySelector('#main .loading'));
   assert.doesNotMatch(await page.locator('#main').innerText(),/OpenAI|ChatGPT|\bGPT\b/);
   assert.equal(await page.locator('[name="cloud_consent"]').count(),0);
  }
  // Component-only fixture with nine examples, zero backend needed.
  const fixture=await context.newPage();await fixture.goto(base+'/v2-static/index.html');
  const {mockActivitySearch}=await import('../frontend/tests/activity-data.mjs');
  await fixture.evaluate(async mockActivitySearch=>{
   const {ActivitySwipeDeck}=await import('/v2-static/ActivitySwipeDeck.mjs');
   document.body.innerHTML='<main id="fixture" style="padding:16px"></main>';
   window.fixtureDeck=new ActivitySwipeDeck(document.querySelector('#fixture'),mockActivitySearch,{identity:()=> 'mock',api:async()=>{throw Error('Simulation locale')},open:async()=>{},choose:async()=>{}});
  },mockActivitySearch);
  await fixture.locator('[data-activity-action="view"]').click();assert.equal(await fixture.locator('.activity-choice').count(),9);
  await fixture.locator('[data-activity-action="keep"]').first().click();await fixture.locator('[data-activity-action="keep"]').first().click();
  await fixture.locator('[data-activity-action="builder"]').click();await fixture.getByText(/se chevauchent/).waitFor();
  assert.equal(await fixture.locator('.kept-row').count(),2);assert.equal(await fixture.locator('[data-activity-action="compose"]').isEnabled(),true);
  // Pending response cannot display A's plan after identity change.
  await fixture.evaluate(async ({plan,mockActivitySearch})=>{
   window.fixtureDeck.destroy();let owner='a';let release;let displayed=false;
   const {ActivitySwipeDeck}=await import('/v2-static/ActivitySwipeDeck.mjs');
   const deck=new ActivitySwipeDeck(document.querySelector('#fixture'),mockActivitySearch,{identity:()=>owner,api:()=>new Promise(r=>release=r),open:async()=>{},choose:async()=>{displayed=true;}});
   document.querySelector('[data-activity-action="keep"]').click();
   document.querySelector('[data-activity-action="compose"]').click();
   owner='b';release(plan);await new Promise(r=>setTimeout(r,0));
   if(displayed)throw Error('Previous profile result displayed');deck.destroy();
  },{plan:final,mockActivitySearch});assert.deepEqual(errors,[]);
  console.log('PASS ActivitySwipeDeck 375px/desktop: actual search, independent swipe/buttons/arrows, persistent selection, retry, compose/replace/accept, nine test contracts, overlap warning, no engine prompts or overflow. Providers disabled.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
