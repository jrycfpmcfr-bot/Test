// Protection du site par mot de passe (Vercel Routing Middleware, gratuit).
// Identifiant et mot de passe viennent des variables d'environnement Vercel
// AUTH_USER et AUTH_PASSWORD : rien n'est écrit dans le code.
// Si elles ne sont pas définies, l'accès est refusé (jamais ouvert par défaut).

export const config = { matcher: '/:path*' };

async function sha256(text) {
  const data = new TextEncoder().encode(text);
  return new Uint8Array(await crypto.subtle.digest('SHA-256', data));
}

// Comparaison en temps constant (sur les empreintes, de longueur fixe).
async function safeEqual(a, b) {
  const [ha, hb] = await Promise.all([sha256(a), sha256(b)]);
  let diff = 0;
  for (let i = 0; i < ha.length; i++) diff |= ha[i] ^ hb[i];
  return diff === 0;
}

function unauthorized(message = 'Authentification requise') {
  return new Response(message, {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Aide-memoire defauts", charset="UTF-8"',
      'Cache-Control': 'no-store',
    },
  });
}

export default async function middleware(request) {
  const user = process.env.AUTH_USER;
  const password = process.env.AUTH_PASSWORD;
  if (!user || !password) {
    return new Response('Site non configuré : définir AUTH_USER et AUTH_PASSWORD.', { status: 503 });
  }

  const header = request.headers.get('authorization') || '';
  const [scheme, encoded] = header.split(' ');
  if (scheme !== 'Basic' || !encoded) return unauthorized();

  let decoded = '';
  try {
    decoded = new TextDecoder().decode(Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0)));
  } catch {
    return unauthorized();
  }
  const sep = decoded.indexOf(':');
  const givenUser = sep >= 0 ? decoded.slice(0, sep) : '';
  const givenPassword = sep >= 0 ? decoded.slice(sep + 1) : '';

  const okUser = await safeEqual(givenUser, user);
  const okPassword = await safeEqual(givenPassword, password);
  if (!(okUser && okPassword)) return unauthorized('Identifiants incorrects');

  // Ne rien renvoyer = laisser passer la requête vers le site statique.
  return undefined;
}
