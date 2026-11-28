// Données personnelles : notes terrain, favoris, historique.
// Fonctions pures (testées sous Node) + stockage IndexedDB sur l'appareil.
// Ces données ne quittent jamais le téléphone, sauf export manuel.

export const HISTORY_MAX = 30;
export const BACKUP_REMINDER_DAYS = 14;
export const EXPORT_FORMAT = 'aide-memoire-defauts/sauvegarde';
export const EXPORT_VERSION = 1;

export function emptyState() {
  return { favoris: [], historique: [], notes: [], meta: { lastExport: null, lastChange: null } };
}

// --- Historique ---
export function addToHistory(historique, ficheId, now = new Date().toISOString(), max = HISTORY_MAX) {
  return [{ id: ficheId, at: now }, ...historique.filter((h) => h.id !== ficheId)].slice(0, max);
}

// --- Favoris ---
export function toggleFavori(favoris, ficheId) {
  return favoris.includes(ficheId) ? favoris.filter((id) => id !== ficheId) : [ficheId, ...favoris];
}

// --- Notes terrain ---
const NOTE_TEXT_MAX = 2000;
const clean = (v, max = 200) => String(v ?? '').trim().slice(0, max);

export function validateNote(n) {
  const errors = [];
  if (!n || typeof n !== 'object') return ['note invalide'];
  if (!n.ficheId) errors.push('fiche manquante');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(n.date || '')) errors.push('date invalide');
  if (!clean(n.causeReelle, NOTE_TEXT_MAX)) errors.push('cause réelle obligatoire');
  return errors;
}

export function makeNote(input, { id, now = new Date().toISOString() } = {}) {
  const note = {
    id: id || input.id || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
    ficheId: clean(input.ficheId),
    date: clean(input.date, 10),
    site: clean(input.site),
    ligne: clean(input.ligne),
    causeReelle: clean(input.causeReelle, NOTE_TEXT_MAX),
    commentaire: clean(input.commentaire, NOTE_TEXT_MAX),
    createdAt: input.createdAt || now,
    fiabilite: 'retour terrain',
  };
  const errors = validateNote(note);
  if (errors.length) throw new Error(errors.join(', '));
  return note;
}

export function notesFor(notes, ficheId) {
  return notes
    .filter((n) => n.ficheId === ficheId)
    .sort((a, b) => b.date.localeCompare(a.date) || b.createdAt.localeCompare(a.createdAt));
}

// --- Sauvegarde ---
export function buildExport(state, now = new Date().toISOString()) {
  return {
    format: EXPORT_FORMAT,
    version: EXPORT_VERSION,
    exportedAt: now,
    favoris: state.favoris,
    historique: state.historique,
    notes: state.notes,
  };
}

/** Lit un fichier de sauvegarde ; lève une erreur lisible s'il est invalide. */
export function parseImport(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error('Fichier illisible (JSON invalide).');
  }
  if (!data || data.format !== EXPORT_FORMAT) throw new Error('Ce fichier n’est pas une sauvegarde de l’aide-mémoire.');
  if (data.version > EXPORT_VERSION) throw new Error('Sauvegarde créée par une version plus récente de l’application.');
  const notes = [];
  let rejected = 0;
  for (const n of Array.isArray(data.notes) ? data.notes : []) {
    try { notes.push(makeNote(n)); } catch { rejected++; }
  }
  return {
    favoris: (Array.isArray(data.favoris) ? data.favoris : []).filter((x) => typeof x === 'string'),
    historique: (Array.isArray(data.historique) ? data.historique : [])
      .filter((h) => h && typeof h.id === 'string' && typeof h.at === 'string'),
    notes,
    rejected,
  };
}

/** Fusion : rien n'est supprimé, les notes sont dédoublonnées par identifiant. */
export function mergeImport(state, imported) {
  const known = new Set(state.notes.map((n) => n.id));
  const added = imported.notes.filter((n) => !known.has(n.id));
  const historique = [...state.historique, ...imported.historique]
    .sort((a, b) => b.at.localeCompare(a.at))
    .filter((h, i, arr) => arr.findIndex((x) => x.id === h.id) === i)
    .slice(0, HISTORY_MAX);
  return {
    state: {
      ...state,
      favoris: [...new Set([...state.favoris, ...imported.favoris])],
      historique,
      notes: [...state.notes, ...added],
    },
    addedNotes: added.length,
  };
}

/** Rappel de sauvegarde : des notes existent et aucun export récent ne les couvre. */
export function needsBackupReminder(state, now = new Date()) {
  if (!state.notes.length) return false;
  const { lastExport, lastChange } = state.meta;
  if (!lastExport) return true;
  const unsaved = Boolean(lastChange && lastChange > lastExport);
  const days = (now - new Date(lastExport)) / 86400000;
  return unsaved && days >= BACKUP_REMINDER_DAYS;
}

// --- Stockage IndexedDB (navigateur uniquement) ---
const DB_NAME = 'aide-memoire-defauts';
const STORE = 'kv';
const KEYS = ['favoris', 'historique', 'notes', 'meta'];

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function createStore() {
  let db = null;
  try {
    db = await openDb();
  } catch (e) {
    console.warn('IndexedDB indisponible : les données ne seront pas conservées.', e);
  }
  let persisted = false;
  try {
    persisted = (await navigator.storage?.persisted?.()) || (await navigator.storage?.persist?.()) || false;
  } catch { /* non pris en charge */ }

  async function load() {
    const state = emptyState();
    if (!db) return state;
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const store = tx.objectStore(STORE);
      for (const key of KEYS) {
        const r = store.get(key);
        r.onsuccess = () => { if (r.result !== undefined) state[key] = r.result; };
      }
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    state.meta = { ...emptyState().meta, ...state.meta };
    return state;
  }

  async function save(state) {
    if (!db) return;
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      const store = tx.objectStore(STORE);
      for (const key of KEYS) store.put(state[key], key);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  }

  return { load, save, available: Boolean(db), persisted };
}
