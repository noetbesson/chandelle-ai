const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base='http://127.0.0.1:8321';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge',args:['--disable-background-networking']});
 try{
  const context=await browser.newContext({viewport:{width:375,height:812}});
  await context.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
  const seed=await context.request.post(base+'/api/v2/dev/seed');assert.equal(seed.status(),200);
  const couple=await seed.json(),member=couple.members[0];
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.evaluate(s=>localStorage.setItem('chandelle-v2',JSON.stringify(s)),{...couple,active:member.id});await page.reload();
  await page.locator('[data-route="discover"]').first().click();
  await page.locator('#query').fill('Un japonais puis une balade');await page.locator('#date').fill('2026-10-02');
  await page.locator('#budget').fill('150');
  const response=page.waitForResponse(r=>r.url().endsWith('/api/v2/dates/search'));
  await page.locator('#discover button[type="submit"]').click();const data=await (await response).json();
  await page.locator('.activity-choice').waitFor();assert.ok(data.activities.length>2);
  assert.ok(data.activities.every(a=>a.source_url&&!a.demo));
  assert.equal(await page.locator('.activity-choice').count(),1);
  await page.locator('.activity-choice').focus();await page.keyboard.press('Enter');
  assert.match(await page.locator('.builder-toggle').innerText(),/1 gardée/);
  await page.locator('[data-activity-action="view"]').click();
  assert.ok(await page.locator('.activity-choice').count()>1);
  await page.locator('[data-activity-action="view"]').click();
  assert.match(await page.locator('.builder-toggle').innerText(),/1 gardée/);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'.runtime/web-cards-mobile.png',fullPage:true});
  // Replay actual captured web facts through the same component; no new paid call.
  const captured=JSON.parse(fs.readFileSync('.runtime/web-live-result.json','utf8'));
  await page.route('**/api/v2/dates/search',r=>r.fulfill({json:captured}));
  await page.locator('[data-route="ask"]').first().click();await page.locator('#query').fill('Un japonais puis une balade');
  await page.locator('#ask button[type="submit"]').click();await page.locator('.activity-choice').waitFor();
  const name=await page.locator('.activity-choice h3').innerText();assert.ok(captured.activities.some(a=>a.name===name));
  assert.match(await page.locator('.activity-choice').innerText(),/Consulter la source/);
  await page.screenshot({path:'.runtime/web-live-cards-mobile.png',fullPage:true});
  await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:'.runtime/web-live-cards-desktop.png',fullPage:true});
  await page.unroute('**/api/v2/dates/search');
  for(const [reason,message] of [['no_web_results','Aucune piste trouvée sur le web'],['all_filtered','Filtre bloquant : budget'],['provider_timeout','La recherche a pris trop de temps']]){
    await page.route('**/api/v2/dates/search',r=>r.fulfill({json:{...captured,activities:[],proposals:[],warnings:[],empty_reason:reason,message}}));
    await page.locator('#ask button[type="submit"]').click();await page.getByText(message,{exact:true}).waitFor();
    assert.equal(await page.locator('.activity-choice').count(),0);await page.unroute('**/api/v2/dates/search');
  }
  assert.deepEqual(errors,[]);console.log('PASS real local API simulation + recorded live web cards, Ask/Discover same route, swipe/select/views, 375px/desktop, three explicit empty states.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
