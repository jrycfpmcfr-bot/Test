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
    parser.add_argument("--demo", action="store_true", help="données fictives")
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

    if cfg.hote not in ("127.0.0.1", "localhost") and not cfg.code_acces:
        print("\n  ATTENTION : Jarvis est ouvert au réseau sans code d'accès. Je reste limité à cet ordinateur.")
        print("  Choisissez un code d'accès dans les Réglages, puis relancez.\n")
        cfg.hote = "127.0.0.1"

    app = creer_app(cfg)
    url = f"http://127.0.0.1:{cfg.port}"
    print(f"\n  {cfg.nom} est en ligne : {url}")
    if cfg.demo:
        print("  Mode démo (données fictives) : ouvrez ⚙ Réglages pour brancher vos comptes.")
    print("  IA Claude : " + ("active" if cfg.ia_active else "inactive (clé Anthropic manquante)"))
    print("  Voix : " + ("ElevenLabs" if cfg.voix_premium else "synthèse du navigateur") + "\n")
    if not args.sans_navigateur:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=cfg.hote, port=cfg.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
