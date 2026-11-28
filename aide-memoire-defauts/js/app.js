import { indexFiche, search, applyFilters, validateFiche } from './search.js';

const $ = (sel) => document.querySelector(sel);
const els = {
  q: $('#q'),
  marque: $('#f-marque'),
  type: $('#f-type'),
  gamme: $('#f-gamme'),
  reset: $('#btn-reset'),
  count: $('#count'),
  results: $('#results'),
  list: $('#view-list'),
  fiche: $('#view-fiche'),
};

let fiches = [];
let indexed = [];

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
    else el.setAttribute(k, v);
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

// --- Filtres ---
function fillSelect(select, values) {
  for (const v of [...new Set(values)].sort((a, b) => a.localeCompare(b, 'fr'))) {
    select.append(h('option', { value: v }, v));
  }
}
function currentFilters() {
  return { marque: els.marque.value, type: els.type.value, gamme: els.gamme.value };
}

// --- Liste ---
function renderList() {
  const filtered = applyFilters(search(els.q.value, indexed), currentFilters());
  els.results.replaceChildren(
    ...filtered.slice(0, 100).map((f) =>
      h('li', {},
        h('a', { href: `#/fiche/${encodeURIComponent(f.id)}` },
          h('span', { class: 'result-code' }, f.code), badge(f),
          h('span', { class: 'result-title' }, f.titre),
          h('span', { class: 'result-meta' }, `${f.marque} · ${f.gammes.join(', ')} · ${f.type}`),
        ),
      ),
    ),
  );
  els.count.textContent = filtered.length
    ? `${filtered.length} fiche${filtered.length > 1 ? 's' : ''}`
    : 'Aucune fiche trouvée. Essayez un autre mot ou retirez un filtre.';
}

// --- Fiche ---
function section(title, content) {
  return h('section', {}, h('h3', {}, title), content);
}
function renderFiche(id) {
  const f = fiches.find((x) => x.id === id);
  if (!f) {
    els.fiche.replaceChildren(h('a', { class: 'back', href: '#' }, '← Retour'), h('p', { class: 'empty' }, 'Fiche introuvable.'));
    return;
  }
  const src = f.source || {};
  els.fiche.replaceChildren(
    h('div', { class: 'fiche' },
      h('a', { class: 'back', href: '#' }, '← Retour'),
      h('p', { class: 'fiche-code' }, f.code, badge(f)),
      h('h2', { class: 'fiche-title' }, f.titre),
      h('p', { class: 'fiche-meta' }, `${f.marque} · ${f.gammes.join(', ')} · ${f.type}`),
      f.genereIA && !f.verifie
        ? h('p', { class: 'warn' }, '⚠ Contenu rédigé par IA, pas encore vérifié contre la notice. Contrôler la source avant de s’y fier.')
        : null,
      section('Signification', h('p', {}, f.signification)),
      section('Causes probables (de la plus fréquente à la plus rare)', h('ol', {}, f.causes.map((c) => h('li', {}, c)))),
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
    ),
  );
  window.scrollTo(0, 0);
}

// --- Navigation ---
function route() {
  const m = location.hash.match(/^#\/fiche\/(.+)$/);
  els.list.hidden = Boolean(m);
  els.fiche.hidden = !m;
  if (m) renderFiche(decodeURIComponent(m[1]));
  else renderList();
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
  indexed = fiches.map(indexFiche);
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
