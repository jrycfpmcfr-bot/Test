"use strict";

// ---------------------------------------------------------------------------
// Utilitaires
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const S = { nom: "Jarvis", utilisateur: "Monsieur", categories: [], mails: [], evenements: [],
            historique: [], enAttente: null, voixPremium: false };

function el(tag, attrs = {}, ...enfants) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const e of enfants) n.append(e instanceof Node ? e : document.createTextNode(e ?? ""));
  return n;
}

function lireReglage(cle, defaut) {
  try { const v = localStorage.getItem("assistant." + cle); return v === null ? defaut : JSON.parse(v); }
  catch { return defaut; }
}
function ecrireReglage(cle, v) { try { localStorage.setItem("assistant." + cle, JSON.stringify(v)); } catch {} }

async function api(chemin, options = {}) {
  const rep = await fetch(chemin, {
    headers: { "Content-Type": "application/json" }, ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const json = await rep.json().catch(() => ({}));
  if (!rep.ok) throw new Error(json.erreur || `Erreur ${rep.status}`);
  return json;
}

let minuteurBandeau;
function bandeau(texte, erreur = false) {
  const b = $("bandeau");
  b.textContent = texte; b.className = "bandeau" + (erreur ? " erreur" : ""); b.hidden = false;
  clearTimeout(minuteurBandeau);
  minuteurBandeau = setTimeout(() => (b.hidden = true), 6000);
}

function etat(mode) {
  const n = $("noyau");
  n.classList.remove("ecoute", "reflexion", "parle");
  if (mode) n.classList.add(mode);
  $("etat").textContent = { ecoute: "J'ÉCOUTE", reflexion: "ANALYSE", parle: "" }[mode] ?? "EN VEILLE";
}

const fmtHeure = (d) => d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
const fmtJour = (d) => d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
const nomExpediteur = (de) => (de.replace(/<.*?>/g, "").replace(/"/g, "").trim() || de);

// ---------------------------------------------------------------------------
// Animation du noyau : niveau sonore -> taille du cœur et barres
// ---------------------------------------------------------------------------
const NB_BARRES = 64;
const barres = [];
(function creerBarres() {
  const g = $("barres");
  for (let i = 0; i < NB_BARRES; i++) {
    const a = (i / NB_BARRES) * Math.PI * 2;
    const l = document.createElementNS("http://www.w3.org/2000/svg", "line");
    g.append(l); barres.push({ l, a });
  }
})();

let niveau = 0, niveauCible = 0, analyseur = null, tampon = null;
function animer(t) {
  if (analyseur) {
    analyseur.getByteFrequencyData(tampon);
    niveauCible = tampon.reduce((s, v) => s + v, 0) / tampon.length / 140;
  } else if ($("noyau").classList.contains("parle")) {
    niveauCible = 0.35 + 0.35 * Math.abs(Math.sin(t / 90)) * Math.random();
  } else {
    niveauCible = 0.04 + 0.03 * Math.sin(t / 700);
  }
  niveau += (niveauCible - niveau) * 0.25;
  $("coeur").setAttribute("r", 62 + niveau * 26);
  barres.forEach(({ l, a }, i) => {
    const v = analyseur ? tampon[i % tampon.length] / 255 : niveau * (0.5 + 0.5 * Math.sin(i * 1.7 + t / 120));
    const r1 = 116, r2 = r1 + 4 + v * 26;
    l.setAttribute("x1", 200 + Math.cos(a) * r1); l.setAttribute("y1", 200 + Math.sin(a) * r1);
    l.setAttribute("x2", 200 + Math.cos(a) * r2); l.setAttribute("y2", 200 + Math.sin(a) * r2);
  });
  requestAnimationFrame(animer);
}
requestAnimationFrame(animer);

// ---------------------------------------------------------------------------
// Voix (synthèse) : ElevenLabs si configuré, sinon voix du navigateur
// ---------------------------------------------------------------------------
const PRENOMS_GRAVES = ["thomas", "paul", "henri", "claude", "mathieu", "nicolas", "daniel", "antoine",
                        "gerard", "jean", "olivier", "remy", "vincent", "denis", "guillaume", "male", "homme"];
let voixDispo = [];
let audioCourant = null, ctxAudio = null;

function chargerVoix() {
  voixDispo = speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("fr"));
  const sel = $("r-voix");
  sel.replaceChildren(...voixDispo.map((v) => el("option", { value: v.name }, `${v.name} (${v.lang})`)));
  const memo = lireReglage("voix", null);
  const score = (v) => (PRENOMS_GRAVES.some((p) => v.name.toLowerCase().includes(p)) ? 2 : 0) + (v.localService ? 0 : 1);
  const choisie = voixDispo.find((v) => v.name === memo) || [...voixDispo].sort((a, b) => score(b) - score(a))[0];
  if (choisie) sel.value = choisie.name;
  $("r-note").textContent = voixDispo.length
    ? "Astuce : choisissez une voix masculine et baissez un peu la hauteur pour un ton de majordome."
    : "Aucune voix française trouvée dans ce navigateur : installez-en une dans les réglages du système.";
}
if ("speechSynthesis" in window) { chargerVoix(); speechSynthesis.onvoiceschanged = chargerVoix; }

function stopParole() {
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  if (audioCourant) { audioCourant.pause(); audioCourant = null; }
  analyseur = null; etat(null);
}

// Filtre « IA » : voix un peu plus dense et métallique, avec un léger écho de cockpit.
function chaineEffetIA(ctx, entree, sortie) {
  const passeHaut = ctx.createBiquadFilter(); passeHaut.type = "highpass"; passeHaut.frequency.value = 110;
  const presence = ctx.createBiquadFilter(); presence.type = "peaking"; presence.frequency.value = 2800; presence.Q.value = 0.9; presence.gain.value = 4;
  const air = ctx.createBiquadFilter(); air.type = "highshelf"; air.frequency.value = 7000; air.gain.value = 2;
  const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -22; comp.ratio.value = 3.5; comp.attack.value = 0.004; comp.release.value = 0.2;
  const sec = ctx.createGain(); sec.gain.value = 0.9;
  // Doublage très court (effet « synthétique ») + petit écho
  const doublage = ctx.createDelay(0.1); doublage.delayTime.value = 0.011;
  const gDoublage = ctx.createGain(); gDoublage.gain.value = 0.28;
  const echo = ctx.createDelay(1); echo.delayTime.value = 0.085;
  const gEcho = ctx.createGain(); gEcho.gain.value = 0.12;
  const retour = ctx.createGain(); retour.gain.value = 0.18;
  entree.connect(passeHaut).connect(presence).connect(air).connect(comp);
  comp.connect(sec).connect(sortie);
  comp.connect(doublage).connect(gDoublage).connect(sortie);
  comp.connect(echo).connect(gEcho).connect(sortie);
  echo.connect(retour).connect(echo);
}

let alerteVoix = false;
async function parlerPremium(texte) {
  const rep = await fetch("/api/voix", { method: "POST", headers: { "Content-Type": "application/json" },
                                          body: JSON.stringify({ texte }) });
  if (!rep.ok) {
    const err = await rep.json().catch(() => ({}));
    if (!alerteVoix) { bandeau(err.erreur || "Voix ElevenLabs indisponible.", true); alerteVoix = true; }
    throw new Error("voix premium indisponible");
  }
  const url = URL.createObjectURL(await rep.blob());
  const audio = new Audio(url);
  audioCourant = audio;
  try {
    ctxAudio ||= new AudioContext();
    if (ctxAudio.state === "suspended") await ctxAudio.resume();
    const src = ctxAudio.createMediaElementSource(audio);
    analyseur = ctxAudio.createAnalyser(); analyseur.fftSize = 128;
    tampon = new Uint8Array(analyseur.frequencyBinCount);
    if ($("r-effet").checked) chaineEffetIA(ctxAudio, src, analyseur);
    else src.connect(analyseur);
    analyseur.connect(ctxAudio.destination);
  } catch { analyseur = null; }
  await new Promise((ok) => { audio.onended = audio.onerror = ok; audio.play().catch(ok); });
  URL.revokeObjectURL(url); analyseur = null;
}

function parlerNavigateur(texte) {
  return new Promise((ok) => {
    if (!("speechSynthesis" in window)) return ok();
    const u = new SpeechSynthesisUtterance(texte);
    const v = voixDispo.find((x) => x.name === $("r-voix").value);
    if (v) u.voice = v;
    u.lang = v?.lang || "fr-FR";
    u.pitch = Number($("r-hauteur").value);
    u.rate = Number($("r-debit").value);
    // Filet de sécurité : certains navigateurs n'émettent jamais « onend ».
    const garde = setTimeout(ok, 4000 + texte.length * 90 / u.rate);
    u.onend = u.onerror = () => { clearTimeout(garde); ok(); };
    speechSynthesis.speak(u);
  });
}

async function dire(texte) {
  if (!texte) return;
  stopParole();
  $("sous-titre").textContent = texte;
  S.historique.push({ role: "assistant", texte });
  pauseEcoute(true);
  etat("parle");
  try {
    if (S.voixPremium && $("r-premium").checked) await parlerPremium(texte);
    else await parlerNavigateur(texte);
  } catch {
    await parlerNavigateur(texte);
  } finally {
    etat(null);
    pauseEcoute(false);
  }
}

// ---------------------------------------------------------------------------
// Micro (reconnaissance vocale du navigateur)
// ---------------------------------------------------------------------------
const Reco = window.SpeechRecognition || window.webkitSpeechRecognition;
let reco = null, ecouteActive = false, enPause = false;

function initReco() {
  if (!Reco) { $("v-micro").title = "Pas de reconnaissance vocale dans ce navigateur : écoute via ElevenLabs si configurée"; return; }
  reco = new Reco();
  reco.lang = "fr-FR";
  reco.interimResults = true;
  reco.onresult = (e) => {
    let final = "", provisoire = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      (r.isFinal ? (final += r[0].transcript) : (provisoire += r[0].transcript));
    }
    $("entendu").textContent = (final || provisoire).trim();
    if (final.trim()) surPhrase(final.trim());
  };
  reco.onend = () => {
    $("btn-micro").classList.remove("actif"); $("v-micro").classList.remove("actif");
    if ($("noyau").classList.contains("ecoute")) etat(null);
    ecouteActive = false;
    if ($("r-ecoute").checked && !enPause) setTimeout(() => demarrerEcoute(), 300);
  };
  reco.onerror = (e) => {
    // Safari refuse souvent (Siri/Dictée désactivés) : on bascule sur l'écoute ElevenLabs si elle existe.
    if ((e.error === "service-not-allowed" || e.error === "network" || e.error === "language-not-supported") && S.ecouteServeur) {
      reco = null;
      bandeau("Reconnaissance du navigateur indisponible : j'utilise l'écoute ElevenLabs. Recliquez pour parler.");
    } else if (e.error === "not-allowed" || e.error === "service-not-allowed") {
      bandeau("Accès au micro refusé : autorisez-le dans les réglages du navigateur pour ce site.", true);
    }
  };
}

// ---------------------------------------------------------------------------
// Écoute par enregistrement (Firefox, Safari sans Dictée) : transcription ElevenLabs
// ---------------------------------------------------------------------------
let enregistreur = null;
async function enregistrer() {
  if (enregistreur) { enregistreur.stop(); return; }   // second clic : fin de la phrase
  let flux;
  try { flux = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
  catch { bandeau("Accès au micro refusé : autorisez-le dans les réglages du navigateur pour ce site.", true); return; }
  stopParole();
  const morceaux = [];
  const rec = new MediaRecorder(flux);
  enregistreur = rec;
  ecouteActive = true;
  $("btn-micro").classList.add("actif"); $("v-micro").classList.add("actif"); etat("ecoute");
  $("entendu").textContent = "…";

  // Fin automatique après ~1,3 s de silence (ou 15 s au maximum).
  const ctx = new AudioContext();
  const an = ctx.createAnalyser(); an.fftSize = 1024;
  ctx.createMediaStreamSource(flux).connect(an);
  const buf = new Float32Array(an.fftSize);
  let aParle = false, silenceDepuis = performance.now();
  const debut = performance.now();
  const veille = setInterval(() => {
    an.getFloatTimeDomainData(buf);
    const rms = Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length);
    const t = performance.now();
    if (rms > 0.025) { aParle = true; silenceDepuis = t; }
    if ((aParle && t - silenceDepuis > 1300) || t - debut > 15000 || (!aParle && t - debut > 7000)) rec.stop();
  }, 100);

  rec.ondataavailable = (e) => e.data.size && morceaux.push(e.data);
  rec.onstop = async () => {
    clearInterval(veille); flux.getTracks().forEach((p) => p.stop()); ctx.close();
    enregistreur = null; ecouteActive = false;
    $("btn-micro").classList.remove("actif"); $("v-micro").classList.remove("actif");
    if (!aParle) { etat(null); $("entendu").textContent = ""; return; }
    etat("reflexion");
    const fd = new FormData();
    const type = rec.mimeType || "audio/webm";
    fd.append("audio", new Blob(morceaux, { type }), "voix." + (type.includes("mp4") ? "mp4" : type.includes("ogg") ? "ogg" : "webm"));
    try {
      const r = await fetch("/api/ecoute", { method: "POST", body: fd });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.erreur || "Transcription impossible.");
      etat(null);
      if (j.texte) traiter(j.texte); else $("entendu").textContent = "Je n'ai rien entendu.";
    } catch (e) { etat(null); bandeau(e.message, true); }
  };
  rec.start();
}

function demarrerEcoute() {
  if (!reco) {
    if (S.ecouteServeur && navigator.mediaDevices && window.MediaRecorder) return enregistrer();
    bandeau("Ce navigateur ne sait pas écouter. Ajoutez une clé ElevenLabs (voir la notice) ou utilisez Chrome/Edge. Vous pouvez écrire vos demandes.", true);
    return;
  }
  if (ecouteActive) return;
  stopParole();
  reco.continuous = $("r-ecoute").checked;
  try { reco.start(); } catch { return; }
  ecouteActive = true;
  $("btn-micro").classList.add("actif"); $("v-micro").classList.add("actif");
  if (!$("r-ecoute").checked) etat("ecoute");
}
function arreterEcoute() {
  if (enregistreur) enregistreur.stop();
  else if (reco && ecouteActive) reco.stop();
}

function pauseEcoute(oui) {
  // Évite que l'assistant s'entende lui-même pendant qu'il parle.
  enPause = oui;
  if (oui) arreterEcoute();
  else if ($("r-ecoute").checked) demarrerEcoute();
}

function surPhrase(phrase) {
  if ($("r-ecoute").checked) {
    const nom = S.nom.toLowerCase();
    const bas = phrase.toLowerCase();
    if (/\b(stop|silence|tais-toi)\b/.test(bas)) return stopParole();
    const pos = bas.indexOf(nom);
    if (pos === -1) return;
    phrase = phrase.slice(pos + nom.length).replace(/^[\s,.!?]+/, "");
    if (!phrase) return dire(`Oui, ${S.utilisateur} ?`);
  } else {
    arreterEcoute();
  }
  traiter(phrase);
}

// ---------------------------------------------------------------------------
// Commandes
// ---------------------------------------------------------------------------
const norm = (t) => t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

async function traiter(texte) {
  texte = texte.trim();
  if (!texte) return;
  $("entendu").textContent = "« " + texte + " »";
  S.historique.push({ role: "user", texte });
  const t = norm(texte);

  if (/\b(stop|arrete|tais[- ]toi|silence|chut)\b/.test(t)) return stopParole();
  if (S.enAttente) {
    if (/\b(oui|confirme|vas[- ]y|go|d'accord|ok|valide|applique|fais[- ]le)\b/.test(t)) return confirmer(true);
    if (/\b(non|annule|laisse tomber|pas maintenant)\b/.test(t)) return confirmer(false);
  }
  const creation = /\b(ajoute|cree|planifie|note|programme un|bloque|reserve)\b/.test(t);
  if (/\b(briefing|quoi de neuf|bonjour|resume de la journee)\b/.test(t)) return briefingComplet();
  if (/\b(trie|tri|trier|range|ranger|classe|classer|nettoie|nettoyer)\b/.test(t)) return proposerTri();
  if (/\b(lis|lire|relis)\b/.test(t) && /\b(mail|message|courriel)\b/.test(t)) return lireMailDemande(t);
  if (!creation && /\b(mails?|courriers?|courriels?|messages?|boite)\b/.test(t)) return chargerMails(true);
  if (!creation && /\b(agenda|calendrier|planning|rendez[- ]vous|rdv|programme|emploi du temps)\b/.test(t)) return chargerAgenda(true);
  return demander(texte);
}

async function avecAttente(fn) {
  etat("reflexion");
  document.querySelectorAll("button").forEach((b) => b.id?.startsWith("btn-") && (b.disabled = true));
  try { return await fn(); }
  catch (e) { bandeau(e.message, true); await dire(`Désolé, ${S.utilisateur}. ${e.message}`); }
  finally {
    document.querySelectorAll("button").forEach((b) => (b.disabled = false));
    if ($("noyau").classList.contains("reflexion")) etat(null);
  }
}

async function chargerMails(parler) {
  return avecAttente(async () => {
    const d = await api("/api/mails");
    S.mails = d.mails;
    afficherMails();
    $("v-mail").classList.add("ok");
    if (parler) await dire(d.resume_oral);
    return d;
  });
}

async function chargerAgenda(parler) {
  return avecAttente(async () => {
    const d = await api("/api/agenda");
    S.evenements = d.evenements;
    afficherAgenda();
    $("v-agenda").classList.add("ok");
    if (parler) await dire(d.resume_oral);
    return d;
  });
}

async function briefingComplet() {
  const h = new Date().getHours();
  await dire(`${h < 18 ? "Bonjour" : "Bonsoir"}, ${S.utilisateur}. Voici votre point de situation.`);
  await chargerMails(true);
  await chargerAgenda(true);
}

async function demander(question) {
  return avecAttente(async () => {
    const d = await api("/api/demander", { method: "POST", body: { question, historique: S.historique.slice(-10) } });
    if (d.action === "creer_evenement" && d.evenement_titre && d.evenement_debut) {
      const debut = new Date(d.evenement_debut), fin = new Date(d.evenement_fin || debut.getTime() + 3600e3);
      demanderConfirmation(
        `Ajouter « ${d.evenement_titre} » le ${fmtJour(debut)} de ${fmtHeure(debut)} à ${fmtHeure(fin)} ?`,
        async () => {
          await api("/api/agenda", { method: "POST", body: { titre: d.evenement_titre, debut: d.evenement_debut, fin: d.evenement_fin } });
          await chargerAgenda(false);
          await dire("C'est noté dans votre agenda.");
        });
    }
    await dire(d.reponse_orale);
  });
}

// --- Lecture d'un mail ------------------------------------------------------
let indexLecture = -1;
async function lireMailDemande(t) {
  if (!S.mails.length) await chargerMails(false);
  if (!S.mails.length) return dire("Il n'y a aucun mail à lire.");
  let i;
  if (/\burgent/.test(t)) i = S.mails.findIndex((m) => m.categorie === "Urgent");
  else if (/\b(premier|1er)\b/.test(t)) i = 0;
  else if (/\b(dernier)\b/.test(t)) i = S.mails.length - 1;
  else if (/\b(precedent)\b/.test(t)) i = Math.max(0, indexLecture - 1);
  else if (/\b(meme|encore|relis|entier|complet)\b/.test(t) && indexLecture >= 0) i = indexLecture;
  else i = indexLecture + 1;
  if (i < 0) return dire("Aucun mail urgent, " + S.utilisateur + ".");
  if (i >= S.mails.length) return dire("C'était le dernier mail.");
  const enEntier = /\b(entier|complet|integral|tout)\b/.test(t);
  return lireMail(i, enEntier);
}

async function lireMail(i, enEntier = false) {
  indexLecture = i;
  const m = S.mails[i];
  document.querySelectorAll("#liste-mails li").forEach((li, j) => li.classList.toggle("lecture", j === i));
  let texte = `Mail ${i + 1} sur ${S.mails.length}, de ${nomExpediteur(m.de)}. Objet : ${m.objet}. `;
  if (enEntier) {
    const complet = await api(`/api/mails/${encodeURIComponent(m.id)}`).catch(() => null);
    texte += complet?.corps ? complet.corps.slice(0, 2000) : m.resume;
  } else {
    texte += m.resume;
  }
  await dire(texte);
}

// --- Tri --------------------------------------------------------------------
async function proposerTri() {
  if (!S.mails.length) await chargerMails(false);
  if (!S.mails.length) return dire(`Rien à trier, ${S.utilisateur}.`);
  const compte = {};
  S.mails.forEach((m) => (compte[m.categorie] = (compte[m.categorie] || 0) + 1));
  const aArchiver = S.mails.filter((m) => m.action === "archiver").length;
  const detail = Object.entries(compte).map(([c, n]) => `${n} « ${c} »`).join(", ");
  const phrase = `Je propose de ranger vos ${S.mails.length} mails ainsi : ${detail}. ` +
    (aArchiver ? `J'en archiverais ${aArchiver}. ` : "") +
    "Vous pouvez ajuster dans la liste. Dois-je appliquer le tri ?";
  demanderConfirmation(`Appliquer ce tri à ${S.mails.length} mails${aArchiver ? ` (dont ${aArchiver} archivés)` : ""} ?`, appliquerTri);
  await dire(phrase);
}

async function appliquerTri() {
  const lu = $("tri-lu").checked;
  const elements = S.mails.map((m) => ({ id: m.id, categorie: m.categorie, archiver: m.action === "archiver", marquer_lu: lu }));
  await avecAttente(async () => {
    const r = await api("/api/mails/trier", { method: "POST", body: { elements } });
    await chargerMails(false);
    await dire(`C'est fait. ${r.ranges} mail${r.ranges > 1 ? "s" : ""} rangé${r.ranges > 1 ? "s" : ""} dans vos libellés « Assistant »` +
      (r.echecs.length ? `, ${r.echecs.length} en échec.` : "."));
  });
}

// --- Confirmation -----------------------------------------------------------
function demanderConfirmation(texte, action) {
  S.enAttente = action;
  $("texte-confirmation").textContent = texte;
  $("confirmation").hidden = false;
}
async function confirmer(oui) {
  const action = S.enAttente;
  S.enAttente = null;
  $("confirmation").hidden = true;
  if (!action) return;
  if (oui) await action();
  else await dire("Très bien, je n'y touche pas.");
}

// ---------------------------------------------------------------------------
// Affichage des panneaux
// ---------------------------------------------------------------------------
function afficherMails() {
  const ul = $("liste-mails");
  $("nb-mails").textContent = S.mails.length;
  $("actions-tri").hidden = !S.mails.length;
  if (!S.mails.length) return ul.replaceChildren(el("li", { class: "vide" }, "Aucun mail non lu."));
  ul.replaceChildren(...S.mails.map((m, i) => {
    const date = m.date ? new Date(m.date) : null;
    const select = el("select", { "aria-label": "Catégorie", onchange: (e) => { m.categorie = e.target.value; afficherMails(); } },
      ...S.categories.map((c) => el("option", { value: c }, c)));
    select.value = m.categorie;
    const archive = el("input", { type: "checkbox", onchange: (e) => (m.action = e.target.checked ? "archiver" : "garder") });
    archive.checked = m.action === "archiver";
    return el("li", { class: `mail cat-${m.categorie}`, title: m.raison || "" },
      el("div", { class: "ligne1" }, el("span", {}, nomExpediteur(m.de)), el("span", {}, date ? fmtHeure(date) : "")),
      el("div", { class: "objet" }, m.objet),
      el("p", { class: "resume" }, m.resume),
      el("div", { class: "reglage" }, select, el("label", {}, archive, " archiver"),
        el("button", { class: "lire", onclick: () => lireMail(i) }, "▶ Lire")));
  }));
}

function afficherAgenda() {
  const ul = $("liste-agenda");
  $("nb-evenements").textContent = S.evenements.length;
  if (!S.evenements.length) return ul.replaceChildren(el("li", { class: "vide" }, "Aucun événement à venir."));
  const items = [];
  let jourCourant = "";
  const maintenant = new Date();
  for (const e of S.evenements) {
    const d = new Date(e.debut), f = new Date(e.fin);
    const jour = fmtJour(d);
    if (jour !== jourCourant) { items.push(el("li", { class: "jour" }, jour)); jourCourant = jour; }
    const encours = d <= maintenant && maintenant < f;
    items.push(el("li", { class: "evenement" + (encours ? " maintenant" : "") },
      el("div", { class: "quand" }, e.journee_entiere ? "Toute la journée" : `${fmtHeure(d)} – ${fmtHeure(f)}`),
      el("div", { class: "titre" }, e.titre),
      e.lieu ? el("div", { class: "lieu" }, e.lieu) : ""));
  }
  ul.replaceChildren(...items);
}

// ---------------------------------------------------------------------------
// Démarrage
// ---------------------------------------------------------------------------
function horloge() {
  const d = new Date();
  $("heure").textContent = fmtHeure(d);
  $("date").textContent = fmtJour(d);
}

function lierInterface() {
  $("btn-micro").addEventListener("click", () => (ecouteActive && !$("r-ecoute").checked ? arreterEcoute() : demarrerEcoute()));
  $("noyau").addEventListener("click", () => ($("noyau").classList.contains("parle") ? stopParole() : demarrerEcoute()));
  $("noyau").addEventListener("keydown", (e) => { if (e.key === "Enter") demarrerEcoute(); });
  $("saisie").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("question").value; $("question").value = ""; traiter(q);
  });
  document.querySelectorAll(".puce").forEach((b) => b.addEventListener("click", () => traiter(b.dataset.cmd)));
  $("btn-mails").addEventListener("click", () => chargerMails(true));
  $("btn-agenda").addEventListener("click", () => chargerAgenda(true));
  $("btn-trier").addEventListener("click", proposerTri);
  $("btn-oui").addEventListener("click", () => confirmer(true));
  $("btn-non").addEventListener("click", () => confirmer(false));

  // Espace maintenu = parler (hors zone de saisie)
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space" && !e.repeat && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "SELECT") {
      e.preventDefault(); demarrerEcoute();
    }
    if (e.key === "Escape") stopParole();
  });
  document.addEventListener("keyup", (e) => {
    if (e.code === "Space" && document.activeElement.tagName !== "INPUT" && !$("r-ecoute").checked) setTimeout(arreterEcoute, 400);
  });

  // Réglages
  $("r-hauteur").value = lireReglage("hauteur", 0.8);
  $("r-debit").value = lireReglage("debit", 0.95);
  $("r-premium").checked = lireReglage("premium", true);
  $("r-effet").checked = lireReglage("effet", true);
  $("r-effet").addEventListener("change", (e) => ecrireReglage("effet", e.target.checked));
  $("r-ecoute").checked = lireReglage("ecoute", false);
  $("btn-reglages").addEventListener("click", () => ($("reglages").hidden = !$("reglages").hidden));
  $("r-fermer").addEventListener("click", () => ($("reglages").hidden = true));
  $("r-voix").addEventListener("change", (e) => ecrireReglage("voix", e.target.value));
  $("r-hauteur").addEventListener("change", (e) => ecrireReglage("hauteur", Number(e.target.value)));
  $("r-debit").addEventListener("change", (e) => ecrireReglage("debit", Number(e.target.value)));
  $("r-premium").addEventListener("change", (e) => ecrireReglage("premium", e.target.checked));
  $("r-ecoute").addEventListener("change", (e) => {
    ecrireReglage("ecoute", e.target.checked);
    if (e.target.checked) { demarrerEcoute(); bandeau(`Écoute permanente : commencez vos phrases par « ${S.nom} ».`); }
    else arreterEcoute();
  });
  $("r-test").addEventListener("click", () => dire(`Bonjour ${S.utilisateur}. Tous les systèmes sont opérationnels.`));
}

async function demarrer() {
  horloge(); setInterval(horloge, 10_000);
  lierInterface();
  initReco();
  try {
    const e = await api("/api/etat");
    Object.assign(S, { nom: e.nom, utilisateur: e.utilisateur, categories: e.categories, voixPremium: e.voix_premium,
                       ecouteServeur: e.ecoute_serveur });
    $("nom").textContent = e.nom.toUpperCase();
    document.title = `${e.nom} — assistant`;
    $("v-ia").classList.add(e.ia ? "ok" : "demo");
    $("v-ia").title = e.ia ? "Claude connecté" : "Sans clé API : tri par mots-clés";
    if (e.demo) { $("v-mail").classList.add("demo"); $("v-agenda").classList.add("demo"); bandeau("Mode démonstration : données fictives."); }
    if (!e.voix_premium) { $("r-premium").closest("label").hidden = true; $("r-effet").closest("label").hidden = true; }
    if (!Reco) $("r-ecoute").closest("label").hidden = true;  // l'écoute permanente demande la reconnaissance du navigateur
    if (Reco || e.ecoute_serveur) $("v-micro").classList.add("ok");
    if (lireReglage("ecoute", false)) demarrerEcoute();
    $("sous-titre").textContent = `Bonjour, ${S.utilisateur}. Cliquez sur le noyau ou maintenez Espace pour me parler.`;
  } catch (err) {
    bandeau("Serveur injoignable : " + err.message, true);
  }
}
demarrer();
