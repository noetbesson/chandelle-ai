const escape = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] ?? c));
const labels = { food: 'Restaurant', culture: 'Culture', concerts: 'Concert', cinema: 'Cinéma', outdoors: 'Balade', sport: 'Sport', workshops: 'Atelier', nightlife: 'Bar', home: 'À la maison', travel: 'Escapade' };
const euros = (v) => new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 }).format(v);
const duration = (n) => `${Math.floor(n / 60)} h ${n % 60 ? String(n % 60).padStart(2, '0') : ''}`.trim();
export function readPlan(value) {
    if (!value || typeof value !== 'object')
        throw Error('Programme invalide reçu du serveur.');
    const p = value;
    if (typeof p.id !== 'string' || !Array.isArray(p.activities) || !p.activities.length || p.activities.length > 50 ||
        typeof p.estimated_total_eur !== 'number' || !Number.isFinite(p.estimated_total_eur) || !Array.isArray(p.timeline) ||
        !p.activities.every(a => typeof a.id === 'string' && typeof a.name === 'string' && Number.isFinite(a.price_per_person)))
        throw Error('Programme incomplet reçu du serveur.');
    return p;
}
export function readSearch(value) {
    if (!value || typeof value !== 'object')
        throw Error('Recherche invalide.');
    const r = value;
    if (typeof r.search_id !== 'string' || !Array.isArray(r.proposals) || r.proposals.length > 3 || !Array.isArray(r.warnings))
        throw Error('Recherche incomplète.');
    r.proposals.forEach(readPlan);
    return r;
}
/** Pure state is separately testable without a DOM or backend. Nothing is persisted in localStorage. */
export class DeckState {
    plans = Object.create(null);
    order;
    selected = new Map();
    interested = new Set();
    index = 0;
    compare = false;
    constructor(proposals) {
        if (proposals.length > 3 || new Set(proposals.map(p => p.id)).size !== proposals.length)
            throw Error('Un deck contient au plus trois programmes distincts.');
        this.order = proposals.map(p => p.id);
        proposals.forEach(p => this.plans[p.id] = structuredClone(readPlan(p)));
    }
    get current() { const id = this.order[this.index]; return id ? this.plans[id] : undefined; }
    move(delta) { if (this.order.length)
        this.index = (this.index + delta + this.order.length) % this.order.length; }
    swipe(direction) { if (direction === 'right' && this.current)
        this.interested.add(this.current.id); this.move(1); }
    update(plan) {
        if (!this.plans[plan.id])
            throw Error('Programme extérieur au deck.');
        const old = this.plans[plan.id];
        this.plans[plan.id] = structuredClone(readPlan(plan));
        for (const a of old?.activities ?? []) {
            if (this.selected.has(a.id) && !plan.activities.some(n => n.id === a.id))
                this.selected.delete(a.id);
        }
    }
    toggle(a) {
        if (this.selected.has(a.id)) {
            this.selected.delete(a.id);
            return;
        }
        if (this.selected.size >= 3)
            throw Error('Choisissez au maximum trois activités.');
        this.selected.set(a.id, structuredClone(a));
    }
}
export function deckSkeleton() {
    return '<section class="date-deck deck-loading" aria-busy="true" aria-label="Composition en cours"><h2>Préparons vos propositions</h2><p role="status">Analyse des envies, consultation des préférences et recherche des activités en cours. Les résultats arrivent après vérification des horaires et des trajets.</p><div class="deck-skeleton" aria-hidden="true"><span></span><span></span><span></span><span></span></div></section>';
}
export class DateProposalDeck {
    host;
    data;
    options;
    state;
    identity;
    abort = new AbortController();
    disposed = false;
    pending = false;
    message = '';
    error = '';
    pointer = null;
    dialog = null;
    constructor(host, data, options) {
        this.host = host;
        this.data = data;
        this.options = options;
        this.state = new DeckState(data.proposals);
        this.identity = options.identity();
        this.render();
        host.addEventListener('click', e => { void this.click(e); }, { signal: this.abort.signal });
        host.addEventListener('keydown', e => this.key(e), { signal: this.abort.signal });
        host.addEventListener('pointerdown', e => {
            if (this.state.compare || this.pending || e.target.closest('button,input,dialog,a,summary'))
                return;
            this.pointer = { x: e.clientX, y: e.clientY };
        }, { signal: this.abort.signal });
        host.addEventListener('pointercancel', () => this.pointer = null, { signal: this.abort.signal });
        host.addEventListener('pointerup', e => {
            if (!this.pointer)
                return;
            const dx = e.clientX - this.pointer.x, dy = e.clientY - this.pointer.y;
            this.pointer = null;
            if (Math.abs(dx) > 65 && Math.abs(dx) > Math.abs(dy) * 1.3) {
                this.state.swipe(dx > 0 ? 'right' : 'left');
                this.message = dx > 0 ? 'Intérêt retenu. Aucune confirmation envoyée.' : '';
                this.render();
            }
        }, { signal: this.abort.signal });
    }
    destroy() { this.disposed = true; this.abort.abort(); this.dialog?.close(); this.dialog?.remove(); this.state.selected.clear(); }
    receivePlan(value) {
        if (!this.current() || !value || typeof value !== 'object')
            return;
        const id = value.id;
        if (typeof id === 'string' && this.state.plans[id]) {
            this.state.update(readPlan(value));
            this.render();
        }
    }
    current() { return !this.disposed && this.identity === this.options.identity() && this.host.isConnected; }
    button(action, text, attributes = '') { return `<button type="button" data-deck-action="${action}" ${attributes} ${this.pending ? 'disabled' : ''}>${text}</button>`; }
    card(p, index) {
        const travels = p.timeline.filter(t => t.type === 'travel');
        return `<article class="date-proposal" data-plan="${escape(p.id)}" aria-label="Proposition ${index + 1}">
      <header><span class="eyebrow">PROPOSITION ${index + 1} / ${this.state.order.length}</span><h3>${escape(p.diversity_label)}</h3><p class="deck-total">${euros(p.estimated_total_eur)} à deux <span>· ${duration(p.duration_minutes)}</span></p></header>
      ${p.activities.some(a => a.demo) ? '<p class="deck-source">Exemples fictifs. Horaires et prix de démonstration.</p>' : ''}
      <ol class="deck-timeline">${p.activities.map((a, i) => `${i ? `<li class="deck-travel">${escape(travels[i - 1]?.minutes ?? '?')} min à pied estimées, marge incluse</li>` : ''}
        <li data-activity="${escape(a.id)}"><div class="deck-step"><time>${escape(a.start)}</time><div><h4>${escape(a.name)}</h4><p>${escape(labels[a.type] ?? a.type)} · ${euros(a.price_per_person)} / personne</p><small>Jusqu’à ${escape(a.end)}</small></div></div>
        <div class="deck-step-actions">${this.button('replace', 'Remplacer', `data-plan="${escape(p.id)}" data-activity="${escape(a.id)}" ${p.kept_ids.includes(a.id) || !['draft', 'proposed'].includes(p.status) ? 'disabled' : ''}`)}
        <details><summary>Détails</summary><p>${escape(a.description)}</p><p>${escape(a.address)}</p><small>${escape(a.source)}</small></details></div>
        ${this.state.compare ? this.button('select', this.state.selected.has(a.id) ? 'Retirer de mon date' : 'Garder dans mon date', `aria-pressed="${this.state.selected.has(a.id)}" data-plan="${escape(p.id)}" data-activity="${escape(a.id)}"`) : ''}</li>`).join('')}</ol>
      <p class="deck-reason">${escape(p.reason)}</p><footer>${this.button('choose', 'Choisir ce date', `class="primary" data-plan="${escape(p.id)}"`)}${this.button('open', 'Ouvrir le programme', `data-plan="${escape(p.id)}"`)}</footer></article>`;
    }
    render() {
        if (this.disposed)
            return;
        this.host.innerHTML = `<section class="date-deck" tabindex="0" role="region" aria-label="Propositions de dates" aria-roledescription="carrousel">
      <div class="deck-toolbar"><h2>${this.state.order.length} propositions pour vous</h2>${this.state.order.length ? this.button('compare', this.state.compare ? 'Revenir aux cartes' : 'Comparer et composer', `aria-pressed="${this.state.compare}"`) : ''}</div>
      ${this.data.warnings.map(w => `<p class="deck-warning" role="status">${escape(w)}</p>`).join('')}
      <p class="sr-only" aria-live="polite" data-deck-status>Proposition ${this.state.order.length ? this.state.index + 1 : 0} sur ${this.state.order.length}. ${escape(this.message)}</p>
      ${this.message ? `<p role="status">${escape(this.message)}</p>` : ''}${this.error ? `<p class="error" role="alert">${escape(this.error)}</p>` : ''}
      <div class="deck-cards ${this.state.compare ? 'deck-compare' : ''}">${this.state.order.map((id, i) => `<div class="deck-slide" ${!this.state.compare && i !== this.state.index ? 'hidden' : ''}>${this.card(this.state.plans[id], i)}</div>`).join('')}</div>
      ${!this.state.compare && this.state.order.length ? `<nav class="deck-controls" aria-label="Parcourir les propositions">${this.button('previous', 'Précédente')}
      <span>${this.state.index + 1} / ${this.state.order.length}</span>${this.button('next', 'Suivante')}</nav>
      <div class="deck-interest">${this.button('interest', this.state.current && this.state.interested.has(this.state.current.id) ? 'Intérêt retenu' : 'Celle-ci me plaît')}<small>Glissez à gauche pour passer, à droite pour retenir votre intérêt. Cela ne confirme rien.</small></div>` : ''}
      ${this.state.compare ? `<aside class="deck-selection" aria-label="Mon date"><h3>Mon date : ${this.state.selected.size} activité${this.state.selected.size > 1 ? 's' : ''}</h3><ul>${[...this.state.selected.values()].map(a => `<li>${escape(a.name)}</li>`).join('')}</ul><p>Les horaires et trajets seront vérifiés avant la création.</p>${this.button('compose', this.pending ? 'Vérification en cours…' : 'Construire mon date', `class="primary" ${!this.state.selected.size ? 'disabled' : ''}`)}</aside>` : ''}
    </section>`;
    }
    key(e) {
        if (this.state.compare || this.dialog?.open || this.pending || e.target.closest('input,textarea,select'))
            return;
        if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
            e.preventDefault();
            this.state.move(e.key === 'ArrowLeft' ? -1 : 1);
            this.render();
            this.host.querySelector('.date-deck')?.focus({ preventScroll: true });
        }
    }
    async click(e) {
        const button = e.target.closest('button[data-deck-action]');
        if (!button || this.pending)
            return;
        e.stopPropagation();
        e.preventDefault();
        this.error = '';
        const action = button.dataset.deckAction, id = button.dataset.plan, aid = button.dataset.activity;
        try {
            if (action === 'next' || action === 'previous') {
                this.state.move(action === 'next' ? 1 : -1);
                this.render();
                this.host.querySelector(`[data-deck-action="${action}"]`)?.focus({ preventScroll: true });
            }
            else if (action === 'interest') {
                if (this.state.current)
                    this.state.interested.add(this.state.current.id);
                this.message = 'Intérêt retenu. Le programme reste à confirmer.';
                this.render();
            }
            else if (action === 'compare') {
                this.state.compare = !this.state.compare;
                this.render();
                this.host.querySelector('[data-deck-action="compare"]')?.focus({ preventScroll: true });
            }
            else if (action === 'select' && id && aid) {
                const a = this.state.plans[id]?.activities.find(a => a.id === aid);
                if (a)
                    this.state.toggle(a);
                this.render();
            }
            else if (action === 'replace' && id && aid)
                this.replacementDialog(id, aid);
            else if (action === 'open' && id)
                await this.options.open(id);
            else if (action === 'choose' && id)
                await this.options.choose(id);
            else if (action === 'compose')
                await this.compose();
        }
        catch (error) {
            if (this.current()) {
                this.error = error instanceof Error ? error.message : 'Action impossible.';
                this.render();
            }
        }
    }
    replacementDialog(id, aid) {
        const dialog = document.createElement('dialog');
        dialog.className = 'deck-dialog';
        dialog.setAttribute('aria-label', 'Remplacer une activité');
        dialog.innerHTML = `<form><h2>Que préférez-vous à la place ?</h2><p>Les autres étapes restent à leur place. Prix par personne, sauf si vous précisez « à deux ».</p><label for="deck-replacement">Votre préférence</label><input id="deck-replacement" name="constraints" maxlength="500" placeholder="Japonais, moins de 40 €"><div class="row spaced"><button type="button" data-preset="japonais, moins de 40 €">Japonais</button><button type="button" data-preset="calme">Au calme</button><button type="button" data-preset="moins de 15 €">Moins de 15 €</button></div><p class="error" role="alert" hidden></p><div class="row spaced"><button type="submit" class="primary">Chercher une alternative</button><button type="button" data-close>Annuler</button></div></form>`;
        this.host.append(dialog);
        this.dialog = dialog;
        dialog.showModal();
        dialog.querySelector('input')?.focus();
        const input = dialog.querySelector('input');
        dialog.addEventListener('click', e => { e.stopPropagation(); const b = e.target.closest('button'); if (b?.dataset.preset)
            input.value = b.dataset.preset; if (b?.hasAttribute('data-close'))
            dialog.close(); });
        dialog.addEventListener('close', () => { dialog.remove(); this.dialog = null; this.host.querySelector('.date-deck')?.focus({ preventScroll: true }); });
        dialog.querySelector('form').addEventListener('submit', e => {
            e.preventDefault();
            e.stopPropagation();
            if (this.pending)
                return;
            this.pending = true;
            dialog.querySelectorAll('button').forEach(b => b.disabled = true);
            void (async () => {
                try {
                    const plan = readPlan(await this.options.api(`/dates/${encodeURIComponent(id)}/replace-activity`, { method: 'POST', body: { activity_id_to_replace: aid, new_constraints: input.value || null } }));
                    if (!this.current())
                        return;
                    this.state.update(plan);
                    dialog.close();
                    this.message = 'Une étape remplacée. Les autres propositions sont conservées.';
                    this.pending = false;
                    this.render();
                    this.host.querySelector('.date-deck')?.focus({ preventScroll: true });
                }
                catch (error) {
                    if (this.current()) {
                        const p = dialog.querySelector('.error');
                        p.hidden = false;
                        p.textContent = error instanceof Error ? error.message : 'Remplacement impossible.';
                    }
                }
                finally {
                    this.pending = false;
                    dialog.querySelectorAll('button').forEach(b => b.disabled = false);
                }
            })();
        });
    }
    async compose() {
        if (!this.state.selected.size)
            return;
        this.pending = true;
        this.render();
        try {
            const result = readPlan(await this.options.api('/dates/compose', { method: 'POST', body: { selected_activity_ids: [...this.state.selected.keys()], search_id: this.data.search_id } }));
            if (!this.current())
                return;
            this.message = 'Votre programme est prêt. Ouvrez-le pour le confirmer.';
            this.state.selected.clear();
            this.pending = false;
            this.render();
            await this.options.choose(result.id);
        }
        finally {
            this.pending = false;
            if (this.current())
                this.render();
        }
    }
}
