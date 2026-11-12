"""Manda su Telegram due notifiche di PROVA (annunci finti, non comprarli!).

    python -m radar.prova_telegram

1) un super affare singolo (con foto);
2) tre annunci dello stesso venditore raggruppati in un unico messaggio,
   uno dei quali "da verificare".
Se Telegram non e' configurato (file .env), stampa i messaggi a video.
"""
from __future__ import annotations

from . import notify
from .main import analyze

IMG = "https://images.pokemontcg.io/sv3pt5/166_hires.png"

SINGLE = {"native_id": "prova:1", "title": "[PROVA] Bulbasaur IR 166/165 Pokémon 151 inglese NM",
          "url": "https://www.ebay.it/", "price": 18.0, "currency": "EUR", "shipping": 2.5,
          "image": IMG, "source": "ebay.it", "platform": "ebay",
          "seller": "venditore_prova", "seller_name": "venditore_prova", "country": "IT",
          "condition": "Ungraded"}
GROUP = [
    {"native_id": "prova:2", "title": "[PROVA] フシギダネ AR M1L 064/063 giapponese",
     "url": "https://www.vinted.it/", "price": 1.0, "currency": "EUR", "shipping": None},
    {"native_id": "prova:3", "title": "[PROVA] Charizard full art lightly played",
     "url": "https://www.vinted.it/", "price": 5.5, "currency": "EUR", "shipping": None},
    {"native_id": "prova:4", "title": "[PROVA] Lotto 20 carte pokemon full art e IR",
     "url": "https://www.vinted.it/", "price": 25.0, "currency": "EUR", "shipping": None},
]
for g in GROUP:
    g.update({"source": "vinted.it", "platform": "vinted", "seller": "123",
              "seller_name": "collezionista prova", "seller_url": "https://www.vinted.it/",
              "image": "", "country": "IT", "condition": ""})


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # emoji nella console di Windows
    single = analyze(SINGLE)
    group = [a for a in (analyze(g) for g in GROUP) if a]
    assert single and len(group) == 3, "gli annunci di prova dovrebbero essere tutti in soglia"
    if not notify.enabled():
        print("Telegram non configurato: ecco i messaggi che arriverebbero.\n")
        print(notify.single_text(single), "\n\n" + "-" * 60 + "\n")
        print(notify.group_text(group))
        return
    ok = notify.send_text("🧪 <b>Radar carte Pokémon: notifiche di prova</b>\n"
                          "Gli annunci qui sotto sono finti.")
    ok &= notify.send_alert([single])
    ok &= notify.send_alert(group)
    print("Messaggi di prova inviati su Telegram." if ok else "Invio NON riuscito: controlla token e chat id nel file .env.")


if __name__ == "__main__":
    main()
