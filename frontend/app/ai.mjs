// Ask and Memory views call these forms. No parallel screen or store.
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const reasons={not_configured_or_disabled:'La recherche web est momentanément indisponible.',budget_limit_reached:'La limite de recherches est atteinte. Réessayez plus tard.',model_not_budgeted:'La recherche est indisponible pour le moment.',provider_timeout:'Le service n’a pas répondu à temps. Réessayez plus tard.',authentication_failed:'Le service de recherche doit être rétabli.',provider_rate_limited:'Le service limite les appels. Réessayez plus tard.'};
export function aiDiscoverForm(){return `<section class="card spaced"><h2>Rechercher une sortie sur le web</h2><button type="button" data-action="ai-budget">Voir le quota restant</button><p>Décrivez le lieu, la date et votre budget. La recherche se limite à l’Île-de-France. Les résultats sont des pistes sourcées, sans garantie de place disponible.</p><form id="web-discover"><label for="web-query">Votre recherche</label><textarea id="web-query" name="text" required minlength="3" maxlength="800" placeholder="Une exposition dimanche à Paris, moins de 20 € par personne"></textarea><label><input type="checkbox" name="cloud_consent" required> J’autorise l’envoi de cette demande à OpenAI pour une recherche web.</label><label><input type="checkbox" name="use_shared_interests"> Inclure les thèmes d’activités partagés dans notre profil de couple.</label><button class="primary">Chercher des sorties réelles</button><p class="muted">Une recherche par demande, cache de 6 h. Réserve locale maximale : 0,10 $ par tentative, distincte du coût facturé.</p></form><div id="web-results" aria-live="polite"></div></section>`}
export function renderWebResult(result){
  if(result.status!=='completed')return `<p role="alert">${esc(reasons[result.reason]||'La recherche n’a pas pu être validée. Aucun résultat inventé n’est ajouté.')}</p>`;
  const text=(result.segments||[{text:result.answer||result.message||''}]).map(s=>s.url&&s.url.startsWith('https://')?`<a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.text||'Source')}</a>`:esc(s.text)).join('');
  return `<p>${result.cached?'Résultat déjà enregistré, aucun nouvel appel.':'Recherche terminée.'} ${esc(result.searched_at)}</p><div style="white-space:pre-wrap">${text}</div><p>${esc(result.verification)}</p><h3>Sources consultées</h3><ul>${(result.sources||[]).map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a></li>`).join('')}</ul><p>Ces pistes ne sont pas encore des activités dont les horaires et disponibilités permettent de composer un programme.</p>`;
}
export function aiMemoryForm(){return `<section class="card spaced"><h2>Ce que vous aimeriez faire</h2><p>Parlez de vos goûts ou de ce que vous préférez éviter. Les informations retenues apparaîtront dans votre mémoire, où vous pourrez les corriger.</p><form id="conversation-memory"><label for="conversation-text">Votre message</label><textarea id="conversation-text" name="text" required maxlength="4000" placeholder="J’aime le jazz. En ce moment, j’ai envie de nature."></textarea><label for="conversation-privacy">Utilisation des informations retenues</label><select name="privacy_scope" id="conversation-privacy"><option value="PRIVATE">Privé, sans influence sur nos recommandations communes</option><option value="COUPLE_RECOMMENDATION">Adapter nos recommandations sans montrer mes notes au partenaire</option><option value="SHARED">Partager au couple</option></select><button class="primary">Enregistrer dans ma mémoire</button></form><div id="conversation-result" aria-live="polite"></div></section>`}
export async function submitAI(form,{api,navigate,notify,identity}){
  if(form.id==='web-discover'){
    const owner=identity(),fd=new FormData(form),target=form.parentElement.querySelector('[aria-live]');
    target.textContent='Recherche en cours…';
    const result=await api('/discovery/web',{method:'POST',body:{text:fd.get('text'),cloud_consent:fd.has('cloud_consent'),use_shared_interests:fd.has('use_shared_interests')}});
    if(owner===identity()&&target.isConnected)target.innerHTML=renderWebResult(result);
    return true;
  }
  if(form.id!=='conversation-memory')return false;
  const owner=identity(),fd=new FormData(form),target=form.parentElement.querySelector('[aria-live]');
  target.textContent='Analyse du message en cours…';
    const result=await api('/conversations',{method:'POST',body:{text:fd.get('text'),privacy_scope:fd.get('privacy_scope'),mode:'auto'}});
    if(owner!==identity())return true;
    await navigate('memories');
    notify(result.reply);
  return true;
}
