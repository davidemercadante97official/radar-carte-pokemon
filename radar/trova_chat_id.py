"""Trova il chat id di Telegram e lo scrive nel file .env.

Prima: metti il token in .env (TELEGRAM_BOT_TOKEN=...) e scrivi "ciao" al bot.
Poi:   python -m radar.trova_chat_id   (oppure doppio clic su trova-chat-id.bat)
"""
from __future__ import annotations

import os
import re
import sys

import requests

from .config import ROOT

ENV = ROOT / ".env"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not ENV.exists():
        print("Non trovo il file .env nella cartella del radar.")
        return
    text = ENV.read_text(encoding="utf-8-sig")
    m = re.search(r"^TELEGRAM_BOT_TOKEN=(.*)$", text, re.M)
    token = (m.group(1) if m else "").strip().strip('"').strip("'").replace(" ", "")
    if not token:
        print("Nel file .env manca il token: scrivilo dopo TELEGRAM_BOT_TOKEN= e salva.")
        return
    if token.lower().startswith("bot"):
        token = token[3:]   # errore comune: "bot" incollato davanti al token
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
        data = r.json()
    except Exception as e:
        print(f"Non riesco a contattare Telegram: {e}")
        return
    if not data.get("ok"):
        print("Telegram dice che il token non è valido. Ricopialo da BotFather "
              "(/mybots → il tuo bot → API Token), tutto intero, e salva di nuovo il file .env.")
        return
    chats = {}
    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("edited_message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            chats[chat["id"]] = chat.get("first_name") or chat.get("title") or chat.get("username") or ""
    if not chats:
        print("Il token è giusto, ma il bot non ha ancora ricevuto messaggi.\n"
              "Apri il bot su Telegram, scrivigli 'ciao' e rilancia questo programma.")
        return
    chat_id, name = list(chats.items())[-1]
    new = re.sub(r"^TELEGRAM_CHAT_ID=.*$", f"TELEGRAM_CHAT_ID={chat_id}", text, flags=re.M)
    if new == text and f"TELEGRAM_CHAT_ID={chat_id}" not in text:
        new = text.rstrip("\n") + f"\nTELEGRAM_CHAT_ID={chat_id}\n"
    ENV.write_text(new, encoding="utf-8")
    os.environ["TELEGRAM_CHAT_ID"] = str(chat_id)
    print(f"Trovato! Chat id {chat_id} ({name}). L'ho scritto nel file .env.")
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat_id, "text": "✅ Radar carte Pokémon collegato a questa chat."},
                      timeout=30)
    print("Ti ho mandato un messaggio di conferma su Telegram." if r.ok else
          "Chat id salvato, ma il messaggio di conferma non è partito.")


if __name__ == "__main__":
    main()
