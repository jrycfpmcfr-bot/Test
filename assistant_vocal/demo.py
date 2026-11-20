"""Source de données fictive : permet d'essayer l'interface sans compte Google."""

from __future__ import annotations

from datetime import datetime, timedelta


def _h(jour: int, heure: int, minute: int = 0) -> str:
    base = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return (base + timedelta(days=jour, hours=heure, minutes=minute)).isoformat()


class Demo:
    def __init__(self) -> None:
        self.mails = [
            {"id": "d1", "de": "Claire Martin <claire.martin@client-industrie.example>",
             "objet": "URGENT - validation du devis avant vendredi",
             "date": _h(0, 8, 12), "extrait": "Bonjour, pouvez-vous valider le devis n°2291 ?",
             "corps": "Bonjour, pouvez-vous valider le devis n°2291 avant vendredi midi ? "
                      "Sans retour de votre part nous perdrons le créneau de livraison. Merci, Claire."},
            {"id": "d2", "de": "Ma Banque <noreply@ma-banque.example>",
             "objet": "Votre relevé de compte est disponible",
             "date": _h(0, 7, 3), "extrait": "Votre relevé du mois est disponible dans votre espace.",
             "corps": "Votre relevé de compte du mois est disponible dans votre espace client."},
            {"id": "d3", "de": "Thomas <thomas.durand@mail.example>",
             "objet": "Dîner samedi ?", "date": _h(-1, 21, 40),
             "extrait": "Salut ! On se fait un resto samedi soir ?",
             "corps": "Salut ! On se fait un resto samedi soir avec Julie ? Dis-moi si 20h te va."},
            {"id": "d4", "de": "Boutique Mode <news@boutique-mode.example>", "objet": "-30 % sur toute la collection",
             "date": _h(-1, 10), "extrait": "Profitez de nos offres exclusives ce week-end.",
             "corps": "Profitez de -30 % sur toute la collection ce week-end seulement.",
             "desabonnement": {"https": "https://boutique-mode.example/desabo", "mailto": None, "un_clic": True}},
            {"id": "d5", "de": "Service Cloud <noreply@service-cloud.example>",
             "objet": "[Test] Nouvelle connexion à votre compte", "date": _h(-1, 9, 15),
             "extrait": "Une nouvelle connexion a été détectée depuis Chrome sur Windows.",
             "corps": "Une nouvelle connexion à votre compte a été détectée depuis Chrome sur Windows."},
        ]
        self.agenda = [
            {"id": "e1", "titre": "Réunion projet P&ID", "debut": _h(0, 10), "fin": _h(0, 11),
             "journee_entiere": False, "lieu": "Salle B", "description": ""},
            {"id": "e2", "titre": "Déjeuner avec Marc", "debut": _h(0, 12, 30), "fin": _h(0, 14),
             "journee_entiere": False, "lieu": "", "description": ""},
            {"id": "e3", "titre": "Dentiste", "debut": _h(1, 17), "fin": _h(1, 17, 45),
             "journee_entiere": False, "lieu": "", "description": ""},
        ]
        self.rangements: list[dict] = []
        self.envoyes: list[dict] = []
        self.desabonnements: list[str] = []

    def mails_non_lus(self, maximum: int) -> list[dict]:
        return [dict(m, thread_id=m["id"], libelles=["INBOX", "UNREAD"]) for m in self.mails[:maximum]]

    def ranger(self, mail_id: str, categorie: str, archiver: bool, marquer_lu: bool) -> None:
        self.rangements.append({"id": mail_id, "categorie": categorie, "archiver": archiver})
        if archiver:
            self.mails = [m for m in self.mails if m["id"] != mail_id]

    def marquer_lu(self, mail_id: str) -> None:
        pass

    def repondre(self, mail: dict, texte: str) -> None:
        self.envoyes.append({"a": mail["de"], "texte": texte})

    def desabonner(self, mail: dict) -> str:
        self.desabonnements.append(mail["id"])
        return "fait"

    def evenements(self, jours: int) -> list[dict]:
        return list(self.agenda)

    def creer_evenement(self, titre: str, debut: str, fin: str, description: str = "") -> dict:
        ev = {"id": f"e{len(self.agenda) + 1}", "titre": titre, "debut": debut, "fin": fin,
              "journee_entiere": False, "lieu": "", "description": description}
        self.agenda.append(ev)
        self.agenda.sort(key=lambda e: e["debut"])
        return ev
