/* Real local UI/API/SQLite; AI providers disabled. No external calls. */
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.AI_TEST_URL||'http://127.0.0.1:8315';
if(!['127.0.0.1','localhost'].includes(new URL(base).hostname))throw Error('Local test only');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge',args:['--disable-background-networking']});
 try{
  const context=await browser.newContext({viewport:{width:375,height:812}});
  await context.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  const response=await context.request.post(base+'/api/v2/dev/seed');assert.equal(response.status(),200);
  const couple=await response.json();const a=couple.members[0];
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);
  await page.evaluate(s=>localStorage.setItem('chandelle-v2',JSON.stringify(s)),{...couple,active:a.id});
  await page.reload();
  await page.locator('[data-route="discover"]').first().click();
  await page.locator('#web-query').fill('Une exposition à Paris dimanche');
  await page.locator('#web-discover input[name="cloud_consent"]').check();
  await page.locator('#web-discover button').click();
  await page.getByText('La recherche OpenAI n’est pas activée sur ce serveur.').waitFor();
  await page.screenshot({path:'.runtime/ai-discover-mobile.png',fullPage:false});
  await page.locator('[data-action="ai-budget"]').click();
  await page.getByRole('heading',{name:'Quota local OpenAI'}).waitFor();
  await page.locator('[data-action="close"]').click();
  await page.locator('[data-route="memories"]').first().click();
  await page.locator('#conversation-text').fill('J’aime le jazz. Je déteste le cinéma.');
  await page.locator('#conversation-privacy').selectOption('COUPLE_RECOMMENDATION');
  await page.locator('#conversation-memory button').click();
  await page.waitForFunction(()=>document.querySelector('#main')?.textContent.includes('discussion:dislikes:'));
  await page.screenshot({path:'.runtime/ai-memory-mobile.png',fullPage:false});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,'375px overflow');
  const budget=await context.request.get(base+'/api/v2/ai/budget',{headers:{'X-Member-Token':a.token}});
  assert.equal((await budget.json()).total_reserved,0);
  assert.deepEqual(errors,[]);
  console.log('PASS: 375px Discover disabled state, quota modal, French conversation -> persisted memory, zero paid calls');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
