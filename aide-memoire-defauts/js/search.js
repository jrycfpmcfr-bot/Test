// Recherche tolérante aux fautes et aux variantes d'écriture.
// Module sans dépendance, utilisable dans le navigateur et sous Node (tests).

const STOPWORDS = new Set([
  'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'd', 'l', 'au', 'aux',
  'et', 'ou', 'en', 'a', 'ne', 'pas', 'plus', 'est', 'sur', 'par', 'pour',
  'avec', 'sans', 'se', 'sa', 'son', 'ses', 'il', 'elle', 'on', 'que', 'qui',
]);

/** Minuscules, sans accents, ponctuation remplacée par des espaces. */
export function normalize(text) {
  return String(text ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/œ/g, 'oe')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/**
 * Forme canonique d'un code défaut : sans espaces ni tirets, et sans zéros
 * en tête de la partie numérique ("F 07801", "f7801", "F-07801" -> "f7801").
 */
export function canonicalCode(text) {
  const compact = normalize(text).replace(/ /g, '');
  return compact.replace(/^([a-z]*)0+(?=\d)/, '$1');
}

export function tokenize(text) {
  return normalize(text)
    .split(' ')
    .filter((t) => t && !STOPWORDS.has(t));
}

/** Distance de Levenshtein bornée (renvoie max+1 si dépassée). */
export function levenshtein(a, b, max = 2) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let rowMin = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      if (cur[j] < rowMin) rowMin = cur[j];
    }
    if (rowMin > max) return max + 1;
    prev = cur;
  }
  return prev[b.length];
}

/** Ressemblance entre un mot de la requête et un mot de la fiche (0 à 1). */
export function wordScore(q, w) {
  if (q === w) return 1;
  if (q.length >= 2 && w.startsWith(q)) return 0.9;
  // Variantes de terminaison : demarre / demarrage / demarrer
  const minLen = Math.min(q.length, w.length);
  if (minLen >= 5) {
    let p = 0;
    while (p < minLen && q[p] === w[p]) p++;
    if (p >= 5 && p >= minLen - 3) return 0.8;
  }
  if (q.length >= 4) {
    const max = q.length >= 7 ? 2 : 1;
    const d = levenshtein(q, w, max);
    if (d <= max) return d === 1 ? 0.7 : 0.55;
  }
  return 0;
}

const FIELD_WEIGHTS = {
  titre: 1,
  symptomes: 1,
  signification: 0.8,
  causes: 0.7,
  gammes: 0.9,
  marque: 0.6,
  type: 0.6,
  verifications: 0.5,
  remede: 0.5,
  notes: 0.7, // notes terrain personnelles (cause réelle, commentaire)
};

/** Prépare l'index d'une fiche ; `notesText` = texte des notes terrain associées. */
export function indexFiche(fiche, notesText = '') {
  const fields = {};
  for (const key of Object.keys(FIELD_WEIGHTS)) {
    const value = key === 'notes' ? notesText : fiche[key];
    const text = Array.isArray(value) ? value.join(' ') : value;
    fields[key] = [...new Set(tokenize(text))];
  }
  return { fiche, code: canonicalCode(fiche.code), fields };
}

function codeScore(query, code) {
  const q = canonicalCode(query);
  if (!q || !code) return 0;
  if (q === code) return 3;
  if (q.length >= 2 && code.startsWith(q)) return 2;
  if (q.length >= 4 && /\d/.test(q)) {
    // Faute de frappe ou chiffres inversés (F07810 au lieu de F07801)
    const d = levenshtein(q, code, 2);
    if (d === 1) return 1.5;
    if (d === 2 && q.length >= 5) return 1.1;
  }
  return 0;
}

/** Score global d'une fiche indexée pour une requête (0 = pas de résultat). */
export function scoreFiche(query, indexed) {
  const byCode = codeScore(query, indexed.code);
  const tokens = tokenize(query);
  if (!tokens.length) return byCode;

  let total = 0;
  let matched = 0;
  for (const t of tokens) {
    // Un mot de la requête peut être le code lui-même ("G120 F7801")
    let best = codeScore(t, indexed.code) > 0 ? 1.2 : 0;
    for (const [field, words] of Object.entries(indexed.fields)) {
      const weight = FIELD_WEIGHTS[field];
      for (const w of words) {
        const s = wordScore(t, w) * weight;
        if (s > best) best = s;
      }
    }
    if (best > 0.3) matched++;
    total += best;
  }
  // Tous les mots (ou presque) doivent correspondre à quelque chose.
  const needed = tokens.length <= 2 ? tokens.length : Math.ceil(tokens.length * 0.66);
  const textScore = matched >= needed ? total / tokens.length : 0;
  return Math.max(byCode, textScore);
}

/** Recherche : renvoie les fiches triées par pertinence. */
export function search(query, indexedList, { minScore = 0.45 } = {}) {
  if (!normalize(query)) return indexedList.map((i) => i.fiche);
  return indexedList
    .map((i) => ({ fiche: i.fiche, score: scoreFiche(query, i) }))
    .filter((r) => r.score >= minScore)
    .sort((a, b) => b.score - a.score)
    .map((r) => r.fiche);
}

/** Filtres marque / type / gamme (valeur vide = pas de filtre). */
export function applyFilters(fiches, { marque = '', type = '', gamme = '' } = {}) {
  return fiches.filter(
    (f) =>
      (!marque || f.marque === marque) &&
      (!type || f.type === type) &&
      (!gamme || (f.gammes || []).includes(gamme)),
  );
}

/** Contrôle des règles sur les données : pas de fiche sans source. */
export function validateFiche(f) {
  const errors = [];
  for (const key of ['id', 'code', 'titre', 'marque', 'type', 'signification', 'remede']) {
    if (!f[key] || typeof f[key] !== 'string') errors.push(`champ « ${key} » manquant`);
  }
  for (const key of ['gammes', 'causes', 'verifications']) {
    if (!Array.isArray(f[key]) || !f[key].length) errors.push(`liste « ${key} » vide`);
  }
  if (!f.source || !f.source.document) errors.push('source manquante');
  if (!['notice constructeur', 'retour terrain'].includes(f.fiabilite)) {
    errors.push('fiabilité invalide');
  }
  if (typeof f.genereIA !== 'boolean') errors.push('indicateur « genereIA » manquant');
  return errors;
}
