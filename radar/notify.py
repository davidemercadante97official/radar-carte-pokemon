"""Notifiche Telegram: una per annuncio, oppure una per venditore se ne ha piu' d'uno."""
from __future__ import annotations

import html
import os
import time

import requests

from . import config

LEVEL_HEAD = {"super": "🚨 <b>SUPER AFFARE</b>", "buono": "💡 <b>Buon affare</b>",
              "valutare": "📦 <b>Lotto da valutare</b>"}
PLATFORM = {"ebay": "eBay", "subito.it": "Subito", "vinted": "Vinted",
            "wallapop": "Wallapop", "cardtrader": "CardTrader"}
SUSPICIOUS_RATIO = 0.35     # sotto il 35% del trend: possibile falso o foto non sua


def enabled() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _api(method: str, **data):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    data.setdefault("chat_id", os.environ["TELEGRAM_CHAT_ID"])
    url = f"https://api.telegram.org/bot{token}/{method}"
    r = requests.post(url, data=data, timeout=30)
    if r.status_code == 429:  # troppi messaggi: aspettiamo e riproviamo
        time.sleep(int(r.json().get("parameters", {}).get("retry_after", 5)) + 1)
        r = requests.post(url, data=data, timeout=30)
    if not r.ok:
        print(f"[telegram] {method}: {r.status_code} {r.text[:200]}")
    return r


def eur(x) -> str:
    return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def e(s) -> str:
    return html.escape(str(s or ""))


def price_line(a) -> str:
    ship = "spedizione stimata" if a["ship_estimated"] else "spedizione"
    base = f"{eur(a['price_eur'])} + {eur(a['ship_eur'])} {ship} = <b>{eur(a['total'])}</b>"
    if a.get("currency") and a["currency"] != "EUR":
        base += f" (prezzo in {e(a['currency'])}, convertito)"
    return "💶 " + base


def verdict_lines(a) -> list[str]:
    v = a["verdict"]
    lines = []
    if v["type"] == "carta":
        lines.append(f"🎴 #{v['dex']:04d} <b>{e(v['pokemon'])}</b> · "
                     + ("🆕 ti manca" if v["missing"] else "✔️ già presa"))
        what = "carta riconosciuta" if v["ref_kind"] == "carta" else "carta artistica più economica di questo Pokémon"
        lines.append(f"📋 Riferimento ({what}): {e(v['ref'])}")
        pct = f" · {a['total'] / v['trend']:.0%} del trend" if v.get("trend") else ""
        lines.append(f"📉 Soglia super {eur(v['super'])} · buon affare {eur(v['good'])}"
                     + (f" · trend {eur(v['trend'])}" if v.get("trend") else "") + pct)
        if v.get("cardex_cheapest") and v.get("cardex_good") and v["cardex_good"] < a["total"]:
            lines.append(f"💡 Per il cardex basta anche: {e(v['cardex_cheapest'])}")
        if v.get("trend") and a["total"] < v["trend"] * SUSPICIOUS_RATIO:
            lines.append("⚠️ Prezzo molto basso: controlla che non sia falsa (foto fronte/retro, a luce radente)")
        if v.get("lang_note"):
            lines.append(f"ℹ️ {e(v['lang_note'])}")
    else:
        names = ", ".join(v["missing_names"][:12])
        lines.append("📦 <b>Lotto</b>" + (f" · ti mancano: {e(names)}" if names else ""))
        lines += [f"📋 {e(d)}" for d in v["detail"]]
        lines.append("ℹ️ Chiedi la lista o la foto di ogni carta prima di comprare")
    if a["check"]:
        lines.append("🔎 <b>DA VERIFICARE</b>: " + e(", ".join(a["check"])))
    if a.get("multi"):
        lines.append("🤝 Il venditore parla di " + e(", ".join(a["multi"])))
    return lines


def where_line(a) -> str:
    parts = [f"🛒 {e(a['source'])}"]
    if a.get("seller_name"):
        parts.append(f"venditore {e(a['seller_name'])}")
    if a.get("zero"):
        parts.append("CardTrader Zero")
    if a.get("country") and a["country"] not in config.EU_COUNTRIES:
        parts.append(f"🌍 spedisce da {e(a['country'])}: fuori UE, possibile dogana")
    return " · ".join(parts)


def link(a) -> str:
    return f'<a href="{html.escape(a["url"], quote=True)}">Apri l\'annuncio</a>'


def single_text(a) -> str:
    return "\n".join([LEVEL_HEAD[a["level"]], f"<b>{e(a['title'])}</b>", *verdict_lines(a),
                      price_line(a), where_line(a), link(a)])


def group_text(items, older=0) -> str:
    """Piu' annunci in soglia dello stesso venditore in un unico messaggio."""
    best = min(items, key=lambda a: ("super", "buono", "valutare").index(a["level"]))
    first = items[0]
    sum_price = sum(a["price_eur"] for a in items)
    ship = max(a["ship_eur"] for a in items)
    who = first.get("seller_name") or first.get("seller")
    head = [LEVEL_HEAD[best["level"]] + f" · <b>{len(items)} annunci dello stesso venditore</b>",
            f"👤 {e(who)} su {e(PLATFORM.get(first['platform'], first['platform']))}"
            + (f' · <a href="{html.escape(first["seller_url"], quote=True)}">profilo</a>' if first.get("seller_url") else ""),
            f"🧮 Tutto insieme: {eur(sum_price)} + una spedizione (~{eur(ship)}) = <b>{eur(sum_price + ship)}</b>"
            " — chiedi la spedizione combinata"]
    if older:
        head.append(f"📌 Ha anche altri {older} annunci in soglia già segnalati")
    body = []
    for i, a in enumerate(items[:10], 1):
        v = a["verdict"]
        tag = {"super": "🚨", "buono": "💡", "valutare": "📦"}[a["level"]]
        if v["type"] == "carta":
            what = f"#{v['dex']:04d} {e(v['pokemon'])}" + (" 🆕" if v["missing"] else "")
            thr = f"soglia {eur(v['good'])}"
        else:
            what = "Lotto" + (f" ({len(v['missing_names'])} mancanti)" if v["missing_names"] else "")
            thr = "; ".join(e(d) for d in v["detail"]) or "da valutare"
        chk = f" · 🔎 {e(', '.join(a['check']))}" if a["check"] else ""
        body.append(f"\n{i}. {tag} <b>{e(a['title'])}</b>\n   {what} · {eur(a['price_eur'])} ({thr}){chk}\n"
                    f'   <a href="{html.escape(a["url"], quote=True)}">apri</a>')
    if len(items) > 10:
        body.append(f"\n…e altri {len(items) - 10}.")
    return "\n".join(head) + "\n" + "\n".join(body)


def send_alert(items, older=0) -> bool:
    """items = annunci dello stesso venditore (anche uno solo)."""
    level = min((a["level"] for a in items), key=("super", "buono", "valutare").index)
    silent = "true" if (config.NORMAL_SILENT and level != "super") else "false"
    if len(items) == 1 and not older:
        a = items[0]
        text = single_text(a)
        if a.get("image") and len(text) <= 1024:
            if _api("sendPhoto", photo=a["image"], caption=text, parse_mode="HTML",
                    disable_notification=silent).ok:
                return True
        return _api("sendMessage", text=text, parse_mode="HTML",
                    disable_web_page_preview="false", disable_notification=silent).ok
    text = group_text(items, older)[:4000]
    return _api("sendMessage", text=text, parse_mode="HTML",
                disable_web_page_preview="true", disable_notification=silent).ok


def send_text(text: str, silent=False) -> bool:
    return _api("sendMessage", text=text, parse_mode="HTML", disable_web_page_preview="true",
                disable_notification="true" if silent else "false").ok
