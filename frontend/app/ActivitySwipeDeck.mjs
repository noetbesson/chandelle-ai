import { ActivityCard, esc, labels, safeImage, illustration } from './ActivityCard.mjs';
import { MyDateBuilder } from './MyDateBuilder.mjs';
import { readPlan } from './DateProposalDeck.mjs';
/** Session-only selection. Passing is temporary, never a preference or a memory write. */
export class ActivityState {
    activities;
    kept = new Map();
    passed = new Set();
    overview = false;
    constructor(activities) {
        if (activities.length > 50 || new Set(activities.map(a => a.id)).size !== activities.length)
            throw Error('Lot d’activités invalide.');
        const categories = [...new Set(activities.map(a => a.category))];
        this.activities = structuredClone(activities).sort((a, b) => categories.indexOf(a.category) - categories.indexOf(b.category));
    }
    get remaining() { return this.activities.filter(a => !this.kept.has(a.id) && !this.passed.has(a.id)); }
    get current() { return this.remaining[0]; }
    keep(id) { const a = this.activities.find(a => a.id === id); if (!a)
        throw Error('Activité inconnue.'); this.kept.set(id, a); this.passed.delete(id); }
    pass(id) { if (!this.activities.some(a => a.id === id))
        throw Error('Activité inconnue.'); if (!this.kept.has(id))
        this.passed.add(id); }
    remove(id) { this.kept.delete(id); }
}
export class ActivitySwipeDeck {
    host;
    data;
    options;
    state;
    owner;
    abort = new AbortController();
    disposed = false;
    pending = false;
    expanded = globalThis.matchMedia?.('(min-width:701px)').matches ?? true;
    message = '';
    composed = null;
    pointer = null;
    images = new Map();
    constructor(host, data, options) {
        this.host = host;
        this.data = data;
        this.options = options;
        const rows = data.activities ?? [];
        if (rows.some(a => !a.id || !a.name || (a.price_per_person !== null && !Number.isFinite(a.price_per_person)) || (a.start !== null && !Number.isFinite(Date.parse(a.start))) || (a.end !== null && !Number.isFinite(Date.parse(a.end)))))
            throw Error('Activités reçues incomplètes.');
        this.state = new ActivityState(rows);
        this.owner = options.identity();
        this.render();
        this.host.scrollIntoView({ block: 'start' });
        globalThis.matchMedia?.('(min-width:701px)').addEventListener('change', e => { if (this.live()) {
            this.expanded = e.matches;
            this.render();
        } }, { signal: this.abort.signal });
        host.addEventListener('error', e => {
            if (!(e.target instanceof HTMLImageElement))
                return;
            const card = e.target.closest('[data-activity-id]');
            const activity = this.state.activities.find(a => a.id === card?.dataset.activityId);
            if (!activity)
                return;
            activity.image_url = null;
            e.target.outerHTML = illustration(activity.category);
            const label = card?.querySelector('.activity-origin');
            if (label)
                label.textContent = activity.demo ? 'Exemple fictif' : 'Illustration';
        }, { capture: true, signal: this.abort.signal });
        host.addEventListener('click', e => { void this.click(e); }, { signal: this.abort.signal });
        host.addEventListener('keydown', e => {
            if (!this.live() || this.pending || this.state.overview || !e.target.closest('.activity-choice') || e.target.closest('button,input,a'))
                return;
            if (['ArrowLeft', 'ArrowRight', 'Enter'].includes(e.key)) {
                e.preventDefault();
                this.choose(e.key === 'ArrowLeft' ? 'pass' : 'keep');
            }
        }, { signal: this.abort.signal });
        host.addEventListener('pointerdown', e => {
            const card = e.target.closest('.activity-choice');
            if (!card || this.state.overview || this.pending || e.target.closest('button,a') || e.button !== 0)
                return;
            this.pointer = { x: e.clientX, y: e.clientY, card, id: e.pointerId };
            card.setPointerCapture(e.pointerId);
        }, { signal: this.abort.signal });
        host.addEventListener('pointermove', e => {
            const p = this.pointer;
            if (!p)
                return;
            const dx = e.clientX - p.x, dy = e.clientY - p.y;
            if (Math.abs(dy) > Math.abs(dx) * 1.4 && Math.abs(dy) > 18) {
                this.resetPointer();
                return;
            }
            p.card.style.transform = `translateX(${Math.max(-140, Math.min(140, dx))}px) rotate(${Math.max(-10, Math.min(10, dx / 18))}deg)`;
            p.card.style.setProperty('--keep-opacity', String(Math.max(0, Math.min(1, dx / 90))));
            p.card.style.setProperty('--pass-opacity', String(Math.max(0, Math.min(1, -dx / 90))));
        }, { signal: this.abort.signal });
        host.addEventListener('pointercancel', () => this.resetPointer(), { signal: this.abort.signal });
        host.addEventListener('pointerup', e => {
            const p = this.pointer;
            if (!p)
                return;
            const dx = e.clientX - p.x, dy = e.clientY - p.y;
            this.resetPointer();
            if (Math.abs(dx) > 65 && Math.abs(dx) > Math.abs(dy) * 1.3) {
                e.preventDefault();
                this.choose(dx > 0 ? 'keep' : 'pass');
            }
        }, { signal: this.abort.signal });
    }
    live() { return !this.disposed && this.host.isConnected && this.options.identity() === this.owner; }
    destroy() { this.disposed = true; this.resetPointer(); this.abort.abort(); this.state.kept.clear(); this.images.clear(); }
    receivePlan(value) { if (this.live() && this.composed && value?.id === this.composed.id)
        this.composed = readPlan(value); }
    resetPointer() { const p = this.pointer; this.pointer = null; if (p) {
        p.card.style.transform = '';
        p.card.style.removeProperty('--keep-opacity');
        p.card.style.removeProperty('--pass-opacity');
        if (p.card.hasPointerCapture(p.id))
            p.card.releasePointerCapture(p.id);
    } }
    choose(action, id = this.state.current?.id) {
        if (!this.live() || this.pending || !id)
            return;
        const a = this.state.activities.find(x => x.id === id);
        if (!a)
            return;
        this.state[action](id);
        this.composed = null;
        this.message = action === 'keep' ? `${a.name} gardée dans votre date.` : `${a.name} passée pour cette fois.`;
        this.render();
        if (!this.state.overview)
            this.host.querySelector('.activity-choice')?.focus({ preventScroll: true });
    }
    async click(e) {
        const b = e.target.closest('[data-activity-action]');
        if (!b)
            return;
        e.stopPropagation();
        if (!this.live() || this.pending)
            return;
        const action = b.dataset.activityAction, id = b.dataset.id;
        if (action === 'keep' || action === 'pass') {
            this.choose(action, id);
            return;
        }
        if (action === 'remove' && id) {
            this.state.remove(id);
            this.composed = null;
            this.message = 'Activité retirée. Elle reste disponible dans la découverte.';
        }
        if (action === 'view')
            this.state.overview = !this.state.overview;
        if (action === 'builder')
            this.expanded = !this.expanded;
        if (action === 'review') {
            this.state.passed.clear();
            this.message = 'Les cartes passées sont de nouveau disponibles.';
        }
        if (action === 'compose') {
            if (!this.state.kept.size)
                return;
            if ([...this.state.kept.values()].some(a => a.composable === false)) {
                this.message = 'Certains lieux gardés n’ont pas encore de prix, d’horaire ou de localisation suffisants pour composer un programme. Consultez leurs sources ; votre sélection est conservée.';
                this.render();
                return;
            }
            if (this.composed) {
                await this.options.choose(this.composed.id);
                return;
            }
            this.pending = true;
            this.message = 'Vérification des horaires, du budget et des trajets…';
            this.render();
            try {
                const result = await this.options.api('/dates/compose', { method: 'POST', body: { search_id: this.data.search_id, selected_activity_ids: [...this.state.kept.keys()] } });
                if (!this.live())
                    return;
                this.composed = readPlan(result);
                this.message = 'Votre date est prêt à relire. Aucune réservation ni confirmation envoyée.';
                await this.options.choose(this.composed.id);
            }
            catch (error) {
                if (this.live()) {
                    this.message = error instanceof Error ? error.message : 'La composition a échoué. Votre sélection est conservée.';
                    this.expanded = true;
                }
            }
            finally {
                this.pending = false;
                if (this.live())
                    this.render();
            }
            return;
        }
        this.render();
        this.host.querySelector(`[data-activity-action="${action}"]`)?.focus({ preventScroll: true });
    }
    render() {
        const current = this.state.current, remaining = this.state.remaining, kept = this.state.kept;
        const shown = this.state.activities.filter(a => !this.state.passed.has(a.id));
        this.host.innerHTML = `<section class="activity-discovery" aria-label="Choisir nos activités"><header class="activity-deck-heading"><div><p class="eyebrow">À VOUS DE CHOISIR</p><h2>${this.state.overview ? 'Toutes vos idées' : esc(current ? labels[current.category] ?? current.category : 'Votre sélection est prête')}</h2><p>${remaining.length} carte${remaining.length > 1 ? 's' : ''} à parcourir · ${kept.size} gardée${kept.size > 1 ? 's' : ''}</p></div><button type="button" data-activity-action="view" aria-pressed="${this.state.overview}">${this.state.overview ? 'Découverte' : 'Vue d’ensemble'}</button></header><p class="activity-demo-note">Les horaires et disponibilités restent à confirmer auprès des lieux.</p>${(this.data.warnings ?? []).map(w => `<p class="muted" role="status">${esc(w)}</p>`).join('')}<div class="activity-stage ${this.state.overview ? 'overview' : ''}"><div class="activity-cards">${!this.state.activities.length ? `<p class="empty" role="status">${esc(this.data.message || 'Aucune activité ne correspond à vos critères actuels. Essayez d’élargir votre recherche.')}</p>` : this.state.overview ? shown.map(a => ActivityCard(a, kept.has(a.id), true)).join('') : current ? `<div class="activity-stack">${ActivityCard(current)}</div><p class="swipe-help">Glissez à droite pour garder, à gauche pour passer.<br>Au clavier : flèches, ou Entrée pour garder.</p>` : '<div class="activity-finished"><h3>Vous avez fait le tour.</h3><p>Retrouvez vos choix dans Mon date ou revoyez les cartes passées.</p></div>'}${this.state.passed.size ? '<button type="button" class="review-passed" data-activity-action="review">Revoir les cartes passées</button>' : ''}</div>${MyDateBuilder(kept.values(), this.data, this.expanded, this.pending, !!this.composed)}</div><p class="activity-status" role="status" aria-live="polite">${esc(this.message)}</p></section>`;
        // Only actual URLs, never all images at once; no private media is cached by the worker.
        const urls = remaining.slice(1, 4).map(a => safeImage(a.image_url)).filter((u) => !!u);
        for (const url of [...this.images.keys()])
            if (!urls.includes(url))
                this.images.delete(url);
        for (const url of urls)
            if (!this.images.has(url)) {
                const image = new Image();
                image.referrerPolicy = 'no-referrer';
                image.src = url;
                this.images.set(url, image);
            }
    }
}
