import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  emptyState, addToHistory, toggleFavori, makeNote, notesFor, buildExport,
  parseImport, mergeImport, needsBackupReminder, HISTORY_MAX,
} from '../js/userdata.js';
import { indexFiche, search } from '../js/search.js';

test('historique : plus récent en tête, sans doublon, borné', () => {
  let h = [];
  h = addToHistory(h, 'a', '2026-01-01');
  h = addToHistory(h, 'b', '2026-01-02');
  h = addToHistory(h, 'a', '2026-01-03');
  assert.deepEqual(h.map((x) => x.id), ['a', 'b']);
  for (let i = 0; i < 50; i++) h = addToHistory(h, `f${i}`);
  assert.equal(h.length, HISTORY_MAX);
});

test('favoris : épingler puis désépingler', () => {
  const f = toggleFavori([], 'a');
  assert.deepEqual(f, ['a']);
  assert.deepEqual(toggleFavori(f, 'a'), []);
});

test('note : cause réelle et date obligatoires, champs nettoyés', () => {
  assert.throws(() => makeNote({ ficheId: 'a', date: '2026-01-01', causeReelle: '  ' }), /cause réelle/);
  assert.throws(() => makeNote({ ficheId: 'a', date: '01/01/2026', causeReelle: 'x' }), /date/);
  const n = makeNote({ ficheId: 'a', date: '2026-01-01', site: '  Site A ', causeReelle: 'Câble moteur pincé' });
  assert.equal(n.site, 'Site A');
  assert.equal(n.fiabilite, 'retour terrain');
});

test('notes d’une fiche triées de la plus récente à la plus ancienne', () => {
  const notes = [
    makeNote({ ficheId: 'a', date: '2026-01-01', causeReelle: 'x' }),
    makeNote({ ficheId: 'b', date: '2026-03-01', causeReelle: 'y' }),
    makeNote({ ficheId: 'a', date: '2026-02-01', causeReelle: 'z' }),
  ];
  assert.deepEqual(notesFor(notes, 'a').map((n) => n.causeReelle), ['z', 'x']);
});

test('export puis import : aller-retour et fusion sans doublon', () => {
  const s = emptyState();
  s.favoris = ['a'];
  s.notes = [makeNote({ ficheId: 'a', date: '2026-01-01', causeReelle: 'x' }, { id: 'n1' })];
  const text = JSON.stringify(buildExport(s));
  const imported = parseImport(text);
  const { state, addedNotes } = mergeImport(s, imported);
  assert.equal(addedNotes, 0);
  assert.equal(state.notes.length, 1);

  const other = emptyState();
  const merged = mergeImport(other, imported);
  assert.equal(merged.addedNotes, 1);
  assert.deepEqual(merged.state.favoris, ['a']);
});

test('import : fichiers invalides refusés, notes invalides ignorées', () => {
  assert.throws(() => parseImport('pas du json'), /illisible/);
  assert.throws(() => parseImport('{"format":"autre"}'), /pas une sauvegarde/);
  const r = parseImport(JSON.stringify({
    format: 'aide-memoire-defauts/sauvegarde', version: 1,
    notes: [{ ficheId: 'a', date: '2026-01-01', causeReelle: 'ok' }, { ficheId: 'a' }],
  }));
  assert.equal(r.notes.length, 1);
  assert.equal(r.rejected, 1);
});

test('rappel de sauvegarde', () => {
  const s = emptyState();
  assert.equal(needsBackupReminder(s), false); // pas de notes
  s.notes = [makeNote({ ficheId: 'a', date: '2026-01-01', causeReelle: 'x' })];
  assert.equal(needsBackupReminder(s), true); // jamais exporté
  s.meta = { lastExport: '2026-01-01T00:00:00Z', lastChange: '2026-01-02T00:00:00Z' };
  assert.equal(needsBackupReminder(s, new Date('2026-01-05')), false); // export récent
  assert.equal(needsBackupReminder(s, new Date('2026-02-01')), true); // ancien + modifs
  s.meta.lastChange = '2025-12-31T00:00:00Z';
  assert.equal(needsBackupReminder(s, new Date('2026-06-01')), false); // rien de nouveau
});

test('recherche dans les notes terrain', () => {
  const f = {
    id: 'a', code: 'F07801', titre: 'Surintensité', marque: 'Siemens', type: 'variateur', gammes: ['G120'],
    symptomes: [], signification: 's', causes: ['c'], verifications: ['v'], remede: 'r',
  };
  assert.deepEqual(search('presse-étoupe', [indexFiche(f)]), []);
  assert.equal(search('presse-étoupe', [indexFiche(f, 'Eau dans la boîte à bornes, presse-étoupe mal serré')]).length, 1);
});
