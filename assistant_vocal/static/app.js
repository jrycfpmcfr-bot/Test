"use strict";

// ---------------------------------------------------------------------------
// Utilitaires
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const S = { nom: "Jarvis", utilisateur: "Monsieur", categories: [], mails: [], evenements: [],
            historique: [], enAttente: null, voixPremium: false, ecouteServeur: false, agendaModifiable: true,
            consigneMail: null, conversationJusqua: 0 };

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
function bandeau(texte, erreur = false, lien = null) {
  const b = $("bandeau");
  b.replaceChildren(texte);
  if (lien) b.append(" ", el("a", { href: lien, target: "_blank", rel: "noopener noreferrer" }, "Ouvrir la page"));
  b.className = "bandeau" + (erreur ? " erreur" : ""); b.hidden = false;
  clearTimeout(minuteurBandeau);
  minuteurBandeau = setTimeout(() => (b.hidden = true), lien ? 15000 : 6000);
}

// ---------------------------------------------------------------------------
// Audio partagé : déverrouillé au premier toucher (obligatoire sur iPhone)
// ---------------------------------------------------------------------------
let ctxPartage = null;
function audioCtx() {
  if (!ctxPartage) { const C = window.AudioContext || window.webkitAudioContext; ctxPartage = new C(); }
  if (ctxPartage.state === "suspended") ctxPartage.resume().catch(() => {});
  return ctxPartage;
}
let allume = false;
function allumage() {
  if (allume) return;
  allume = true;
  try {
    const c = audioCtx();
    const b = c.createBuffer(1, 1, 22050), s0 = c.createBufferSource();  // son vide : déverrouille iOS
    s0.buffer = b; s0.connect(c.destination); s0.start(0);
  } catch {}
  $("noyau").classList.add("demarrage");
  setTimeout(() => $("noyau").classList.remove("demarrage"), 1700);
  bip("allumage");
}
["pointerdown", "keydown", "touchend"].forEach((t) => document.addEventListener(t, allumage, { capture: true, passive: true }));

// Petits signaux sonores d'interface, générés sur place
function bip(type) {
  try {
    const c = audioCtx();
    const notes = { ecoute: [880, 1320], fin: [1320, 880], parle: [660, 990], allumage: [220, 330, 495, 990] }[type] || [660];
    notes.forEach((f, i) => {
      const o = c.createOscillator(), g = c.createGain(), t = c.currentTime + i * (type === "allumage" ? 0.12 : 0.07);
      o.type = type === "allumage" ? "triangle" : "sine"; o.frequency.value = f;
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.05, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.14);
      o.connect(g).connect(c.destination); o.start(t); o.stop(t + 0.15);
    });
  } catch {}
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
let sourceCourante = null;

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
  if (sourceCourante) { try { sourceCourante.stop(); } catch {} sourceCourante = null; }
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
  const c = audioCtx();
  const donnees = await rep.arrayBuffer();
  const tamponAudio = await new Promise((ok, ko) => c.decodeAudioData(donnees, ok, ko));
  const src = c.createBufferSource();
  src.buffer = tamponAudio;
  sourceCourante = src;
  analyseur = c.createAnalyser(); analyseur.fftSize = 128;
  tampon = new Uint8Array(analyseur.frequencyBinCount);
  if ($("r-effet").checked) chaineEffetIA(c, src, analyseur);
  else src.connect(analyseur);
  analyseur.connect(c.destination);
  await new Promise((ok) => { src.onended = ok; src.start(0); });
  if (sourceCourante === src) sourceCourante = null;
  analyseur = null;
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
  bip("parle");
  try {
    if (S.voixPremium && $("r-premium").checked) await parlerPremium(texte);
    else await parlerNavigateur(texte);
  } catch {
    await parlerNavigateur(texte);
  } finally {
    etat(null);
    if ($("r-ecoute").checked && !S.finConversation) S.conversationJusqua = Date.now() + 9000;  // réponse possible sans redire le nom
    S.finConversation = false;
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
    if (capture) return;
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
    } else if (e.error === "audio-capture") {
      bandeau("Aucun micro détecté : vérifiez qu'il est branché et choisi dans les réglages du système.", true);
    } else if (e.error === "network") {
      bandeau("La reconnaissance vocale du navigateur n'arrive pas à joindre son service. Ajoutez une clé ElevenLabs pour l'écoute.", true);
    } else if (e.error !== "no-speech" && e.error !== "aborted") {
      bandeau("Micro : erreur « " + e.error + " ».", true);
    }
  };
}

// ---------------------------------------------------------------------------
// Écoute par le micro + transcription ElevenLabs : marche partout (iPhone, Android,
// Safari, Firefox). Le son est capté en continu, découpé en phrases par détection
// de silence, puis envoyé en WAV. Un peu de son avant la phrase est gardé pour ne
// pas couper le premier mot (« Jarvis… »).
// ---------------------------------------------------------------------------
let micro = null;    // { flux, src, proc }
let capture = null;  // { mode: "unique" | "continu", etat, morceaux, silence, debut, preRoll, bruit }

async function ouvrirMicro() {
  if (micro) return micro;
  const flux = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  const c = audioCtx();
  const src = c.createMediaStreamSource(flux);
  const proc = c.createScriptProcessor(4096, 1, 1);
  const muet = c.createGain(); muet.gain.value = 0;
  src.connect(proc); proc.connect(muet).connect(c.destination);
  proc.onaudioprocess = (e) => blocAudio(new Float32Array(e.inputBuffer.getChannelData(0)), c.sampleRate);
  micro = { flux, src, proc };
  return micro;
}

function fermerMicro() {
  if (!micro) return;
  try { micro.proc.disconnect(); micro.src.disconnect(); } catch {}
  micro.flux.getTracks().forEach((p) => p.stop());
  micro = null;
}

function voyantsEcoute(actif) {
  ecouteActive = actif;
  $("btn-micro").classList.toggle("actif", actif); $("v-micro").classList.toggle("actif", actif);
}

function blocAudio(bloc, frequence) {
  if (!capture) return;
  const occupe = $("noyau").classList.contains("parle");
  if (capture.mode === "continu" && occupe) { capture.etat = "attente"; capture.preRoll = []; return; }  // il ne s'écoute pas lui-même
  const rms = Math.sqrt(bloc.reduce((s, v) => s + v * v, 0) / bloc.length);
  const dureeBloc = bloc.length / frequence * 1000;
  const seuil = Math.max(0.018, capture.bruit * 3);
  if (capture.etat === "attente") {
    capture.bruit = capture.bruit * 0.95 + rms * 0.05;
    capture.preRoll.push(bloc);
    if (capture.preRoll.length > 5) capture.preRoll.shift();
    if (rms > seuil) {
      capture.etat = "parole"; capture.morceaux = [...capture.preRoll, bloc]; capture.silence = 0; capture.debutParole = performance.now();
      capture.somme = 0; capture.nb = 0;
      if (capture.mode === "continu") etat("ecoute");
    } else if (capture.mode === "unique" && performance.now() - capture.debut > 7000) {
      finEcoute(false);  // personne n'a parlé
    }
    return;
  }
  capture.morceaux.push(bloc);
  capture.somme += rms; capture.nb++;
  capture.silence = rms > seuil ? 0 : capture.silence + dureeBloc;
  if (capture.silence > 1100) return finPhrase(frequence);
  if (performance.now() - capture.debutParole > 15000) {
    // 15 s sans pause : sans doute un bruit de fond constant (télé, ventilation) -> on relève le seuil
    capture.bruit = Math.max(capture.bruit, capture.somme / capture.nb);
    finPhrase(frequence);
  }
}

function finPhrase(frequence) {
  const morceaux = capture.morceaux;
  const mode = capture.mode;
  if (mode === "unique") finEcoute(false);
  else { capture.etat = "attente"; capture.morceaux = []; capture.preRoll = []; etat(null); }
  envoyerPhrase(wav(morceaux, frequence || audioCtx().sampleRate), mode);
}

function finEcoute(envoyer = true) {
  if (!capture) return;
  if (envoyer && capture.etat === "parole") return finPhrase();
  capture = null;
  fermerMicro();
  voyantsEcoute(false);
  if ($("noyau").classList.contains("ecoute")) etat(null);
  bip("fin");
}

async function envoyerPhrase(blob, mode) {
  if (mode === "unique") etat("reflexion");
  const fd = new FormData();
  fd.append("audio", blob, "voix.wav");
  try {
    const r = await fetch("/api/ecoute", { method: "POST", body: fd });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.erreur || "Transcription impossible.");
    if ($("noyau").classList.contains("reflexion")) etat(null);
    if (!j.texte) { if (mode === "unique") $("entendu").textContent = "Je n'ai rien entendu."; return; }
    if (mode === "continu") surPhrase(j.texte); else traiter(j.texte);
  } catch (e) { etat(null); bandeau(e.message, true); }
}

// Assemble les blocs en WAV 16 kHz mono (léger à envoyer, accepté partout)
function wav(morceaux, frequence) {
  const total = morceaux.reduce((n, m) => n + m.length, 0);
  const brut = new Float32Array(total);
  let o = 0; for (const m of morceaux) { brut.set(m, o); o += m.length; }
  const cible = 16000, pas = frequence / cible, n = Math.floor(total / pas);
  const pcm = new Int16Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * pas), b = Math.min(total, Math.floor((i + 1) * pas));
    let s = 0; for (let j = a; j < b; j++) s += brut[j];
    const v = Math.max(-1, Math.min(1, s / Math.max(1, b - a)));
    pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  const tampon = new ArrayBuffer(44 + pcm.length * 2), d = new DataView(tampon);
  const ecr = (p, t) => [...t].forEach((c, i) => d.setUint8(p + i, c.charCodeAt(0)));
  ecr(0, "RIFF"); d.setUint32(4, 36 + pcm.length * 2, true); ecr(8, "WAVE"); ecr(12, "fmt ");
  d.setUint32(16, 16, true); d.setUint16(20, 1, true); d.setUint16(22, 1, true); d.setUint32(24, cible, true);
  d.setUint32(28, cible * 2, true); d.setUint16(32, 2, true); d.setUint16(34, 16, true); ecr(36, "data");
  d.setUint32(40, pcm.length * 2, true);
  new Int16Array(tampon, 44).set(pcm);
  return new Blob([tampon], { type: "audio/wav" });
}

async function ecouteServeur(mode) {
  if (capture) { if (mode === "unique") finEcoute(true); return; }  // second clic : fin de la phrase
  stopParole();
  try { await ouvrirMicro(); }
  catch (e) {
    const msg = e?.name === "NotAllowedError" ? "Accès au micro refusé : autorisez-le dans les réglages du navigateur pour ce site."
      : e?.name === "NotFoundError" ? "Aucun micro détecté sur cet appareil."
      : !window.isSecureContext ? "Le micro demande une adresse sécurisée (https) : sur téléphone, passez par Tailscale (voir la notice)."
      : "Micro indisponible : " + (e?.message || e);
    bandeau(msg, true); return;
  }
  capture = { mode, etat: "attente", morceaux: [], preRoll: [], silence: 0, debut: performance.now(), bruit: 0.005 };
  voyantsEcoute(true);
  bip("ecoute");
  if (mode === "unique") { etat("ecoute"); $("entendu").textContent = "…"; }
}

function demarrerEcoute() {
  const serveurPossible = S.ecouteServeur && navigator.mediaDevices?.getUserMedia;
  const mainsLibres = $("r-ecoute").checked;
  if (serveurPossible && !(mainsLibres && reco && !S.preferServeur)) return ecouteServeur(mainsLibres ? "continu" : "unique");
  if (!reco) {
    bandeau(!window.isSecureContext
      ? "Le micro demande une adresse sécurisée (https) : sur téléphone, passez par Tailscale (voir la notice)."
      : "Ce navigateur ne sait pas écouter seul. Ajoutez une clé ElevenLabs dans les Réglages pour activer le micro partout.", true);
    return;
  }
  if (ecouteActive) return;
  stopParole();
  reco.continuous = mainsLibres;
  try { reco.start(); } catch { return; }
  voyantsEcoute(true);
  bip("ecoute");
  if (!mainsLibres) etat("ecoute");
}
function arreterEcoute() {
  if (capture) return finEcoute(capture.mode === "unique");
  if (reco && ecouteActive) reco.stop();
}

function pauseEcoute(oui) {
  // Évite que l'assistant s'entende lui-même pendant qu'il parle.
  if (capture?.mode === "continu") return;  // la capture continue ignore déjà sa propre voix
  enPause = oui;
  if (oui) arreterEcoute();
  else if ($("r-ecoute").checked) demarrerEcoute();
}

function surPhrase(phrase) {
  if ($("r-ecoute").checked) {
    const bas = phrase.toLowerCase();
    if (/\b(stop|silence|tais-toi)\b/.test(bas)) return stopParole();
    const enConversation = Date.now() < S.conversationJusqua;
    if (enConversation && /\b(merci|c'est tout|ce sera tout|fin de la conversation)\b/.test(bas)) {
      S.conversationJusqua = 0; S.finConversation = true;
      return dire(`À votre service, ${S.utilisateur}.`);
    }
    const nom = S.nom.toLowerCase();
    const pos = bas.indexOf(nom);
    if (pos === -1) { if (!enConversation) return; }
    else phrase = phrase.slice(pos + nom.length).replace(/^[\s,.!?]+/, "");
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
  if (S.consigneMail) { const id = S.consigneMail; S.consigneMail = null; $("question").placeholder = "Parlez, ou écrivez une demande…"; return preparerReponse(id, texte); }
  if (S.enAttente) {
    if (/\b(oui|confirme|vas[- ]y|go|d'accord|ok|valide|applique|fais[- ]le|envoie|envoyer|envoie[- ]le)\b/.test(t)) return confirmer(true);
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
    if (d.avertissement) bandeau(d.avertissement, true);
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
    if (d.action === "repondre_mail" && d.mail_id && d.texte_mail) proposerEnvoi(d.mail_id, d.texte_mail);
    if (d.action === "desabonner" && d.mail_id) {
      const m = S.mails.find((x) => x.id === d.mail_id);
      if (m) demanderConfirmation(`Me désabonner de « ${nomExpediteur(m.de)} » ?`, () => desabonner(m));
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
    await dire(`C'est fait. ${r.ranges} mail${r.ranges > 1 ? "s" : ""} rangé${r.ranges > 1 ? "s" : ""}` +
      (r.echecs.length ? `, ${r.echecs.length} en échec.` : ".") +
      (r.appris ? ` J'ai retenu vos ${r.appris > 1 ? r.appris + " corrections" : "corrections"} pour la prochaine fois.` : ""));
  });
}

// --- Confirmation -----------------------------------------------------------
function demanderConfirmation(texte, action, brouillon = null, libelle = "Confirmer") {
  S.enAttente = action;
  $("texte-confirmation").textContent = texte;
  $("brouillon").hidden = brouillon === null;
  if (brouillon !== null) $("brouillon").value = brouillon;
  $("btn-oui").textContent = libelle;
  $("confirmation").hidden = false;
}
async function confirmer(oui) {
  const action = S.enAttente;
  S.enAttente = null;
  $("confirmation").hidden = true;
  if (!action) return;
  if (oui) await action($("brouillon").value);
  else await dire("Très bien, je n'y touche pas.");
}

// --- Réponses aux mails -------------------------------------------------------
function demanderConsigne(m) {
  S.consigneMail = m.id;
  $("question").placeholder = `Que dois-je répondre à ${nomExpediteur(m.de)} ?`;
  $("question").focus();
  dire(`Que dois-je répondre à ${nomExpediteur(m.de)} ?`).then(() => { if (S.ecouteServeur || reco) demarrerEcoute(); });
}

async function preparerReponse(id, consigne) {
  await avecAttente(async () => {
    const d = await api(`/api/mails/${encodeURIComponent(id)}/brouillon`, { method: "POST", body: { consigne } });
    proposerEnvoi(id, d.texte);
    await dire(`Voici ma proposition. ${d.texte} Dois-je l'envoyer ?`);
  });
}

function proposerEnvoi(id, texte) {
  const m = S.mails.find((x) => x.id === id);
  if (!m) return;
  demanderConfirmation(`Réponse à ${nomExpediteur(m.de)} — vous pouvez la modifier avant l'envoi :`, async (final) => {
    await avecAttente(async () => {
      await api(`/api/mails/${encodeURIComponent(id)}/repondre`, { method: "POST", body: { texte: final } });
      await dire("Réponse envoyée.");
    });
  }, texte, "Envoyer");
}

async function desabonner(m) {
  await avecAttente(async () => {
    const r = await api(`/api/mails/${encodeURIComponent(m.id)}/desabonner`, { method: "POST" });
    if (r.fait) await dire(`C'est fait, vous ne devriez plus recevoir les envois de ${nomExpediteur(m.de)}.`);
    else { bandeau("Cet expéditeur demande de confirmer sur sa page :", false, r.lien); await dire("Il faut confirmer sur leur page : j'affiche le lien."); }
  });
}

async function basculerPrioritaire(m) {
  try {
    const r = await api(`/api/mails/${encodeURIComponent(m.id)}/prioritaire`, { method: "POST" });
    S.mails.filter((x) => x.de === m.de).forEach((x) => (x.prioritaire = r.prioritaire));
    S.mails.sort((a, b) => (b.prioritaire ? 1 : 0) - (a.prioritaire ? 1 : 0));
    afficherMails();
    bandeau(r.prioritaire ? `${nomExpediteur(m.de)} passe en contact prioritaire.` : `${nomExpediteur(m.de)} n'est plus prioritaire.`);
  } catch (e) { bandeau(e.message, true); }
}

function ajouterEvenementDuMail(m) {
  const ev = m.evenement;
  if (!S.agendaModifiable) return bandeau("Votre agenda est en lecture seule (lien secret) : activez l'accès Google complet pour ajouter des rendez-vous.", true);
  const debut = new Date(ev.debut), fin = ev.fin ? new Date(ev.fin) : new Date(debut.getTime() + 3600e3);
  demanderConfirmation(`Ajouter « ${ev.titre} » le ${fmtJour(debut)} de ${fmtHeure(debut)} à ${fmtHeure(fin)} ?`, async () => {
    await avecAttente(async () => {
      await api("/api/agenda", { method: "POST", body: { titre: ev.titre, debut: ev.debut, fin: ev.fin || new Date(fin.getTime() - fin.getTimezoneOffset() * 60e3).toISOString().slice(0, 19) } });
      await chargerAgenda(false);
      await dire("C'est noté dans votre agenda.");
    });
  });
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
    const outils = el("div", { class: "outils" },
      el("button", { onclick: () => demanderConsigne(m) }, "Répondre"));
    if (m.evenement) outils.append(el("button", { onclick: () => ajouterEvenementDuMail(m), title: m.evenement.titre }, "+ Agenda"));
    if (m.desabonnable) outils.append(el("button", { onclick: () => demanderConfirmation(`Me désabonner de « ${nomExpediteur(m.de)} » ?`, () => desabonner(m)) }, "Se désabonner"));
    return el("li", { class: `mail cat-${m.categorie}` + (m.prioritaire ? " prioritaire" : ""), title: m.raison || "" },
      el("div", { class: "ligne1" }, el("span", {},
        el("button", { class: "etoile" + (m.prioritaire ? " on" : ""), title: "Contact prioritaire", "aria-label": "Contact prioritaire", "aria-pressed": String(!!m.prioritaire), onclick: () => basculerPrioritaire(m) }, "★"),
        " ", nomExpediteur(m.de)),
        el("span", {}, (m.boite ? { icloud: "iCloud · ", gmail: "Gmail · " }[m.boite] || "" : "") + (date ? fmtHeure(date) : ""))),
      el("div", { class: "objet" }, m.objet),
      el("p", { class: "resume" }, m.resume),
      el("div", { class: "reglage" }, select, el("label", {}, archive, " archiver"),
        el("button", { class: "lire", onclick: () => lireMail(i) }, "▶ Lire")),
      outils);
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

  // Briefing programmé et rappels
  $("r-briefing").value = lireReglage("briefing", "");
  $("r-rappels").checked = lireReglage("rappels", true);
  $("r-briefing").addEventListener("change", (e) => ecrireReglage("briefing", e.target.value));
  $("r-rappels").addEventListener("change", (e) => ecrireReglage("rappels", e.target.checked));

  // Comptes et clés
  $("btn-reglages").addEventListener("click", () => { if (!$("reglages").hidden) chargerReglages(); });
  $("c-enregistrer").addEventListener("click", enregistrerReglages);
  document.querySelectorAll(".tester").forEach((b) => b.addEventListener("click", () => tester(b)));
  $("c-google-fichier").addEventListener("change", envoyerFichierGoogle);
}

// ---------------------------------------------------------------------------
// Réglages des comptes (enregistrés sur l'ordinateur, secrets jamais renvoyés)
// ---------------------------------------------------------------------------
const CHAMPS_SECRETS = ["ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "ICLOUD_MOT_DE_PASSE_APP", "GOOGLE_AGENDA_ICS", "ASSISTANT_CODE"];
const CHAMPS_CLAIRS = ["ASSISTANT_NOM", "ASSISTANT_UTILISATEUR", "ELEVENLABS_VOICE_ID", "ICLOUD_ADRESSE"];

async function chargerReglages() {
  let r;
  try { r = await api("/api/reglages"); } catch (e) { $("c-resultat").textContent = e.message; return; }
  CHAMPS_CLAIRS.forEach((c) => ($("c-" + c).value = r.reglages[c] || ""));
  CHAMPS_SECRETS.forEach((c) => { const i = $("c-" + c); i.value = ""; i.placeholder = r.secrets[c] ? "•••••• (enregistré)" : "non renseigné"; });
  $("c-ASSISTANT_GMAIL").checked = (r.reglages.ASSISTANT_GMAIL || "1") !== "0";
  $("c-prioritaires").value = (r.prioritaires || []).join("\n");
  $("c-google-fichier").previousSibling.textContent = r.google_credentials
    ? "Accès complet : fichier Google déjà déposé (en choisir un autre pour le remplacer) "
    : "Ou accès complet : fichier d'identifiants Google ";
  $("r-rangement").textContent = r.rangement === "trousseau"
    ? "Les clés et mots de passe sont rangés dans le Trousseau de l'ordinateur."
    : "Les clés sont rangées dans ~/.assistant_vocal/.env, lisible par vous seul.";
}

async function enregistrerReglages() {
  const valeurs = {};
  CHAMPS_CLAIRS.forEach((c) => (valeurs[c] = $("c-" + c).value.trim()));
  CHAMPS_SECRETS.forEach((c) => { const v = $("c-" + c).value.trim(); if (v) valeurs[c] = v; });
  valeurs.ASSISTANT_GMAIL = $("c-ASSISTANT_GMAIL").checked ? "1" : "0";
  const prioritaires = $("c-prioritaires").value.split(/[\s,;]+/).filter((x) => x.includes("@"));
  $("c-resultat").textContent = "Enregistrement…";
  try {
    const r = await api("/api/reglages", { method: "POST", body: { valeurs, prioritaires } });
    $("c-resultat").textContent = r.demo ? "Enregistré. Aucune boîte ni agenda encore branché : je reste en mode démo."
                                         : "Enregistré et appliqué.";
    if (valeurs.ASSISTANT_CODE) $("c-resultat").textContent += " Le code d'accès est actif.";
    const e = await api("/api/etat"); appliquerEtat(e);
    chargerReglages();
  } catch (e) { $("c-resultat").textContent = e.message; }
}

async function tester(bouton) {
  const ancien = bouton.textContent;
  bouton.disabled = true; bouton.textContent = "Test…";
  let sortie = bouton.nextElementSibling?.classList?.contains("resultat-test") ? bouton.nextElementSibling : null;
  if (!sortie) { sortie = el("p", { class: "note resultat-test" }); (bouton.closest(".ligne-boutons") || bouton).after(sortie); }
  if (bouton.dataset.service === "google") sortie.textContent = "Une page Google s'ouvre sur l'ordinateur où tourne Jarvis…";
  try {
    const r = await api(`/api/reglages/tester/${bouton.dataset.service}`, { method: "POST" });
    sortie.textContent = r.message; sortie.className = "note resultat-test " + (r.ok ? "ok-test" : "ko-test");
  } catch (e) { sortie.textContent = e.message; sortie.className = "note resultat-test ko-test"; }
  bouton.disabled = false; bouton.textContent = ancien;
}

async function envoyerFichierGoogle(e) {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData(); fd.append("fichier", f);
  const r = await fetch("/api/reglages/google", { method: "POST", body: fd });
  const j = await r.json().catch(() => ({}));
  $("c-resultat").textContent = r.ok ? "Fichier Google enregistré. Cliquez sur « Autoriser Google »." : (j.erreur || "Fichier refusé.");
  e.target.value = "";
}

// ---------------------------------------------------------------------------
// Briefing programmé et rappels de rendez-vous (tant que la page est ouverte)
// ---------------------------------------------------------------------------
const rappelsFaits = new Set();
async function veilleQuotidienne() {
  const maintenant = new Date();
  const hm = `${String(maintenant.getHours()).padStart(2, "0")}:${String(maintenant.getMinutes()).padStart(2, "0")}`;
  const jour = maintenant.toDateString();
  const heure = $("r-briefing").value;
  if (heure && hm === heure && lireReglage("briefingFait", "") !== jour && !$("noyau").classList.contains("parle")) {
    ecrireReglage("briefingFait", jour);
    briefingComplet();
    return;
  }
  if (!$("r-rappels").checked) return;
  for (const e of S.evenements) {
    if (e.journee_entiere) continue;
    const debut = new Date(e.debut), minutes = (debut - maintenant) / 60000;
    const cle = e.id + e.debut;
    if (minutes > 0 && minutes <= 15 && !rappelsFaits.has(cle)) {
      rappelsFaits.add(cle);
      bandeau(`Rappel : ${e.titre} à ${fmtHeure(debut)}`);
      if (!$("noyau").classList.contains("parle")) dire(`${S.utilisateur}, rappel : ${e.titre} dans ${Math.max(1, Math.round(minutes))} minutes.`);
    }
  }
}
setInterval(veilleQuotidienne, 30_000);
setInterval(() => { if (S.evenements.length || $("r-rappels").checked) api("/api/agenda").then((d) => { S.evenements = d.evenements; afficherAgenda(); }).catch(() => {}); }, 15 * 60_000);

function appliquerEtat(e) {
  Object.assign(S, { nom: e.nom, utilisateur: e.utilisateur, categories: e.categories, voixPremium: e.voix_premium,
                     ecouteServeur: e.ecoute_serveur, agendaModifiable: e.agenda_modifiable });
  $("nom").textContent = e.nom.toUpperCase();
  document.title = e.nom;
  $("v-ia").classList.toggle("ok", e.ia); $("v-ia").classList.toggle("demo", !e.ia);
  $("v-ia").title = e.ia ? "Claude connecté" : "Sans clé Claude : tri par mots-clés";
  $("r-premium").closest("label").hidden = !e.voix_premium;
  $("r-effet").closest("label").hidden = !e.voix_premium;
  $("r-ecoute").closest("label").hidden = !(Reco || e.ecoute_serveur);
  $("v-micro").classList.toggle("ok", !!(Reco || e.ecoute_serveur));
}

function salutation() {
  const h = new Date().getHours();
  const moment = h < 5 ? "Bonne nuit" : h < 12 ? "Bonjour" : h < 18 ? "Bon après-midi" : "Bonsoir";
  const suites = ["Tous les systèmes sont opérationnels.", "Je suis à votre écoute.", "Que puis-je faire pour vous ?",
                  "Prêt quand vous l'êtes."];
  return `${moment}, ${S.utilisateur}. ${suites[Math.floor(Math.random() * suites.length)]}`;
}

async function demarrer() {
  horloge(); setInterval(horloge, 10_000);
  lierInterface();
  initReco();
  try {
    const e = await api("/api/etat");
    appliquerEtat(e);
    if (e.demo) { $("v-mail").classList.add("demo"); $("v-agenda").classList.add("demo"); bandeau("Mode démonstration : ouvrez ⚙ Réglages pour brancher vos comptes."); }
    if (lireReglage("ecoute", false)) demarrerEcoute();
    $("sous-titre").textContent = salutation() + " Touchez le noyau pour me parler.";
    api("/api/agenda").then((d) => { S.evenements = d.evenements; afficherAgenda(); $("v-agenda").classList.add("ok"); }).catch(() => {});
  } catch (err) {
    bandeau("Serveur injoignable : " + err.message, true);
  }
}
demarrer();
