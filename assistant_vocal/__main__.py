"""Lancement : python -m assistant_vocal"""

from __future__ import annotations

import argparse
import logging
import threading
import webbrowser

from .config import charger_config
from .serveur import creer_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="assistant_vocal", description="Assistant vocal mails + agenda")
    parser.add_argument("--demo", action="store_true", help="données fictives, sans compte Google")
    parser.add_argument("--port", type=int, help="port local (5050 par défaut)")
    parser.add_argument("--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = charger_config()
    if args.demo:
        cfg.demo = True
    if args.port:
        cfg.port = args.port
    cfg.dossier.mkdir(parents=True, exist_ok=True)

    source = None
    if not cfg.demo:
        # Première utilisation : ouvre la page de consentement Google avant de démarrer.
        from .google_services import Google
        source = Google(cfg)
        source.connecter()
    app = creer_app(cfg, source=source)

    url = f"http://127.0.0.1:{cfg.port}"
    print(f"\n  {cfg.nom} est en ligne : {url}")
    print("  Mode démo (données fictives)" if cfg.demo else "  Connecté à Gmail et Google Agenda")
    print("  IA Claude : " + ("active" if cfg.ia_active else "inactive (ANTHROPIC_API_KEY manquante)"))
    print("  Voix : " + ("ElevenLabs" if cfg.voix_premium else "synthèse du navigateur") + "\n")
    if not args.sans_navigateur:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=cfg.port, debug=False)


if __name__ == "__main__":
    main()
