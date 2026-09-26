// Temporary reception on this device. This is not a second profile/memory database.
export const MAX_VIDEO=32*1024*1024;
export const TTL=24*60*60*1000;
export const MAX_DRAFTS=5;
const DB='chandelle-share-inbox';
const STORE='drafts';

export function safeSource(value){
  if(!value)return '';
  let u;try{u=new URL(value);}catch{throw Error('Le lien partagé est invalide.');}
  const h=u.hostname.toLowerCase();
  if(u.protocol!=='https:'||u.username||u.password||value.length>2048||!(h==='instagram.com'||h.endsWith('.instagram.com')||h==='tiktok.com'||h.endsWith('.tiktok.com')))
    throw Error('Utilisez un lien HTTPS Instagram ou TikTok. Aucun lien ne sera téléchargé.');
  return u.href;
}
export function draftFromForm(form,stamp=Date.now()){
  const keys=[...form.keys()];
  if(keys.length!==new Set(keys).size||keys.some(k=>!['title','text','url','video'].includes(k)))throw Error('Partage non pris en charge : champs répétés ou inconnus.');
  const text=name=>{const v=form.get(name)||'';if(typeof v!=='string'||v.length>10000)throw Error('Texte partagé invalide ou trop long.');return v.trim();};
  const title=text('title'),body=text('text'),explicit=text('url');
  const embedded=body.match(/https:\/\/[^\s<>"']+/)?.[0]?.replace(/[),.;]+$/,'')||'';
  const url=safeSource(explicit||embedded);
  const caption=[title,body.replace(/https?:\/\/\S+/g,'').trim()].filter(Boolean).join('\n');
  if(caption.length>10000)throw Error('Légende limitée à 10 000 caractères.');
  let video=form.get('video');
  if(video && typeof video!=='string' && video.size===0)video=null;
  if(video && (!(video instanceof Blob)||!video.size||video.size>MAX_VIDEO||!['video/mp4','video/quicktime',''].includes(video.type)||(! /\.(mp4|mov)$/i.test(video.name||'')&&!['video/mp4','video/quicktime'].includes(video.type))))throw Error('Ajoutez une seule vidéo MP4 ou MOV de 32 Mio maximum.');
  if(video){
    const extension=/\.(mp4|mov)$/i.test(video.name||'')?'':video.type==='video/quicktime'?'.mov':'.mp4';
    const name=(video.name||'partage')+extension;
    video=new File([video],name,{type:video.type||(name.toLowerCase().endsWith('.mov')?'video/quicktime':'video/mp4')});
  }
  if(!video&&!url&&!caption)throw Error('Le partage est vide.');
  return {id:crypto.randomUUID(),createdAt:stamp,expiresAt:stamp+TTL,caption,url,video:video||null,owner:null};
}
async function open(){
  if(!globalThis.indexedDB)throw Error('Le stockage local est indisponible. Utilisez l’import manuel.');
  return new Promise((resolve,reject)=>{
    const r=indexedDB.open(DB,1);
    r.onupgradeneeded=()=>r.result.createObjectStore(STORE,{keyPath:'id'});
    r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('Le stockage du partage est indisponible.'));
  });
}
async function transaction(action){
  const db=await open();
  try{return await new Promise((resolve,reject)=>{
    const tx=db.transaction(STORE,'readwrite'),store=tx.objectStore(STORE);let value,error;
    tx.oncomplete=()=>resolve(value);tx.onabort=tx.onerror=()=>reject(error||Error('Impossible de conserver ce partage sur l’appareil.'));
    const done=v=>{value=v;};const fail=e=>{error=e;tx.abort();};
    action(store,done,fail);
  });}finally{db.close();}
}
export async function saveDraft(draft){
  return transaction((store,done,fail)=>{
    const r=store.getAll();r.onsuccess=()=>{
      const valid=r.result.filter(d=>d.expiresAt>Date.now());
      for(const d of r.result)if(d.expiresAt<=Date.now())store.delete(d.id);
      if(valid.length>=MAX_DRAFTS){fail(Error('Cinq partages sont déjà en attente. Terminez ou supprimez un import.'));return;}
      store.add(draft);done(draft.id);
    };
  });
}
export async function getDraft(id){
  return transaction((store,done)=>{const r=store.getAll();r.onsuccess=()=>{for(const d of r.result)if(d.expiresAt<=Date.now())store.delete(d.id);done(r.result.find(d=>d.id===id&&d.expiresAt>Date.now())||null);};});
}
export async function claimDraft(id,owner){
  return transaction((store,done,fail)=>{const r=store.get(id);r.onsuccess=()=>{
    const d=r.result;
    if(!d||d.expiresAt<=Date.now()){if(d)store.delete(id);fail(Error('Ce partage a expiré. Recommencez depuis Instagram ou TikTok.'));return;}
    if(d.owner&&d.owner!==owner){fail(Error('Ce partage appartient à un autre profil.'));return;}
    d.owner=owner;store.put(d);done(d);
  };});
}
export async function deleteDraft(id){return transaction((store,done)=>{store.delete(id);done();});}
export async function clearDrafts(){return transaction((store,done)=>{store.clear();done();});}

export async function setDraftJob(id,owner,jobId){
  return transaction((store,done,fail)=>{const r=store.get(id);r.onsuccess=()=>{
    const draft=r.result;if(!draft||draft.owner!==owner){fail(Error('Le partage n’est plus disponible pour ce profil.'));return;}
    draft.jobId=jobId;store.put(draft);done();
  };});
}
