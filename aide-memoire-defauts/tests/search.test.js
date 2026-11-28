import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  normalize, canonicalCode, levenshtein, indexFiche, search, applyFilters, validateFiche,
} from '../js/search.js';

const base = {
  fiabilite: 'notice constructeur', genereIA: true, verifie: false,
  source: { document: 'Notice test', reference: 'X', page: 'à vérifier' },
  verifications: ['v'], remede: 'r',
};
const fixtures = [
  { ...base, id: 'a', code: 'F07801', titre: 'Surintensité moteur', marque: 'Siemens', type: 'variateur', gammes: ['G120'],
    symptomes: ['variateur se met en défaut au démarrage'], signification: 'Courant moteur trop élevé', causes: ['rampe trop courte'] },
  { ...base, id: 'b', code: 'OCF', titre: 'Surintensité', marque: 'Schneider', type: 'variateur', gammes: ['ATV320'],
    symptomes: ['moteur ne démarre pas'], signification: 'Courant excessif', causes: ['court-circuit'] },
  { ...base, id: 'c', code: 'F30003', titre: 'Sous-tension circuit intermédiaire', marque: 'Siemens', type: 'variateur', gammes: ['G120'],
    symptomes: ['coupure réseau'], signification: 'Tension DC trop basse', causes: ['réseau absent'] },
];
const idx = fixtures.map(indexFiche);
const ids = (q) => search(q, idx).map((f) => f.id);

test('normalisation des accents et de la casse', () => {
  assert.equal(normalize('Démarré  ÉCHEC!'), 'demarre echec');
});

test('variantes d’écriture d’un code', () => {
  for (const v of ['F07801', 'f7801', 'F 07801', 'F-07801', 'f07801']) {
    assert.equal(canonicalCode(v), 'f7801', v);
  }
});

test('levenshtein borné', () => {
  assert.equal(levenshtein('moteur', 'moteru', 2), 2);
  assert.equal(levenshtein('abc', 'abcdefgh', 2), 3);
});

test('recherche par code exact et variante', () => {
  assert.equal(ids('F07801')[0], 'a');
  assert.equal(ids('f7801')[0], 'a');
  assert.equal(ids('ocf')[0], 'b');
});

test('recherche par code avec une faute de frappe', () => {
  assert.equal(ids('F07810')[0], 'a');
});

test('recherche par symptôme tolérante', () => {
  assert.equal(ids('moteur ne démarre pas')[0], 'b');
  assert.ok(ids('moteur demarage').includes('b'));
  assert.ok(ids('surintensite').includes('a'));
  assert.ok(ids('sous tension')[0] === 'c');
});

test('aucun résultat pour une requête sans rapport', () => {
  assert.deepEqual(ids('imprimante papier'), []);
});

test('requête vide : toutes les fiches', () => {
  assert.equal(ids('').length, 3);
});

test('filtres marque / type / gamme', () => {
  assert.deepEqual(applyFilters(fixtures, { marque: 'Schneider' }).map((f) => f.id), ['b']);
  assert.deepEqual(applyFilters(fixtures, { gamme: 'G120' }).map((f) => f.id), ['a', 'c']);
  assert.equal(applyFilters(fixtures, { type: 'automate' }).length, 0);
});

test('une fiche sans source est refusée', () => {
  assert.deepEqual(validateFiche(fixtures[0]), []);
  const { source, ...sansSource } = fixtures[0];
  assert.ok(validateFiche(sansSource).includes('source manquante'));
});

test('données : toutes les fiches de data/fiches.json sont valides et uniques', () => {
  const data = JSON.parse(readFileSync(new URL('../data/fiches.json', import.meta.url), 'utf8'));
  assert.ok(Array.isArray(data) && data.length > 0);
  const seen = new Set();
  for (const f of data) {
    assert.deepEqual(validateFiche(f), [], `fiche ${f.id}`);
    assert.ok(!seen.has(f.id), `id en double : ${f.id}`);
    seen.add(f.id);
    if (f.genereIA) assert.equal(f.verifie, false, `${f.id} : fiche IA marquée vérifiée sans relecture`);
  }
});
