const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=v=>v?new Date(v).toLocaleString('fr-FR',{timeZone:'Europe/Paris'}):'Jamais';

export async function calendarPanel({api}){
  const [calendar,prefs]=await Promise.all([api('/calendar/status'),api('/proactive/settings')]);
  const callback=new URLSearchParams(globalThis.location?.search||'').get('calendar');
  const message=callback==='connected'?'Autorisation reçue. Actualisez maintenant votre agenda.':callback==='failed'?'Connexion non terminée. Recommencez depuis votre profil.':'';
  return `<section class="card spaced"><h2>Mon agenda connecté</h2>${message?`<p role="status">${message}</p>`:''}<p>${calendar.connected?`${esc(calendar.provider)} connecté · dernière lecture ${esc(date(calendar.last_sync))}`:'Aucun compte connecté.'}</p>${calendar.error?'<p class="error" role="alert">La dernière lecture a échoué. Actualisez ou reconnectez le compte. Aucun créneau libre ne sera supposé.</p>':''}<div class="row">${[['google','Google Calendar'],['outlook','Outlook / Microsoft']].map(([id,label])=>`<button data-action="calendar-connect" data-provider="${id}" ${calendar.providers[id]?'':'disabled'}>${label}</button>`).join('')}${calendar.connected?'<button data-action="calendar-sync">Actualiser mon agenda</button><button data-action="calendar-disconnect">Déconnecter</button>':''}</div>${Object.values(calendar.providers).some(x=>!x)?'<p class="muted">Un bouton désactivé signifie que le serveur attend la configuration OAuth du fournisseur.</p>':''}<p class="muted">${esc(calendar.window_policy)} Les titres de vos rendez-vous ne sont pas conservés. Vos créneaux saisis ci-dessous limitent les heures proposées.</p><p class="muted">Apple : export .ics disponible dans les programmes. La connexion iCloud CalDAV reste à implémenter.</p></section>
  <section class="card spaced"><h2>Recevoir une idée de sortie</h2><p>Les deux personnes doivent accepter. Après sept jours sans sortie confirmée passée, Chandelle cherche deux heures en commun et propose un programme dans ce fil. La proposition utilise la même recherche web que vos demandes de sorties, dans la limite du quota disponible.</p><button data-action="proactive-consent" data-enabled="${!prefs.enabled}" aria-pressed="${prefs.enabled}">${prefs.enabled?'Désactiver mes propositions':'Activer mes propositions'}</button><p>${prefs.both_enabled?'Accord reçu des deux personnes.':'Accord des deux personnes encore incomplet.'}</p><p class="muted">Vos envies récentes autorisées pour les recommandations aident à choisir le programme. Les notes privées restent exclues.</p><p>Vérification automatique : ${prefs.scheduler.running?esc(prefs.scheduler.cadence):'non activée sur ce serveur'}.</p><p class="muted">Dernier passage : ${esc(date(prefs.scheduler.last_run))}${prefs.scheduler.outcome?.reason?' · '+esc(prefs.scheduler.outcome.reason):''}</p><div class="row"><button data-action="proactive-trigger" data-demo="false">Vérifier maintenant</button>${prefs.demo_available?'<button data-action="proactive-trigger" data-demo="true">Test : ignorer les sept jours</button>':''}</div><p id="proactive-result" aria-live="polite"></p></section>`;
}

export async function calendarPlanPanel(api,p){
  if(!['accepted','cancelled'].includes(p.status))return '';
  const s=await api('/calendar/plans/'+encodeURIComponent(p.id));
  return `<section class="card spaced"><h3>${s.operation==='delete'?'Retirer la sortie des agendas':'Ajouter cette sortie aux agendas'}</h3><p>${esc(s.event.title)} · ${esc(date(s.event.start))} à ${esc(date(s.event.end))}</p><p>${s.connected_calendars} agenda(s) connecté(s). ${s.approvals}/2 confirmations pour cette version du programme.</p>${s.demo?'<p class="muted">Programme fictif. L’écriture exige le mode démo autorisé sur le serveur et un calendrier de test.</p>':''}${s.own_event?`<p>Mon agenda : ${esc(s.own_event.status)}${s.own_event.error?' · échec, vous pouvez réessayer.':''}</p>`:''}<button data-action="calendar-confirm" data-id="${esc(p.id)}" data-revision="${esc(s.revision)}" ${s.connected_calendars?'':'disabled'}>${s.approved_by_me?'Actualiser / réessayer la synchronisation':'Je confirme cette modification de calendrier'}</button><p class="muted">La modification est exécutée après l’accord des deux personnes. Aucun invité ni réservation n’est créé.</p></section>`;
}

export async function notificationsPanel(api){
  const feed=await api('/notifications');
  if(!feed.items.length)return '';
  return `<section class="card spaced" aria-label="Notifications"><h2>Une proposition vous attend</h2>${feed.items.map(n=>`<article><h3>${esc(n.title)}</h3><p>${esc(n.message)}</p><button data-action="notification-open" data-id="${esc(n.id)}" data-plan="${esc(n.plan_id)}">${n.read?'Revoir le programme':'Voir le programme'}</button></article>`).join('')}</section>`;
}

export async function clickCalendar(button,ctx){
  const action=button.dataset.action;
  if(!action?.startsWith('calendar-')&&!action?.startsWith('proactive-')&&action!=='notification-open')return false;
  if(action==='calendar-export')return false;
  const identity=ctx.identity();
  if(action==='calendar-connect'){
    const result=await ctx.api('/calendar/connect/'+button.dataset.provider+'?format=json');
    const url=new URL(result.authorization_url);
    if(!['accounts.google.com','login.microsoftonline.com'].includes(url.hostname)||url.protocol!=='https:')throw Error('Adresse de connexion inattendue.');
    if(ctx.identity()===identity)location.assign(url.href);
  }else if(action==='calendar-sync'){
    ctx.notify('Lecture de votre agenda en cours…');await ctx.api('/calendar/sync',{method:'POST',body:{}});
    if(ctx.identity()===identity)await ctx.navigate('availability');
  }else if(action==='calendar-disconnect'){
    if(!confirm('Déconnecter cet agenda ? Les événements déjà créés resteront dans le calendrier.'))return true;
    await ctx.api('/calendar/connection',{method:'DELETE'});if(ctx.identity()===identity)await ctx.navigate('availability');
  }else if(action==='calendar-confirm'){
    await ctx.api('/calendar/plans/'+button.dataset.id+'/confirm',{method:'POST',body:{revision:button.dataset.revision}});
    if(ctx.identity()===identity)await ctx.showPlan(button.dataset.id);
  }else if(action==='proactive-consent'){
    await ctx.api('/proactive/settings',{method:'PUT',body:{enabled:button.dataset.enabled==='true'}});
    if(ctx.identity()===identity)await ctx.navigate('availability');
  }else if(action==='proactive-trigger'){
    ctx.notify('Recherche de créneaux et calcul de la proposition…');
    const result=await ctx.api('/proactive/trigger/'+ctx.cid(),{method:'POST',body:{demo:button.dataset.demo==='true'}});
    if(ctx.identity()!==identity)return true;
    if(result.triggered){ctx.notify('Proposition créée dans votre fil.');await ctx.navigate('home');}
    else {const output=document.querySelector('#proactive-result');if(output)output.textContent=result.reason;ctx.notify(result.reason);}
  }else{
    await ctx.api('/notifications/'+button.dataset.id+'/read',{method:'POST',body:{}});
    if(ctx.identity()===identity)await ctx.showPlan(button.dataset.plan);
  }
  return true;
}
