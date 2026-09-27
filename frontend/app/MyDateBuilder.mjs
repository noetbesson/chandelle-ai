import { esc, euros, clock, illustration } from './ActivityCard.mjs';
export function travelMinutes(a, b) {
    if (!a.location || !b.location)
        return null;
    const r = Math.PI / 180, lat1 = a.location.lat * r, lat2 = b.location.lat * r;
    const h = Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((b.location.lng - a.location.lng) * r / 2) ** 2;
    return Math.ceil(Math.max(5, 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(h))) / 4.5 * 60 + 5));
}
export const chronological = (values) => [...values].sort((a, b) => Date.parse(a.start ?? '9999-01-01') - Date.parse(b.start ?? '9999-01-01') || a.id.localeCompare(b.id));
export function selectionWarnings(values, limits) {
    const all = chronological(values), warnings = [];
    for (let i = 1; i < all.length; i++) {
        const a = all[i - 1], b = all[i], gap = (Date.parse(b.start ?? '') - Date.parse(a.end ?? '')) / 60000, travel = travelMinutes(a, b);
        if (travel == null)
            continue;
        if (gap < 0)
            warnings.push(`${a.name} et ${b.name} se chevauchent. Choisissez un autre horaire ou une seule activité.`);
        else if (gap < travel)
            warnings.push(`${a.name} → ${b.name} : prévoyez environ ${travel} min à pied, contre ${Math.max(0, Math.floor(gap))} min disponibles.`);
        else if (travel > (limits.max_travel_time_minutes ?? 30))
            warnings.push(`${a.name} → ${b.name} : environ ${travel} min à pied, au-delà de votre limite de trajet.`);
    }
    if (limits.budget_cap != null && all.reduce((n, a) => n + 2 * (a.price_per_person ?? 0), 0) > limits.budget_cap)
        warnings.push(`La sélection dépasse votre budget de ${euros(limits.budget_cap)} à deux.`);
    if (all.length && (Date.parse(all.at(-1).end ?? '') - Date.parse(all[0].start ?? '')) / 60000 > (limits.max_total_duration_minutes ?? 360))
        warnings.push('La sélection dépasse la durée prévue pour votre sortie.');
    if (all.some(a => a.composable === false))
        warnings.push('Informations manquantes pour composer certains lieux gardés : consultez leurs sources.');
    return warnings;
}
export function MyDateBuilder(values, data, expanded, pending, composed) {
    const all = chronological(values), warnings = selectionWarnings(all, data), total = all.reduce((n, a) => n + 2 * (a.price_per_person ?? 0), 0);
    const balanced = all.some(a => a.category === 'food') && all.some(a => a.category !== 'food');
    return `<aside class="my-date-builder ${expanded ? 'is-expanded' : ''}" aria-label="Mon date"><button type="button" class="builder-toggle" data-activity-action="builder" aria-expanded="${expanded}" aria-controls="kept-activities"><span>Mon date <strong>${all.length} gardée${all.length > 1 ? 's' : ''}</strong></span><span>${all.some(a => a.price_per_person == null) ? 'Total inconnu' : euros(total) + ' à deux'}</span></button><div class="builder-content" id="kept-activities"><p class="builder-guidance">${!all.length ? 'Une table, une balade… gardez ce qui vous plaît.' : warnings.length ? 'Quelques horaires ou trajets à ajuster.' : balanced ? 'Un restaurant et une activité : votre sortie prend forme.' : `${all.length} activité${all.length > 1 ? 's' : ''} retenue${all.length > 1 ? 's' : ''}. Ajoutez-en ou composez dès maintenant.`}</p><ol class="kept-list">${all.map((a, i) => `<li>${i ? `<p class="builder-travel">${travelMinutes(all[i - 1], a) == null ? 'Trajet inconnu' : travelMinutes(all[i - 1], a) + ' min à pied estimées, marge incluse'}</p>` : ''}<div class="kept-row">${illustration(a.category, true)}<div><span>${clock(a.start)} · ${a.price_per_person == null ? 'Prix inconnu' : euros(a.price_per_person * 2) + ' à deux'}</span><p>${esc(a.name)}</p></div><button type="button" data-activity-action="remove" data-id="${esc(a.id)}" aria-label="Retirer ${esc(a.name)}">×</button></div></li>`).join('')}</ol><div class="builder-warnings">${warnings.map(w => `<p>${esc(w)}</p>`).join('')}</div><small>Horaires de Paris. Estimations à pied, sans itinéraire vérifié. Garder une carte ne modifie pas vos goûts.</small></div><div class="builder-footer">${warnings.length ? `<p class="builder-warning-count" role="status">${warnings.length} point${warnings.length > 1 ? 's' : ''} à ajuster</p>` : ''}<button type="button" class="primary" data-activity-action="compose" ${!all.length || pending ? 'disabled' : ''}>${pending ? 'Vérification du programme…' : composed ? 'Revoir mon date' : 'Construire mon date'}</button></div></aside>`;
}
