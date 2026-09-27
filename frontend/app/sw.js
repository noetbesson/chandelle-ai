import {draftFromForm,saveDraft,MAX_VIDEO} from '/v2-static/share-store.mjs';
const CACHE='chandelle-public-v3';
const ASSETS=['/v2-static/style.css','/v2-static/icons/chandelle-192.png','/v2-static/icons/chandelle-512.png'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)));});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{for(const key of await caches.keys())if(key.startsWith('chandelle-public-')&&key!==CACHE)await caches.delete(key);await self.clients.claim();})());});
async function receiveShare(request){
  try{
    if(!request.headers.get('content-type')?.startsWith('multipart/form-data'))throw Error('Format de partage non pris en charge.');
    const max=MAX_VIDEO+65536;
    if(Number(request.headers.get('content-length'))>max)throw Error('Vidéo trop volumineuse (32 Mio maximum).');
    const reader=request.body.getReader(),chunks=[];let size=0;
    const timer=setTimeout(()=>reader.cancel(),30000);
    try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>max){await reader.cancel();throw Error('Vidéo trop volumineuse (32 Mio maximum).');}chunks.push(value);}}
    finally{clearTimeout(timer);reader.releaseLock();}
    const form=await new Response(new Blob(chunks),{headers:{'Content-Type':request.headers.get('content-type')}}).formData();
    const draft=draftFromForm(form);await saveDraft(draft);
    return Response.redirect(new URL('/partager?id='+draft.id,self.location.origin),303);
  }catch{
    // No submitted data, filenames or URLs in logs, redirect or public cache.
    return Response.redirect(new URL('/partager?error=reception',self.location.origin),303);
  }
}
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin)return;
  if(event.request.method==='POST'&&url.pathname==='/api/receive-share'){
    if(event.request.mode!=='navigate'&&event.request.headers.get('origin')!==self.location.origin){event.respondWith(new Response('Partage refusé',{status:403}));return;}
    event.respondWith(receiveShare(event.request));return;
  }
  // Never cache API responses, profiles, captions, uploaded videos or app HTML.
  if(event.request.method==='GET'&&ASSETS.includes(url.pathname)&&!url.search){event.respondWith(caches.match(event.request).then(hit=>hit||fetch(event.request)));}
});
