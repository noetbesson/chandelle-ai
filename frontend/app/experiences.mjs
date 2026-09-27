// Peer-inspired journeys on the existing authenticated API and single memory.
const escape = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const format = stamp => new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',dateStyle:'medium',timeStyle:'short'}).format(new Date(stamp));
let ctx;
const selected=new Map();
export function configureExperiences(context){ctx=context;}
export function resetSelection(){selected.clear();}
export const selectionIds=()=>[...selected.keys()];
export function selectButton(a){return `<button data-action="compare-toggle" data-id="${escape(a.id)}" data-title="${escape(a.title)}" aria-pressed="${selected.has(a.id)}">${selected.has(a.id)?'✓ Sélectionné':'Comparer'}</button>`;}
export const compareBar=()=>`<div class="selection-bar" id="comparison"><span>Jusqu’à 5 idées à comparer · 3 activités par programme</span><button data-action="compare-open">Voir mes choix (${selected.size})</button></div>`;
const privacy=(value='PRIVATE')=>`<label>Utilisation des goûts confirmés<select name="privacy_scope"><option value="PRIVATE" ${value==='PRIVATE'?'selected':''}>Privé · uniquement moi</option><option value="COUPLE_RECOMMENDATION" ${value==='COUPLE_RECOMMENDATION'?'selected':''}>Recommandations · sans montrer mon contenu</option><option value="SHARED" ${value==='SHARED'?'selected':''}>Partagé · visible à deux</option></select></label>`;

export const reelForm=()=>`<form id="reel-import" class="card"><h2>Importer une vidéo Instagram ou TikTok</h2><p class="muted">Ajoutez un fichier obtenu avec autorisation. Aucun téléchargement depuis le lien. Sans transcription configurée, seule la légende fournit des goûts proposés.</p><label>Vidéo MP4 ou MOV, 32 Mio maximum et 3 minutes<input name="video" type="file" accept=".mp4,.mov,video/mp4,video/quicktime" required></label><label>Légende ou description<textarea name="caption" maxlength="10000" placeholder="Collez la légende du Reel ici"></textarea></label><label>Lien d’origine (facultatif)<input name="source_url" type="url" placeholder="https://www.instagram.com/reel/..."></label><label>Date du partage ou du favori, si connue<input name="signal_at" type="date"></label><label><input name="consent" type="checkbox" value="true" required> Je suis autorisé à utiliser ce fichier.</label><label><input name="cloud_consent" type="checkbox" value="true"> J’autorise l’envoi de l’audio et du texte aux fournisseurs configurés par le serveur (Gradium, OpenAI ou Pipelex).</label><p class="muted">L’import reste privé. Vous pourrez corriger et confirmer les goûts avant leur utilisation dans les recommandations.</p><p class="muted" data-reel-status role="status" aria-live="polite"></p><button class="primary spaced">Ajouter à mes inspirations</button></form>`;

export async function inspirations(){
  const result=await ctx.api('/inspirations');
  return `<div class="eyebrow">CE QUI VOUS DONNE ENVIE</div><h1>Une idée aujourd’hui.<br>Un souvenir demain.</h1><p class="muted">Gardez une adresse, une légende de Reel ou un export de favoris. Relisez les goûts proposés avant de les utiliser dans vos prochains programmes.</p>
  ${reelForm()}
  <p><a href="/installer">Recevoir depuis le bouton Partager du téléphone</a></p>
  <form id="signal-import" class="card"><h2>Ajouter une inspiration</h2><div class="form-grid"><label>Source<select name="platform"><option value="manual">Note personnelle</option><option value="google_maps">Google Maps</option><option value="instagram">Instagram</option><option value="tiktok">TikTok</option></select></label><label>Format<select name="format"><option value="text">Texte ou lien partagé</option><option value="csv">CSV Google Maps</option><option value="json">Export JSON</option></select></label></div><label>Importer un fichier (facultatif)<input type="file" name="file" accept=".json,.csv,.txt"></label><label>Ou coller le contenu<textarea name="content" maxlength="1000000" placeholder="J’aimerais essayer un atelier de céramique…"></textarea></label><p class="muted">Un lien seul est conservé sans télécharger la page ni inventer son contenu. Les imports restent dans votre mémoire privée jusqu’à votre choix de partage.</p><label>Date du signal (facultatif)<input type="date" name="signal_at"></label><button class="primary spaced">Analyser l’inspiration</button></form>
  <div class="grid two spaced">${result.items.map(f=>`<article class="card"><span class="badge">${escape(f.value.platform)} · ${escape(f.privacy_scope)}</span><p class="spaced signal-text">${escape(f.value.text||'Lien sans contenu')}</p>${f.value.source_url?`<p class="muted signal-text">${escape(f.value.source_url)}</p>`:''}${f.value.taste_signal?`<p class="muted">Analyse ${escape(f.value.normalization_backend||'inconnue')} · ${f.value.transcription_status==='transcribed'?'audio transcrit':'aucune transcription disponible, légende seulement'}. Goûts à vérifier.</p>`:''}<small>Signal : ${f.value.signal_at?format(f.value.signal_at):'date inconnue'} · import ${format(f.value.imported_at)}</small><form id="signal-confirm" data-id="${escape(f.id)}"><label>Goûts à retenir · séparés par des virgules<input name="tags" maxlength="1000" value="${escape((f.value.values||f.value.proposed_tags||[]).join(', '))}"></label><label>Durée<select name="horizon"><option value="durable">Goût durable</option><option value="temporary" ${f.value.horizon==='temporary'?'selected':''}>Envie temporaire · 45 jours après le signal</option></select></label>${privacy(f.privacy_scope)}<button class="primary spaced">${f.value.confirmed?'Mettre à jour':'Confirmer ces goûts'}</button></form><button class="quiet spaced" data-action="signal-delete" data-id="${escape(f.id)}">Supprimer cette inspiration</button></article>`).join('')||'<p class="empty">Vos inspirations apparaîtront ici.</p>'}</div>`;
}

export async function availability(){
  const state=await ctx.api('/availability');
  const own=state.own_slots;
  const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const google=`<section class="card"><h2>Importer mon Google Calendar</h2><p>Chandelle retire vos événements pour calculer vos créneaux libres de 30 minutes ou plus, dans les heures choisies.</p><form id="calendar-import"><label>Adresse iCal Google Calendar<input name="url" type="password" required autocomplete="off" maxlength="2048" placeholder="https://calendar.google.com/calendar/ical/…/basic.ics"></label><p class="muted">Google Calendar → Paramètres → votre agenda → Intégrer l’agenda → Adresse secrète au format iCal (ou adresse publique iCal). Le lien habituel du navigateur ne suffit pas.</p><div class="form-grid"><label>À partir du<input name="start_date" type="date" required value="${today}"></label><label>Nombre de jours<input name="days" type="number" min="1" max="31" required value="14"></label><label>Sorties possibles à partir de<input name="daily_start" type="time" required value="08:00"></label><label>Jusqu’à<input name="daily_end" type="time" required value="23:00"></label></div><p class="privacy">Le lien donne accès à cet agenda : gardez-le privé. Il est utilisé uniquement pour cet import. Les titres, lieux et événements ne sont pas enregistrés ; votre partenaire voit seulement vos créneaux communs.</p><p class="muted">Cet import remplace vos disponibilités actuelles. Refaites-le après une modification dans Google : aucune synchronisation automatique. Un seul agenda est lu, pas tous les agendas superposés dans Google Calendar.</p><button class="primary spaced">Calculer mes disponibilités</button></form>${state.calendar_import?`<p class="spaced">Dernier import : ${format(state.calendar_import.imported_at)} · ${escape(state.calendar_import.days)} jours à partir du ${escape(state.calendar_import.start_date)}.</p>`:''}</section>`;
  return `<div class="eyebrow">FAIRE DE LA PLACE POUR NOUS</div><h1>Le bon moment,<br>pour tous les deux.</h1><p class="muted">Heures de Paris. Importez vos disponibilités depuis Google Calendar ou saisissez-les manuellement. Seuls leurs croisements servent à composer les programmes.</p>${google}<section class="card"><h2>Mes disponibilités</h2><p>${state.mode==='demo'?'Aucun agenda saisi : le créneau fictif de démonstration est utilisé.':state.both_configured?'Les deux agendas ont été renseignés.':'Il manque encore les disponibilités de votre partenaire.'}</p><form id="availability-add" data-slots="${escape(JSON.stringify(own))}"><div class="form-grid"><label>Début<input name="start" type="datetime-local" required></label><label>Fin<input name="end" type="datetime-local" required></label></div><button class="primary spaced">Ajouter ce créneau</button></form><div class="stack spaced">${own.map((s,i)=>`<div class="row between"><span>${format(s.start)} → ${format(s.end)}</span><button data-action="slot-delete" data-index="${i}" data-slots="${escape(JSON.stringify(own))}">Retirer</button></div>`).join('')||'<p class="muted">Aucun créneau personnel enregistré.</p>'}</div></section><section class="card spaced"><h2>${state.mode==='demo'?'Créneau de démonstration':'Nos créneaux communs'}</h2>${state.common_slots.map(s=>`<p>${format(s.start)} → ${format(s.end)}</p>`).join('')||'<p>Aucun créneau commun pour le moment.</p>'}<button data-route="ask">Composer notre sortie →</button></section>`;
}

export async function submitExperience(form){
  if(!['reel-import','signal-import','signal-confirm','availability-add','calendar-import'].includes(form.id))return false;
  const identity=ctx.identity();
  const data=new FormData(form);
  if(form.id==='calendar-import'){
    if(identity!==ctx.identity())throw Error('Le profil actif a changé.');
    const result=await ctx.api('/availability/google-calendar',{method:'POST',body:{url:String(data.get('url')||'').trim(),start_date:data.get('start_date'),days:Number(data.get('days')),daily_start:data.get('daily_start'),daily_end:data.get('daily_end')}});
    if(identity!==ctx.identity())return true;
    form.reset();await ctx.navigate('availability');ctx.notify(`${result.imported_slots} créneau(x) libre(s) importé(s).`);
  }else if(form.id==='reel-import'){
    const received=ctx.receivedVideo?.();
    if(received)data.set('video',received,received.name||'partage.mp4');
    const file=data.get('video');
    if(!file?.size)throw Error('Choisissez une vidéo MP4 ou MOV.');
    if(file.size>32*1024*1024)throw Error('Vidéo limitée à 32 Mio.');
    if(!/\.(mp4|mov)$/i.test(file.name))throw Error('Formats acceptés : MP4 et MOV.');
    if(data.get('consent')!=='true')throw Error('Confirmez votre autorisation d’utiliser ce fichier.');
    if(data.get('signal_at'))data.set('signal_at',new Date(data.get('signal_at')+'T00:00:00Z').toISOString());
    const status=form.querySelector?.('[data-reel-status]');
    if(status)status.textContent='Envoi et analyse en cours. Gardez cette page ouverte.';
    try{
      const result=await ctx.api('/reels/upload?wait=true',{method:'POST',raw:data});
      await ctx.finishReel?.(result);
      if(identity!==ctx.identity())throw Error('Le profil actif a changé.');
      await ctx.navigate('inspirations');ctx.notify('Vidéo traitée. Relisez et confirmez les goûts proposés.');
    }finally{if(status)status.textContent='';}
  }else if(form.id==='signal-import'){
    const file=data.get('file');
    if(file?.size>1000000)throw Error('Import limité à 1 Mo.');
    const content=file?.size?await file.text():String(data.get('content')||'');
    if(identity!==ctx.identity())throw Error('Le profil actif a changé.');
    const result=await ctx.api('/inspirations/import',{method:'POST',body:{platform:data.get('platform'),format:data.get('format'),content,signal_at:data.get('signal_at')||null,privacy_scope:'PRIVATE'}});
    await ctx.navigate('inspirations');ctx.notify(`${result.items.length} inspiration(s), ${result.duplicates} doublon(s). ${result.warnings.join(' ')}`);
  }else if(form.id==='signal-confirm'){
    await ctx.api('/inspirations/'+form.dataset.id+'/confirm',{method:'POST',body:{tags:String(data.get('tags')).split(',').map(x=>x.trim()).filter(Boolean),horizon:data.get('horizon'),privacy_scope:data.get('privacy_scope')}});
    await ctx.navigate('inspirations');ctx.notify('Goûts enregistrés avec votre choix de partage.');
  }else{
    const slots=JSON.parse(form.dataset.slots);slots.push({start:data.get('start'),end:data.get('end')});
    await ctx.api('/availability',{method:'PUT',body:{slots}});await ctx.navigate('availability');
  }
  return true;
}

export async function clickExperience(button){
  const action=button.dataset.action;
  if(action==='compare-toggle'){
    const id=button.dataset.id;
    if(selected.has(id))selected.delete(id);else{if(selected.size>=5)throw Error('Choisissez au maximum cinq idées.');selected.set(id,button.dataset.title);}
    button.textContent=selected.has(id)?'✓ Sélectionné':'Comparer';button.setAttribute('aria-pressed',String(selected.has(id)));
    const bar=document.querySelector('#comparison');if(bar)bar.outerHTML=compareBar();return true;
  }
  if(action==='compare-open'){
    if(!selected.size)throw Error('Sélectionnez au moins une activité.');
    const result=await ctx.api('/activities/compare',{method:'POST',body:{activity_ids:selectionIds()}});
    ctx.modal(`<h2>Vos idées, côte à côte</h2><div class="comparison-table"><table><caption>Prix pour deux · exemples fictifs</caption><thead><tr><th>Activité</th><th>Budget</th><th>Durée</th></tr></thead><tbody>${result.items.map(a=>`<tr><td>${escape(a.title)}</td><td>${a.price_per_person===null?'Inconnu':escape(a.price_per_person*2)+' €'}</td><td>${escape(a.duration_minutes)} min</td></tr>`).join('')}</tbody></table></div><p class="spaced">Total ${result.budget_complete?'':'connu : '}${escape(result.known_total_eur)} € pour deux.</p><p class="muted">${escape(result.message)}</p>${selected.size<=3?'<button class="primary" data-action="compose-selection">Composer avec ces choix →</button>':'<p>Revenez à la liste et gardez au maximum trois activités pour composer un programme.</p>'}`);return true;
  }
  if(action==='compose-selection'){
    const ids=selectionIds();document.querySelector('dialog')?.close();await ctx.navigate('planner');
    ctx.setRequired(ids);
    document.querySelector('#selected-activity').innerHTML=`<p class="privacy">${ids.length} choix imposés à la composition. Le serveur vérifiera leur compatibilité. <button type="button" data-action="remove-selected">Retirer les choix</button></p>`;
    document.querySelector('#query').value='Un programme autour de nos choix';document.querySelector('#count').value=String(ids.length);return true;
  }
  if(action==='signal-delete'){
    await ctx.api('/memories/'+button.dataset.id,{method:'DELETE'});await ctx.navigate('inspirations');return true;
  }
  if(action==='slot-delete'){
    const slots=JSON.parse(button.dataset.slots);slots.splice(Number(button.dataset.index),1);
    await ctx.api('/availability',{method:'PUT',body:{slots}});await ctx.navigate('availability');return true;
  }
  if(action==='prepare-booking'){
    const result=await ctx.api('/date-plans/'+button.dataset.id+'/booking',{method:'POST',body:{}});
    ctx.modal(`<h2>Préparer votre sortie</h2><p>${escape(result.message)}</p>${result.actions.map(a=>`<article class="card spaced"><h3>${escape(a.title)}</h3><p>${format(a.start)} · ${a.participants} personnes · ${escape(a.price_per_person)} € / personne</p><span class="badge">${a.demo?'Exemple fictif':'Disponibilité à vérifier'}</span>${a.booking_url?`<a href="${escape(a.booking_url)}" target="_blank" rel="noopener noreferrer">Continuer chez le prestataire</a>`:'<p class="muted">Pas de lien de réservation vérifié pour cette activité.</p>'}</article>`).join('')}<button class="spaced" data-action="calendar-export" data-id="${escape(button.dataset.id)}">Exporter dans mon calendrier (.ics)</button>`);return true;
  }
  if(action==='calendar-export'){
    const response=await ctx.download('/date-plans/'+button.dataset.id+'/calendar');
    const url=URL.createObjectURL(response);const link=document.createElement('a');link.href=url;link.download='chandelle.ics';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return true;
  }
  return false;
}
