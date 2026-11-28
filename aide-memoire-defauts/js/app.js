import { indexFiche, search, applyFilters, validateFiche } from './search.js';
import {
  createStore, emptyState, addToHistory, toggleFavori, makeNote, notesFor,
  buildExport, parseImport, mergeImport, needsBackupReminder,
} from './userdata.js';

const $ = (sel) => document.querySelector(sel);
const els = {
  q: $('#q'),
  marque: $('#f-marque'),
  type: $('#f-type'),
  gamme: $('#f-gamme'),
  reset: $('#btn-reset'),
  count: $('#count'),
  results: $('#results'),
  home: $('#home-sections'),
  list: $('#view-list'),
  fiche: $('#view-fiche'),
  backup: $('#view-backup'),
};

let fiches = [];
let indexed = [];
let store = null;
let state = emptyState();

// --- Préférences d'affichage (confort uniquement, le stockage peut échouer) ---
function pref(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch { /* navigation privée : on ignore */ }
  return null;
}
function applyPrefs() {
  const theme = pref('theme') || 'dark';
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.size = pref('size') || 'normal';
  document.querySelector('meta[name="theme-color"]').content = theme === 'light' ? '#ffffff' : '#0b0d10';
}
$('#btn-theme').addEventListener('click', () => {
  pref('theme', document.documentElement.dataset.theme === 'light' ? 'dark' : 'light');
  applyPrefs();
});
$('#btn-text').addEventListener('click', () => {
  pref('size', document.documentElement.dataset.size === 'large' ? 'normal' : 'large');
  applyPrefs();
});
applyPrefs();
$('#search-form').addEventListener('submit', (e) => e.preventDefault());

// --- Utilitaires DOM (aucun innerHTML avec des données) ---
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, '');
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
function badge(f) {
  if (f.genereIA && !f.verifie) return h('span', { class: 'badge badge-ia' }, 'IA – à vérifier');
  if (f.fiabilite === 'retour terrain') return h('span', { class: 'badge badge-ok' }, 'Retour terrain');
  return h('span', { class: 'badge badge-ok' }, 'Notice vérifiée');
}
const frDate = (iso) => new Date(iso.length === 10 ? `${iso}T12:00:00` : iso)
  .toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

// --- Données personnelles ---
async function commit(next, { changed = true } = {}) {
  state = { ...next, meta: { ...next.meta, ...(changed ? { lastChange: new Date().toISOString() } : {}) } };
  try {
    await store?.save(state);
  } catch (e) {
    console.error(e);
    alert('Enregistrement impossible sur cet appareil. Pensez à exporter vos notes.');
  }
}
function reindex() {
  const notesByFiche = new Map();
  for (const n of state.notes) {
    notesByFiche.set(n.ficheId, `${notesByFiche.get(n.ficheId) || ''} ${n.causeReelle} ${n.commentaire}`);
  }
  indexed = fiches.map((f) => indexFiche(f, notesByFiche.get(f.id) || ''));
}
const ficheById = (id) => fiches.find((f) => f.id === id);

// --- Filtres ---
function fillSelect(select, values) {
  for (const v of [...new Set(values)].sort((a, b) => a.localeCompare(b, 'fr'))) {
    select.append(h('option', { value: v }, v));
  }
}
function currentFilters() {
  return { marque: els.marque.value, type: els.type.value, gamme: els.gamme.value };
}
const isIdle = () => !els.q.value.trim() && !els.marque.value && !els.type.value && !els.gamme.value;

// --- Liste ---
function resultItem(f, extra) {
  const nbNotes = state.notes.filter((n) => n.ficheId === f.id).length;
  return h('li', {},
    h('a', { href: `#/fiche/${encodeURIComponent(f.id)}` },
      h('span', { class: 'result-code' }, f.code), badge(f),
      state.favoris.includes(f.id) ? h('span', { class: 'pin', 'aria-label': 'épinglée' }, '★') : null,
      h('span', { class: 'result-title' }, f.titre),
      h('span', { class: 'result-meta' },
        `${f.marque} · ${f.gammes.join(', ')} · ${f.type}`,
        nbNotes ? ` · ${nbNotes} note${nbNotes > 1 ? 's' : ''} terrain` : '',
        extra ? ` · ${extra}` : ''),
    ),
  );
}
function homeSection(title, items) {
  if (!items.length) return null;
  return h('section', { class: 'home-section' },
    h('h2', {}, title),
    h('ul', { class: 'results' }, items));
}
function renderHome() {
  if (!isIdle()) { els.home.replaceChildren(); return; }
  const reminder = needsBackupReminder(state)
    ? h('p', { class: 'warn' },
      `⚠ ${state.notes.length} note${state.notes.length > 1 ? 's' : ''} terrain non sauvegardée${state.notes.length > 1 ? 's' : ''}. `,
      h('a', { href: '#/sauvegarde' }, 'Exporter maintenant'))
    : null;
  const favs = state.favoris.map(ficheById).filter(Boolean).map((f) => resultItem(f));
  const recents = state.historique
    .filter((x) => ficheById(x.id))
    .slice(0, 8)
    .map((x) => resultItem(ficheById(x.id), `vue le ${frDate(x.at)}`));
  els.home.replaceChildren(
    ...[reminder, homeSection('★ Épinglées', favs), homeSection('Consultées récemment', recents)].filter(Boolean),
  );
}
function renderList() {
  renderHome();
  const filtered = applyFilters(search(els.q.value, indexed), currentFilters());
  els.results.replaceChildren(...filtered.slice(0, 100).map((f) => resultItem(f)));
  els.count.textContent = filtered.length
    ? (isIdle() ? `Toutes les fiches (${filtered.length})` : `${filtered.length} fiche${filtered.length > 1 ? 's' : ''}`)
    : 'Aucune fiche trouvée. Essayez un autre mot ou retirez un filtre.';
}

// --- Fiche ---
function section(title, ...content) {
  return h('section', {}, h('h3', {}, title), ...content);
}
function noteItem(n) {
  return h('li', { class: 'note' },
    h('p', { class: 'note-meta' }, [frDate(n.date), n.site, n.ligne].filter(Boolean).join(' · ')),
    h('p', { class: 'note-cause' }, n.causeReelle),
    n.commentaire ? h('p', {}, n.commentaire) : null,
    h('button', {
      type: 'button',
      class: 'link-btn danger',
      onclick: async () => {
        if (!confirm('Supprimer cette note terrain ?')) return;
        await commit({ ...state, notes: state.notes.filter((x) => x.id !== n.id) });
        reindex();
        renderFiche(n.ficheId, { keepScroll: true });
      },
    }, 'Supprimer'),
  );
}
function noteForm(f) {
  const status = h('p', { class: 'form-status', 'aria-live': 'polite' });
  const form = h('form', { class: 'note-form' },
    h('label', {}, 'Date', h('input', { name: 'date', type: 'date', value: today(), required: true })),
    h('div', { class: 'two-cols' },
      h('label', {}, 'Site', h('input', { name: 'site', type: 'text', maxlength: '200', autocomplete: 'off' })),
      h('label', {}, 'Ligne / équipement', h('input', { name: 'ligne', type: 'text', maxlength: '200', autocomplete: 'off' })),
    ),
    h('label', {}, 'Cause réelle constatée *',
      h('textarea', { name: 'causeReelle', rows: '3', required: true, maxlength: '2000' })),
    h('label', {}, 'Commentaire (ce qui a été fait…)',
      h('textarea', { name: 'commentaire', rows: '2', maxlength: '2000' })),
    h('p', { class: 'hint' }, 'Reste uniquement sur cet appareil. Évitez les noms de clients sensibles.'),
    h('button', { type: 'submit', class: 'primary-btn' }, 'Ajouter la note'),
    status,
  );
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    try {
      const note = makeNote({ ...data, ficheId: f.id });
      await commit({ ...state, notes: [...state.notes, note] });
      reindex();
      renderFiche(f.id, { keepScroll: true });
    } catch (err) {
      status.textContent = `Note non enregistrée : ${err.message}.`;
    }
  });
  return form;
}
function renderFiche(id, { keepScroll = false } = {}) {
  const f = ficheById(id);
  if (!f) {
    els.fiche.replaceChildren(h('a', { class: 'back', href: '#' }, '← Retour'), h('p', { class: 'empty' }, 'Fiche introuvable.'));
    return;
  }
  const src = f.source || {};
  const isFav = state.favoris.includes(f.id);
  const notes = notesFor(state.notes, f.id);
  els.fiche.replaceChildren(
    h('div', { class: 'fiche' },
      h('div', { class: 'fiche-actions' },
        h('a', { class: 'back', href: '#' }, '← Retour'),
        h('button', {
          type: 'button',
          class: `pin-btn${isFav ? ' active' : ''}`,
          'aria-pressed': String(isFav),
          onclick: async () => {
            await commit({ ...state, favoris: toggleFavori(state.favoris, f.id) }, { changed: false });
            renderFiche(f.id, { keepScroll: true });
          },
        }, isFav ? '★ Épinglée' : '☆ Épingler'),
      ),
      h('p', { class: 'fiche-code' }, f.code, badge(f)),
      h('h2', { class: 'fiche-title' }, f.titre),
      h('p', { class: 'fiche-meta' }, `${f.marque} · ${f.gammes.join(', ')} · ${f.type}`),
      f.genereIA && !f.verifie
        ? h('p', { class: 'warn' }, '⚠ Contenu rédigé par IA, pas encore vérifié contre la notice. Contrôler la source avant de s’y fier.')
        : null,
      notes.length
        ? h('p', { class: 'ok-box' }, `Vécu sur le terrain : ${notes[0].causeReelle}`, notes.length > 1 ? ` (+${notes.length - 1} autre${notes.length > 2 ? 's' : ''})` : '')
        : null,
      section('Signification', h('p', {}, f.signification)),
      section('Causes probables (fréquentes → rares)', h('ol', {}, f.causes.map((c) => h('li', {}, c)))),
      section('Vérifications pas à pas', h('ol', {}, f.verifications.map((c) => h('li', {}, c)))),
      section('Remède', h('p', {}, f.remede)),
      section('Source',
        h('p', {},
          src.document || '—',
          src.reference ? ` — réf. ${src.reference}` : '',
          src.page ? ` — ${/^\d/.test(src.page) ? 'p. ' : ''}${src.page}` : '',
        ),
        h('p', { class: 'fiche-meta' }, `Fiabilité : ${f.fiabilite}`),
      ),
      section(`Notes terrain (${notes.length})`,
        notes.length ? h('ul', { class: 'notes' }, notes.map(noteItem)) : h('p', { class: 'fiche-meta' }, 'Aucune note pour ce défaut.'),
        h('details', { class: 'add-note' },
          h('summary', {}, '+ Ajouter une note terrain'),
          noteForm(f)),
      ),
    ),
  );
  if (!keepScroll) window.scrollTo(0, 0);
}

// --- Sauvegarde ---
function download(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  const a = h('a', { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function renderBackup() {
  const status = h('p', { class: 'form-status', 'aria-live': 'polite' });
  const fileInput = h('input', { type: 'file', accept: 'application/json,.json', class: 'file-input' });
  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    try {
      const imported = parseImport(await file.text());
      const { state: merged, addedNotes } = mergeImport(state, imported);
      await commit(merged);
      reindex();
      status.textContent = `Import réussi : ${addedNotes} note${addedNotes > 1 ? 's' : ''} ajoutée${addedNotes > 1 ? 's' : ''}`
        + (imported.rejected ? `, ${imported.rejected} ignorée${imported.rejected > 1 ? 's' : ''} (invalides)` : '') + '.';
      renderBackupStats();
    } catch (err) {
      status.textContent = `Import impossible : ${err.message}`;
    }
    fileInput.value = '';
  });
  const stats = h('ul', { class: 'stats' });
  function renderBackupStats() {
    const { lastExport } = state.meta;
    stats.replaceChildren(
      h('li', {}, `${state.notes.length} note${state.notes.length > 1 ? 's' : ''} terrain`),
      h('li', {}, `${state.favoris.length} fiche${state.favoris.length > 1 ? 's' : ''} épinglée${state.favoris.length > 1 ? 's' : ''}`),
      h('li', {}, `${state.historique.length} dans l’historique`),
      h('li', {}, lastExport ? `Dernier export : ${frDate(lastExport)}` : 'Jamais exporté'),
      h('li', {}, store?.available
        ? (store.persisted ? 'Stockage protégé contre l’effacement automatique' : 'Stockage non garanti : le navigateur peut l’effacer, exportez régulièrement')
        : 'Stockage indisponible (navigation privée ?) : rien n’est conservé'),
    );
  }
  renderBackupStats();
  els.backup.replaceChildren(
    h('div', { class: 'fiche' },
      h('a', { class: 'back', href: '#' }, '← Retour'),
      h('h2', { class: 'fiche-title' }, 'Sauvegarde de mes données'),
      h('p', {}, 'Notes terrain, favoris et historique sont enregistrés uniquement sur cet appareil. '
        + 'Exportez-les régulièrement (et avant de changer de téléphone). Ne mettez jamais ce fichier dans le dépôt GitHub.'),
      section('État', stats),
      section('Exporter',
        h('button', {
          type: 'button',
          class: 'primary-btn',
          onclick: async () => {
            const now = new Date().toISOString();
            download(`aide-memoire-sauvegarde-${now.slice(0, 10)}.export.json`, JSON.stringify(buildExport(state, now), null, 2));
            await commit({ ...state, meta: { ...state.meta, lastExport: now } }, { changed: false });
            renderBackupStats();
            status.textContent = 'Fichier de sauvegarde téléchargé.';
          },
        }, 'Télécharger la sauvegarde')),
      section('Importer',
        h('p', { class: 'fiche-meta' }, 'Fusionne avec les données actuelles : rien n’est supprimé.'),
        h('label', { class: 'primary-btn file-label' }, 'Choisir un fichier…', fileInput)),
      section('Historique',
        h('button', {
          type: 'button',
          class: 'link-btn danger',
          onclick: async () => {
            if (!confirm('Effacer l’historique de consultation ?')) return;
            await commit({ ...state, historique: [] }, { changed: false });
            renderBackupStats();
          },
        }, 'Effacer l’historique')),
      status,
    ),
  );
  window.scrollTo(0, 0);
}

// --- Navigation ---
async function route() {
  const m = location.hash.match(/^#\/fiche\/(.+)$/);
  const isBackup = location.hash === '#/sauvegarde';
  els.list.hidden = Boolean(m) || isBackup;
  els.fiche.hidden = !m;
  els.backup.hidden = !isBackup;
  if (m) {
    const id = decodeURIComponent(m[1]);
    renderFiche(id);
    if (ficheById(id)) await commit({ ...state, historique: addToHistory(state.historique, id) }, { changed: false });
  } else if (isBackup) {
    renderBackup();
  } else {
    renderList();
  }
}

// --- Démarrage ---
async function init() {
  try {
    const res = await fetch('data/fiches.json', { cache: 'no-cache' });
    const data = await res.json();
    // Règle : aucune fiche sans source. Les fiches invalides sont écartées.
    fiches = data.filter((f) => {
      const errors = validateFiche(f);
      if (errors.length) console.warn(`Fiche ${f.id || f.code} ignorée :`, errors);
      return !errors.length;
    });
  } catch (e) {
    els.count.textContent = 'Impossible de charger les fiches.';
    console.error(e);
    return;
  }
  store = await createStore();
  try {
    state = await store.load();
  } catch (e) {
    console.error('Lecture des données personnelles impossible', e);
  }
  reindex();
  fillSelect(els.marque, fiches.map((f) => f.marque));
  fillSelect(els.type, fiches.map((f) => f.type));
  fillSelect(els.gamme, fiches.flatMap((f) => f.gammes));

  els.q.addEventListener('input', () => { if (location.hash) location.hash = ''; renderList(); });
  for (const s of [els.marque, els.type, els.gamme]) s.addEventListener('change', renderList);
  els.reset.addEventListener('click', () => {
    els.q.value = ''; els.marque.value = ''; els.type.value = ''; els.gamme.value = '';
    renderList(); els.q.focus();
  });
  window.addEventListener('hashchange', route);
  route();
}
init();
