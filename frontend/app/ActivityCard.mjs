export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] ?? c));
export const labels = { food: 'Restaurants', culture: 'Sorties culturelles', concerts: 'Concerts', cinema: 'Cinéma', outdoors: 'Balades', sport: 'Sport', workshops: 'Ateliers', nightlife: 'Bars', home: 'À la maison', travel: 'Escapades' };
export const euros = (v) => new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 }).format(v);
export const clock = (v) => v == null ? 'Horaire inconnu' : new Date(v).toLocaleTimeString('fr-FR', { timeZone: 'Europe/Paris', hour: '2-digit', minute: '2-digit' });
const motifs = {
    food: '<ellipse cx="160" cy="119" rx="57" ry="35"/><ellipse cx="160" cy="119" rx="42" ry="24"/><path d="M78 83v72m-9-72v25q9 12 18 0V83m155 0q-16 23-9 40h9v32V83M135 61q-9-12 0-24m28 24q-9-12 0-24"/>',
    culture: '<path d="M73 170V60h174v110M93 170V79h134v91M120 170v-48a40 40 0 0 1 80 0v48M64 170h192M122 55l38-30 38 30"/>',
    outdoors: '<path d="M67 167q57-52 75-19t107-2M160 155V74m0 44-34-24m34 11 30-26M161 104c-56 0-59-53-25-69 41 3 70 28 25 69Z"/><circle cx="230" cy="52" r="19"/>',
    concerts: '<path d="M133 134V52l70-15v81M133 76l70-15"/><ellipse cx="113" cy="138" rx="20" ry="14"/><ellipse cx="183" cy="122" rx="20" ry="14"/><path d="M76 164q84 27 169-9"/>',
    cinema: '<rect x="79" y="54" width="162" height="113" rx="8"/><path d="M79 79h162M96 54l20 25m15-25 20 25m15-25 20 25m15-25 20 25M145 102l31 20-31 20Z"/>',
    workshops: '<path d="M111 74h98l-9 52q-5 35-40 35t-40-35ZM130 54q-10-16 0-30m30 30q-10-16 0-30m30 30q-10-16 0-30M94 174h132"/>',
};
export function illustration(category, mini = false) {
    return `<svg class="${mini ? 'activity-mini-art' : 'activity-art'}" viewBox="0 0 320 210" aria-hidden="true" focusable="false"><g fill="none" stroke="currentColor" stroke-width="${mini ? 5 : 2.3}" stroke-linecap="round" stroke-linejoin="round">${motifs[category] ?? motifs.culture}</g></svg>`;
}
export function safeImage(url) { try {
    const u = new URL(url ?? '');
    return u.protocol === 'https:' && !u.username && !u.password ? u.href : null;
}
catch {
    return null;
} }
export function ActivityCard(a, kept = false, compact = false) {
    const photo = safeImage(a.image_url);
    const mood = a.tags.slice(0, 2).map(t => ({ quiet: 'Calme', calm: 'Calme', romantic: 'Romantique', japanese: 'Cuisine japonaise', italian: 'Cuisine italienne', nature: 'Nature', creative: 'Créatif', music: 'Musique', intimate: 'Intimiste' }[t] ?? t)).join(' · ');
    return `<article class="activity-choice ${compact ? 'is-compact' : ''}" data-activity-id="${esc(a.id)}" tabindex="${compact ? '-1' : '0'}" aria-label="${esc(a.name)}"><div class="activity-picture">${photo ? `<img src="${esc(photo)}" alt="${esc(a.name)}" decoding="async" referrerpolicy="no-referrer">` : illustration(a.category)}<span class="activity-origin">${a.demo ? 'Exemple fictif' : photo ? 'Photo du lieu' : 'Illustration'}</span><span class="swipe-feedback swipe-keep" aria-hidden="true">Garder</span><span class="swipe-feedback swipe-pass" aria-hidden="true">Passer</span></div><div class="activity-copy"><p class="activity-category">${illustration(a.category, true)}${esc(labels[a.category] ?? a.category)}</p><h3>${esc(a.name)}</h3><p class="activity-practical"><time datetime="${esc(a.start)}">${clock(a.start)}</time>${a.end ? ' à ' + clock(a.end) : ''} <span>${a.price_per_person == null ? 'Prix inconnu' : euros(a.price_per_person) + ' / pers.'}</span></p><p class="activity-place">${esc(a.demo ? 'Paris, localisation illustrative' : a.address || 'Adresse à confirmer')}</p><p class="activity-mood">${a.rating == null ? esc(mood || 'Ambiance à découvrir') : `${esc(a.rating)} / 5 · ${esc(mood)}`}</p><p class="activity-why">${esc(a.why)}</p><small>${a.schedule_status === 'proposed' ? 'Heures de visite suggérées, à confirmer.' : a.schedule_status === 'published' && (a.start || a.end) ? 'Dates publiées par la source.' : 'Horaires à confirmer.'} Disponibilité non vérifiée.</small>${safeImage(a.source_url) ? `<p><a href="${esc(a.source_url)}" target="_blank" rel="noopener noreferrer">Consulter la source</a>${a.checked_at ? ` · consultée le ${esc(new Date(a.checked_at).toLocaleDateString('fr-FR'))}` : ''}</p>` : ''}<div class="activity-actions"><button type="button" data-activity-action="pass" data-id="${esc(a.id)}" ${kept ? 'disabled' : ''}><span aria-hidden="true">×</span> Passer</button><button type="button" class="primary" data-activity-action="${kept ? 'remove' : 'keep'}" data-id="${esc(a.id)}" aria-pressed="${kept}"><span aria-hidden="true">♡</span> ${kept ? 'Gardée, retirer' : 'Garder'}</button></div></div></article>`;
}
