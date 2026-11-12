"""Configura il bot Telegram: pulsante "Dashboard" e messaggio fissato col link.

Si lancia una volta sola (workflow "Configura bot Telegram" su GitHub):
    python -m radar.setup_bot
"""
from __future__ import annotations

from . import config  # noqa: F401  (legge il file .env e i certificati)

import os
import sys

import requests

DASHBOARD = os.getenv("DASHBOARD_URL", "https://davidemercadante97official.github.io/radar-carte-pokemon/")


def api(method: str, **payload):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=30)
    data = r.json()
    print(f"{method}: {'ok' if data.get('ok') else data.get('description')}")
    return data


def main():
    chat = os.environ["TELEGRAM_CHAT_ID"]
    ok = True

    # 1) pulsante accanto al campo di scrittura: apre la dashboard dentro Telegram
    ok &= api("setChatMenuButton", chat_id=int(chat), menu_button={
        "type": "web_app", "text": "Dashboard", "web_app": {"url": DASHBOARD}}).get("ok", False)

    # 2) messaggio con il link, fissato in cima alla chat
    msg = api("sendMessage", chat_id=chat, parse_mode="HTML",
              text=("🎴 <b>Radar Carte Pokémon</b>\n"
                    "Affari in soglia, lotti e avanzamento del cardex:\n"
                    f'<a href="{DASHBOARD}">Apri la dashboard</a>'),
              reply_markup={"inline_keyboard": [[{"text": "📊 Apri la dashboard", "url": DASHBOARD}]]},
              disable_web_page_preview=True)
    if msg.get("ok"):
        ok &= api("pinChatMessage", chat_id=chat, message_id=msg["result"]["message_id"],
                  disable_notification=True).get("ok", False)
    else:
        ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
