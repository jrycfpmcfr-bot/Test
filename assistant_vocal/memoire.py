"""Mémoire de Jarvis : ce qu'il apprend de vos corrections de tri, et vos contacts prioritaires."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

_verrou = threading.Lock()


def adresse_de(expediteur: str) -> str:
    """« Claire <claire@x.fr> » -> « claire@x.fr » (en minuscules)."""
    m = re.search(r"<([^>]+)>", expediteur or "")
    adresse = (m.group(1) if m else expediteur or "").strip().lower()
    return adresse if "@" in adresse else ""


class Memoire:
    def __init__(self, dossier: Path):
        self.fichier = Path(dossier) / "memoire.json"
        self.donnees = {"categories": {}, "prioritaires": []}
        if self.fichier.is_file():
            try:
                self.donnees.update(json.loads(self.fichier.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass

    def _sauver(self) -> None:
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.fichier.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.donnees, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.fichier)

    # --- Tri appris -----------------------------------------------------------
    def categorie_apprise(self, expediteur: str) -> str | None:
        return self.donnees["categories"].get(adresse_de(expediteur))

    def apprendre(self, expediteur: str, categorie: str) -> None:
        adresse = adresse_de(expediteur)
        if adresse:
            with _verrou:
                self.donnees["categories"][adresse] = categorie
                self._sauver()

    # --- Contacts prioritaires ------------------------------------------------
    @property
    def prioritaires(self) -> list[str]:
        return list(self.donnees["prioritaires"])

    def est_prioritaire(self, expediteur: str) -> bool:
        return adresse_de(expediteur) in self.donnees["prioritaires"]

    def basculer_prioritaire(self, expediteur: str) -> bool:
        adresse = adresse_de(expediteur)
        if not adresse:
            return False
        with _verrou:
            liste = self.donnees["prioritaires"]
            if adresse in liste:
                liste.remove(adresse)
                etat = False
            else:
                liste.append(adresse)
                etat = True
            self._sauver()
        return etat

    def definir_prioritaires(self, adresses: list[str]) -> None:
        propres = sorted({a.strip().lower() for a in adresses if "@" in a})
        with _verrou:
            self.donnees["prioritaires"] = propres
            self._sauver()
