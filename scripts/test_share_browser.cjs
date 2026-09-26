/* Real Chromium service worker + IndexedDB + FastAPI. No external provider calls. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.SHARE_TEST_URL||'http://127.0.0.1:8314';
if(!['127.0.0.1','localhost'].includes(new URL(base).hostname))throw Error('Local browser test only');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge',args:['--disable-background-networking']});
 try{
 const context=await browser.newContext({viewport:{width:375,height:812},serviceWorkers:'allow'});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const seed=await context.request.post(base+'/api/v2/dev/seed');assert.equal(seed.status(),200);const couple=await seed.json();const [a,b]=couple.members;
 await page.goto(base+'/installer');await page.evaluate(()=>navigator.serviceWorker.ready);await page.reload();
 await page.waitForFunction(()=>navigator.serviceWorker.controller!==null);
 await page.evaluate(s=>localStorage.setItem('chandelle-v2',JSON.stringify(s)),{...couple,active:a.id});
 async function share(fields,video){
  await page.goto(base+'/installer');await page.waitForFunction(()=>navigator.serviceWorker.controller!==null);
  await page.evaluate(values=>{
   const form=document.createElement('form');form.id='test-native-share';form.action='/api/receive-share';form.method='POST';form.enctype='multipart/form-data';
   for(const [key,value]of Object.entries(values)){const input=document.createElement('input');input.name=key;input.value=value;form.append(input);}
   const file=document.createElement('input');file.name='video';file.type='file';form.append(file);
   const send=document.createElement('button');send.textContent='Send fixture';form.append(send);document.body.append(form);
  },fields);
  if(video)await page.locator('#test-native-share input[type=file]').setInputFiles(video);
  else await page.locator('#test-native-share input[type=file]').evaluate(el=>el.remove());
  await page.locator('#test-native-share button').click();await page.waitForURL(/\/partager\?id=/);
  await page.locator('#share-profile').waitFor({state:'visible'});return new URL(page.url()).searchParams.get('id');
 }
 async function facts(member){const r=await context.request.get(base+'/api/v2/inspirations',{headers:{'X-Member-Token':member.token}});assert.equal(r.status(),200);return (await r.json()).items;}
 const linkId=await share({title:'Un atelier <script>danger</script>',text:'https://www.instagram.com/reel/testshare/'});
 assert.equal(await page.locator('#share-content').isVisible(),false,'No shared content before explicit profile choice');
 await page.selectOption('#share-profile',a.id);
 await page.locator('#share-content form').waitFor({state:'visible'});
 assert.match(await page.locator('#share-status').innerText(),/sans fichier/);
 assert.equal(await page.locator('[name=source_url]').inputValue(),'https://www.instagram.com/reel/testshare/');
 assert.equal(await page.locator('#share-content script').count(),0);
 await page.screenshot({path:path.resolve('.runtime/pwa-link-mobile.png'),fullPage:true});
 await page.check('[name=consent]');await page.getByRole('button',{name:'Enregistrer le lien ou la description comme piste'}).click();
 await page.locator('#return-to-inspirations').waitFor({state:'visible'});
 const own=await facts(a);assert.equal(own.length,1);assert.equal(own[0].privacy_scope,'PRIVATE');assert.equal(own[0].value.confirmed,false);assert.equal(own[0].value.taste_signal,undefined);assert.equal((await facts(b)).length,0);
 assert.equal(await page.evaluate(async id=>(await import('/v2-static/share-store.mjs')).getDraft(id),linkId),null);
 // Existing file ingestion, using an actual synthetic MP4 and the same OS-style POST.
 const fileId=await share({title:'Un concert jazz à Paris',url:'https://www.tiktok.com/@fixture/video/123456789'},path.resolve('.runtime/pwa-fixture.mp4'));
 await page.selectOption('#share-profile',b.id);await page.locator('#share-content form').waitFor({state:'visible'});
 assert.equal(await page.locator('[name=video]').isDisabled(),true);
 await page.check('[name=consent]');await page.getByRole('button',{name:'Ajouter à mes inspirations'}).click();
 await page.locator('#return-to-inspirations').waitFor({state:'visible',timeout:60000});
 const second=await facts(b);assert.equal(second.length,1);assert.equal(second[0].value.taste_signal.source,'reel');assert.equal(second[0].value.taste_signal.raw_transcript,'');assert.ok(second[0].value.proposed_tags.includes('jazz'));assert.equal(second[0].value.confirmed,false);
 assert.equal(await page.evaluate(async id=>(await import('/v2-static/share-store.mjs')).getDraft(id),fileId),null);
 await page.screenshot({path:path.resolve('.runtime/pwa-success-mobile.png'),fullPage:true});
 // Resume an already submitted real server job after the receiving page was closed.
 const resumed=await context.request.post(base+'/api/v2/reels/upload',{headers:{'X-Member-Token':b.token},multipart:{consent:'true',caption:'Un atelier de céramique',source_url:'https://www.tiktok.com/@fixture/video/987654321',video:{name:'resume.mp4',mimeType:'video/mp4',buffer:fs.readFileSync('.runtime/pwa-fixture.mp4')}}});
 assert.equal(resumed.status(),202);const job=await resumed.json();
 const resumeId=await page.evaluate(async input=>{
   const m=await import('/v2-static/share-store.mjs'),form=new FormData();form.set('text','Un atelier');
   const d=m.draftFromForm(form);await m.saveDraft(d);await m.claimDraft(d.id,input.owner);await m.setDraftJob(d.id,input.owner,input.job);return d.id;
 },{owner:couple.couple_id+':'+b.id,job:job.job_id});
 await page.goto(base+'/partager?id='+resumeId);await page.selectOption('#share-profile',b.id);
 await page.getByRole('button',{name:'Reprendre le suivi du traitement'}).click();await page.locator('#return-to-inspirations').waitFor({state:'visible'});
 assert.equal((await facts(b)).length,2);
 // IndexedDB enforces a claimed owner; pending content does not migrate on switching.
 const claimed=await share({text:'https://www.instagram.com/reel/private/'});
 await page.selectOption('#share-profile',a.id);await page.locator('#share-content form').waitFor({state:'visible'});
 await page.selectOption('#share-profile',b.id);await page.waitForFunction(()=>document.querySelector('#share-error').textContent.includes('autre profil'));
 assert.equal(await page.locator('#share-content').isVisible(),false);
 await page.click('#cancel-share');assert.equal(await page.evaluate(async id=>(await import('/v2-static/share-store.mjs')).getDraft(id),claimed),null);
 // Real IndexedDB quota/expiry and only public assets in CacheStorage.
 const storage=await page.evaluate(async()=>{
   const m=await import('/v2-static/share-store.mjs');await m.clearDrafts();
   const create=stamp=>{const f=new FormData();f.set('text','jazz');return m.draftFromForm(f,stamp);};
   const old=create(Date.now()-m.TTL-1);await m.saveDraft(old);const expired=await m.getDraft(old.id);
   for(let i=0;i<5;i++)await m.saveDraft(create(Date.now()));
   let capped=false;try{await m.saveDraft(create(Date.now()));}catch{capped=true;}
   await m.clearDrafts();let urls=[];for(const k of await caches.keys()){const c=await caches.open(k);urls.push(...(await c.keys()).map(r=>r.url));}
   return {expired,capped,urls};
 });
 assert.equal(storage.expired,null);assert.equal(storage.capped,true);assert.ok(storage.urls.every(u=>/\/v2-static\/(style\.css|icons\/)/.test(u)));
 assert.deepEqual(errors,[]);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'375px layout must not overflow');
 console.log('Browser PASS: installed-worker POST link/file, explicit owner, private memory, real FFmpeg, link-only honesty, owner conflict, resume job, deletion, expiry/quota, static-only cache, 375px. Native Android share sheet not exercised.');
 await context.close();
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
