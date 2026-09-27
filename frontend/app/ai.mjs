// Ask and Memory views call these forms. No parallel screen or store.
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const reasons={not_configured_or_disabled:'La recherche web est momentanément indisponible.',budget_limit_reached:'La limite de recherches est atteinte. Réessayez plus tard.',model_not_budgeted:'La recherche est indisponible pour le moment.',provider_timeout:'Le service n’a pas répondu à temps. Réessayez plus tard.',authentication_failed:'Le service de recherche doit être rétabli.',provider_rate_limited:'Le service limite les appels. Réessayez plus tard.'};
export function aiMemoryForm(){return `<section class="card spaced"><h2>Ce que vous aimeriez faire</h2><p>Parlez de vos goûts ou de ce que vous préférez éviter. Les informations retenues apparaîtront dans votre mémoire, où vous pourrez les corriger.</p><form id="conversation-memory"><label for="conversation-text">Votre message</label><textarea id="conversation-text" name="text" required maxlength="4000" placeholder="J’aime le jazz. En ce moment, j’ai envie de nature."></textarea><label for="conversation-privacy">Utilisation des informations retenues</label><select name="privacy_scope" id="conversation-privacy"><option value="PRIVATE">Privé, sans influence sur nos recommandations communes</option><option value="COUPLE_RECOMMENDATION">Adapter nos recommandations sans montrer mes notes au partenaire</option><option value="SHARED">Partager au couple</option></select><button class="primary">Enregistrer dans ma mémoire</button></form><div id="conversation-result" aria-live="polite"></div></section>`}
export async function submitAI(form,{api,navigate,notify,identity}){
  if(form.id!=='conversation-memory')return false;
  const owner=identity(),fd=new FormData(form),target=form.parentElement.querySelector('[aria-live]');
  target.textContent='Analyse du message en cours…';
    const result=await api('/conversations',{method:'POST',body:{text:fd.get('text'),privacy_scope:fd.get('privacy_scope'),mode:'auto'}});
    if(owner!==identity())return true;
    await navigate('memories');
    notify(result.reply);
  return true;
}
