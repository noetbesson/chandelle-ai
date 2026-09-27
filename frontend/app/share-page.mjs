import {getDraft,claimDraft,deleteDraft,setDraftJob} from './share-store.mjs';
import {configureExperiences,reelForm,submitExperience} from './experiences.mjs';
const status=document.querySelector('#share-status'),error=document.querySelector('#share-error');
const content=document.querySelector('#share-content'),choose=document.querySelector('#choose-profile'),select=document.querySelector('#share-profile');
const cancel=document.querySelector('#cancel-share'),back=document.querySelector('#return-to-inspirations');
const params=new URLSearchParams(location.search),id=params.get('id');
let draft,selected=null,busy=false,epoch=0;
function session(){try{return JSON.parse(localStorage.getItem('chandelle-v2')||'null');}catch{return null;}}
function owner(member){return session()?.couple_id+':'+member.id;}
function current(){return selected&&session()?.members?.find(m=>m.id===selected.id&&m.token===selected.token);}
function failure(e){error.textContent=e.message||'Le partage n’a pas pu être traité.';}
function requireIdentity(identity){if(identity!==epoch||!current())throw Error('Le profil a changé. Choisissez à nouveau votre profil.');}
async function api(path,options={}){
  const identity=epoch;requireIdentity(identity);
  const videoUpload=path==='/reels/upload?wait=true';
  const response=await fetch('/api/v2'+(videoUpload?'/reels/upload':path),{method:options.method||'GET',headers:{'X-Member-Token':selected.token,...(options.raw?{}:{'Content-Type':'application/json'})},body:options.raw??(options.body?JSON.stringify(options.body):undefined),cache:'no-store'});
  requireIdentity(identity);
  let value;try{value=await response.json();}catch{throw Error('Réponse serveur illisible. Vérifiez la connexion.');}
  if(!response.ok)throw Error(value?.error?.message||value?.message||'Import refusé. Vérifiez votre profil et les deux entretiens.');
  if(videoUpload&&value.job_id){
    if(id){await setDraftJob(id,owner(selected),value.job_id);draft.jobId=value.job_id;}
    return followJob(value.job_id,identity);
  }
  return value;
}
async function followJob(jobId,identity){
  const labels={upload:'Vidéo reçue',extraction:'Extraction audio',transcription:'Traitement de l’audio',normalization:'Analyse des goûts',memory:'Ajout à la mémoire',complete:'Mémoire créée'};
  for(let attempt=0;attempt<240;attempt++){
    requireIdentity(identity);
    const state=await api('/reels/jobs/'+encodeURIComponent(jobId));
    status.textContent=labels[state.phase]||'Traitement en cours';
    if(state.status==='completed')return state;
    if(state.status==='failed'){
      if(id){await setDraftJob(id,owner(selected),null);draft.jobId=null;}
      throw Error('Le traitement a échoué ('+(state.error||'inconnu')+'). Vous pouvez réessayer ou utiliser une légende.');
    }
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
  throw Error('Le traitement continue côté serveur. Rechargez cette page pour reprendre son suivi.');
}
async function finish(){
  const identity=epoch;requireIdentity(identity);
  if(id)await deleteDraft(id);
  requireIdentity(identity);
  const saved=session();saved.active=selected.id;localStorage.setItem('chandelle-v2',JSON.stringify(saved));
  content.hidden=true;choose.hidden=true;cancel.hidden=true;back.hidden=false;
  status.textContent='Inspiration ajoutée à votre mémoire privée. Ouvrez vos inspirations pour corriger et confirmer les goûts.';
  history.replaceState(null,'','/partager');
}
configureExperiences({api,identity:()=>epoch,receivedVideo:()=>draft?.video||null,finishReel:finish,navigate:async()=>{},notify:()=>{}});

async function render(){
  if(draft?.jobId){
    content.replaceChildren();content.hidden=false;
    const resume=document.createElement('button');resume.className='primary';resume.textContent='Reprendre le suivi du traitement';
    resume.addEventListener('click',()=>run(async()=>{await followJob(draft.jobId,epoch);await finish();}));content.append(resume);return;
  }
  content.innerHTML=reelForm();content.hidden=false;
  const form=content.querySelector('form');
  form.querySelector('[name=caption]').value=draft?.caption||'';
  form.querySelector('[name=source_url]').value=draft?.url||'';
  if(draft?.video){
    const input=form.querySelector('[name=video]');input.required=false;input.disabled=true;
    const info=document.createElement('p');info.textContent='Fichier reçu : '+draft.video.name+' ('+(draft.video.size/1024/1024).toFixed(1)+' Mio).';input.after(info);
    status.textContent='Vidéo reçue. Vérifiez la légende puis ajoutez-la à vos inspirations.';
  }else{
    status.textContent=id?'Lien ou texte reçu, sans fichier vidéo. Ajoutez la vidéo obtenue avec autorisation ou gardez une piste à confirmer.':'Ajoutez votre vidéo, ou collez un lien avec une description.';
    const note=document.createElement('button');note.type='button';note.className='quiet spaced';note.textContent='Enregistrer le lien ou la description comme piste';
    note.addEventListener('click',()=>run(async()=>{
      if(!form.querySelector('[name=consent]').checked)throw Error('Confirmez votre autorisation d’utiliser ce contenu.');
      const caption=form.querySelector('[name=caption]').value.trim(),url=form.querySelector('[name=source_url]').value.trim();
      if(!caption&&!url)throw Error('Ajoutez une description ou un lien.');
      const platform=url.includes('tiktok.com')?'tiktok':url.includes('instagram.com')?'instagram':'manual';
      const date=form.querySelector('[name=signal_at]').value||null;
      await api('/inspirations/import',{method:'POST',body:{platform,format:'text',content:[caption,url].filter(Boolean).join('\n'),signal_at:date,privacy_scope:'PRIVATE'}});
      await finish();
    }));form.append(note);
  }
}
async function run(action){
  if(busy)return;busy=true;error.textContent='';select.disabled=true;cancel.disabled=true;
  for(const button of content.querySelectorAll('button'))button.disabled=true;
  try{await action();}catch(e){failure(e);if(draft&&!draft.jobId&&selected&&content.querySelector('form')===null)await render();}finally{
    busy=false;select.disabled=false;cancel.disabled=false;
    for(const button of content.querySelectorAll('button'))button.disabled=false;
  }
}
content.addEventListener('submit',event=>{event.preventDefault();run(()=>submitExperience(event.target));});
select.addEventListener('change',async()=>{
  const version=++epoch;selected=null;content.hidden=true;error.textContent='';
  const member=session()?.members?.find(m=>m.id===select.value);
  if(!member)return;
  try{
    if(id){draft=await claimDraft(id,owner(member));if(version!==epoch)return;}
    selected=member;await render();
  }catch(e){failure(e);}
});
cancel.addEventListener('click',()=>run(async()=>{const jobStarted=Boolean(draft?.jobId);if(id)await deleteDraft(id);draft=null;selected=null;epoch++;content.hidden=true;choose.hidden=true;cancel.hidden=true;status.textContent=jobStarted?'Brouillon supprimé de cet appareil. Le traitement déjà lancé peut continuer : son résultat se trouve dans vos inspirations.':'Partage supprimé de cet appareil. Rien n’a été ajouté à la mémoire.';history.replaceState(null,'','/partager');}));
addEventListener('storage',event=>{if(event.key==='chandelle-v2'){epoch++;selected=null;content.hidden=true;select.value='';failure(Error('La session a changé. Rechargez la page pour choisir votre profil.'));}});
async function start(){
  if(params.has('error')){status.textContent='Le partage n’a pas été conservé.';failure(Error('Réessayez avec une seule vidéo MP4/MOV de moins de 32 Mio, ou utilisez l’import manuel. Vérifiez aussi l’espace disponible sur le téléphone.'));}
  if(id){
    if(!/^[0-9a-f-]{36}$/i.test(id))throw Error('Référence de partage invalide.');
    draft=await getDraft(id);if(!draft)throw Error('Ce partage est expiré ou a déjà été supprimé. Partagez-le à nouveau.');
    cancel.hidden=false;
  }
  const saved=session();
  if(!saved?.couple_id||!saved.members?.length){status.textContent='Ouvrez Chandelle et terminez les entretiens, puis revenez ici. Le partage reçu reste en attente sur cet appareil pendant 24 heures.';back.hidden=false;back.textContent='Ouvrir Chandelle';back.href='/';return;}
  for(const member of saved.members){const option=document.createElement('option');option.value=member.id;option.textContent=member.name||'Mon profil';select.append(option);}
  choose.hidden=false;
  if(!params.has('error'))status.textContent='Choisissez le profil auquel appartient cette inspiration.';
}
start().catch(e=>{status.textContent='Réception indisponible.';failure(e);});
