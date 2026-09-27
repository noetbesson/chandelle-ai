/* Real local UI/API/SQLite. Synthetic manual slots and catalogue, no external provider calls. */
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.CALENDAR_TEST_URL||'http://127.0.0.1:8316';
if(!['127.0.0.1','localhost'].includes(new URL(base).hostname))throw Error('Local test only');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge',args:['--disable-background-networking']});
 try{
  const context=await browser.newContext({viewport:{width:375,height:812}});
  await context.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
  const seed=await context.request.post(base+'/api/v2/dev/seed');assert.equal(seed.status(),200);
  const couple=await seed.json();const start=new Date();start.setUTCDate(start.getUTCDate()+1);start.setUTCHours(16,0,0,0);const end=new Date(+start+5*3600000);
  for(const member of couple.members){
   const headers={'X-Member-Token':member.token};
   assert.equal((await context.request.put(base+'/api/v2/availability',{headers,data:{slots:[{start:start.toISOString(),end:end.toISOString()}]}})).status(),200);
   assert.equal((await context.request.put(base+'/api/v2/proactive/settings',{headers,data:{enabled:true}})).status(),200);
  }
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.evaluate(s=>localStorage.setItem('chandelle-v2',JSON.stringify(s)),{...couple,active:couple.members[0].id});await page.reload();
  await page.locator('[data-route="availability"]').first().click();await page.getByRole('heading',{name:'Mon agenda connecté'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Google Calendar',exact:true}).isDisabled(),true);
  await page.screenshot({path:'.runtime/calendar-settings-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Test : ignorer les sept jours'}).click();
  await page.getByRole('heading',{name:'Une proposition vous attend'}).waitFor();
  await page.getByRole('button',{name:'Voir le programme',exact:true}).click();
  await page.locator('dialog [data-action="keep"]').first().click();
  await page.locator('dialog [data-action="keep"]').first().filter({hasText:'Kept'}).waitFor();
  await page.locator('dialog [data-action="replace"]').last().click();
  await page.locator('dialog [data-action="plan-status"][data-value="accepted"]').click();
  await page.getByRole('heading',{name:'Ajouter cette sortie aux agendas'}).waitFor();
  assert.equal(await page.locator('dialog [data-action="calendar-confirm"]').isDisabled(),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.getByRole('heading',{name:'Ajouter cette sortie aux agendas'}).scrollIntoViewIfNeeded();
  await page.screenshot({path:'.runtime/calendar-mobile.png',fullPage:false});
  assert.deepEqual(errors,[]);
  console.log('PASS Calendar 375px: unavailable OAuth, two consents, manual trigger, persisted notification, open plan, keep/replace, accept and calendar panel. No external calendar connected.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
