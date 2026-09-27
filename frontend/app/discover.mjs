// Presentation only: preserve the API records, order within groups and existing actions.
import {Calendar22, LocationPin, Euro} from './icons.mjs';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const categoryLabels={food:'À table',culture:'Culture',concerts:'Concerts',cinema:'Cinéma',outdoors:'Au grand air',sport:'Sport',workshops:'Ateliers',nightlife:'La nuit',home:'À la maison',travel:'Escapades'};
const typeLabels={concert:'Concerts','expo/performance':'Expositions & performances',exposition:'Expositions',parade:'Parades',restaurant:'Restaurants',bar:'Bars',atelier:'Ateliers','escape game':'Escape games'};
const number=new Intl.NumberFormat('fr-FR',{maximumFractionDigits:2});
const safeURL=value=>{try{const url=new URL(value);return ['https:','http:'].includes(url.protocol)?url.href:'';}catch{return '';}};
function dateLabel(value){
  if(!value)return '';
  const date=new Date(value);if(!Number.isFinite(date.getTime()))return '';
  // A date-only value is not a known midnight performance time.
  return new Intl.DateTimeFormat('fr-FR',{timeZone:'Europe/Paris',day:'numeric',month:'short',year:'numeric',...(/T\d{2}:\d{2}/.test(value)?{hour:'2-digit',minute:'2-digit'}:{})}).format(date);
}
const meta=(icon,text,kind)=>text?`<li class="activity-meta-${kind}">${icon}<span>${esc(text)}</span></li>`:'';
export function activityMeta(a){
  const start=dateLabel(a.start),end=dateLabel(a.end);
  const when=start?`${start}${end?' → '+end:''}`:end?'Jusqu’au '+end:'';
  const location=typeof a.location==='string'?a.location:a.location?.address;
  const place=location||a.neighborhood||'';
  const price=typeof a.price_per_person==='number'&&Number.isFinite(a.price_per_person)&&a.price_per_person>=0
    ?a.price_per_person===0?'Gratuit':`${number.format(a.price_per_person)} € / pers.`:'Prix à confirmer';
  return `<ul class="activity-meta">${meta(Calendar22,when,'date')}${meta(LocationPin,place,'place')}${meta(Euro,price,'price')}</ul>`;
}
function activityArt(a,label){
  const url=safeURL(a.image_url);
  return `<div class="discover-art" aria-hidden="true"><div class="art-fallback"><span class="art-orbit"></span><span class="art-letter font-display">${esc(label.charAt(0))}</span><span class="art-caption">${esc(label)}</span></div>${url?`<img src="${esc(url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" data-activity-image>`:''}</div>`;
}
export function discoverActivityRow(a,{demo=false,label='',selectButton=()=>'',scores=()=>''}={}){
  const title=demo?a.title:a.name,source=safeURL(a.website);
  const action=demo?`<button class="activity-action" data-action="activity" data-id="${esc(a.id)}">Découvrir <span aria-hidden="true">↗</span></button>${selectButton(a)}`:source?`<a class="activity-action" href="${esc(source)}" target="_blank" rel="noopener noreferrer">Voir la source <span aria-hidden="true">↗</span></a>`:'';
  return `<article class="discover-row" data-discover-row>
    ${activityArt(a,label)}<div class="discover-copy">
      <p class="activity-kicker">${demo?'Exemple fictif':esc(a.type||'Activité réelle')}</p>
      <h3 class="font-body" title="${esc(title)}">${esc(title)}</h3>
      ${a.description?`<p class="activity-description">${esc(a.description)}</p>`:''}
      ${activityMeta(a)}
      ${!demo&&a.why?`<p class="activity-reason">${esc(a.why)}</p>`:''}
      ${!demo&&typeof a.match_score==='number'?`<small>Affinité : ${esc(a.match_score)}</small>`:''}
      ${demo&&a.duration_minutes!=null?`<small>${esc(a.duration_minutes)} min${a.neighborhood?' · '+esc(a.neighborhood):''}</small>`:''}
      ${demo?`<details class="activity-fit"><summary>Votre affinité</summary>${a.eligible?scores(a):'<p class="muted">Hors de vos contraintes communes actuelles.</p>'}</details>`:''}
      ${demo&&a.state&&a.state!=='neutral'?`<small class="activity-state">${esc(a.state)} · votre choix</small>`:''}
      <div class="activity-actions">${action}</div>
    </div>
  </article>`;
}
export function discoverSections(records,options={}){
  const groups=new Map();
  for(const a of records){const key=String((options.demo?a.category:a.type)||'Autres idées');if(!groups.has(key))groups.set(key,[]);groups.get(key).push(a);}
  return [...groups].map(([key,rows],i)=>{
    const label=(options.demo?categoryLabels[key]:typeLabels[key.toLowerCase()])||key;
    return `<section class="discover-section" aria-labelledby="${options.demo?'demo':'real'}-category-${i}"><div class="category-heading" data-reveal><h2 class="font-display" id="${options.demo?'demo':'real'}-category-${i}">${esc(label)}</h2><span>${rows.length} ${rows.length===1?'idée':'idées'}</span></div><div class="discover-list">${rows.map(a=>discoverActivityRow(a,{...options,label})).join('')}</div></section>`;
  }).join('');
}
export function discoverPage({catalog,real,query,category,filterCategories,selectButton,compareBar,scores}){
  return `<div class="discover-page"><header class="discover-heading"><p class="eyebrow">DISCOVER · LE GOÛT DE SORTIR</p><h1 class="font-display">Des idées de sorties<br>en Île-de-France</h1><p>Une scène, une adresse, un détour.<br>Et du temps pour vous deux.</p></header>
    <form id="discover" class="discover-filters"><div class="discover-search"><label class="sr-only" for="search">Rechercher une activité</label><input id="search" name="query" placeholder="Une envie, un lieu…" value="${esc(query)}"><button class="primary" aria-label="Rechercher">Rechercher</button></div><label class="sr-only" for="category">Catégorie</label><select id="category" name="category"><option value="">Toutes les catégories</option>${filterCategories.map(c=>`<option value="${esc(c)}" ${c===category?'selected':''}>${esc(categoryLabels[c]||c)}</option>`).join('')}</select></form>
    <div class="discover-caption"><span>${real.length} ${real.length===1?'idée à explorer':'idées à explorer'}</span><span>Les sorties du moment</span></div>
    <div class="discover-feed">${discoverSections(real)||'<div class="empty"><h2>Aucune idée ici, pour le moment.</h2><p>Essayez une autre envie ou une autre catégorie.</p></div>'}</div>
    <p class="discover-source-note">Ces pistes proviennent de sources publiques. Horaires, tarifs et disponibilité sont à confirmer auprès du lieu.</p>
    <details class="discover-demo"><summary>Explorer les exemples de démonstration <span>${catalog.length}</span></summary><p class="muted">Ce catalogue fictif permet de tester la comparaison et la composition de programmes.</p>${compareBar()}${discoverSections(catalog,{demo:true,selectButton,scores})||'<p class="empty">Aucun exemple pour cette recherche.</p>'}</details>
  </div>`;
}
