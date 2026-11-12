"""CardTrader (API ufficiale, facoltativa): serve CARDTRADER_TOKEN.

Il token si copia da CardTrader -> API - Area sviluppatori (pagina "Full API").
Documentazione: https://www.cardtrader.com/docs/api/full/reference

Come funziona:
  1. trova le espansioni CardTrader che corrispondono ai set dei CSV
     (per nome, es. "Evolving Skies", o per codice, es. "sv2a");
  2. per ogni espansione legge le carte (blueprint) e tiene solo quelle che
     sono nel CSV delle carte artistiche, riconosciute dal numero (215, TG05...);
  3. legge le offerte (le 25 piu' economiche per carta) e scarta subito quelle
     sopra la soglia, gradate, in lingue escluse o di venditori in vacanza;
  4. passa le rimaste agli stessi filtri degli altri siti, gia' sapendo
     esattamente quale carta sono.
"""
from __future__ import annotations

import os
import time

from .. import config, dati
from ..dati import normalize, number_key

API = "https://api.cardtrader.com/api/v2"
LANG_WORD = {"en": "english", "it": "italiano", "jp": "japanese", "ja": "japanese",
             "kr": "korean", "ko": "korean", "zh-cn": "chinese", "zh-tw": "chinese",
             "zh": "chinese", "cn": "chinese"}
POKEMON_GAME_ID = 5


def _get(ctx, path, **params):
    headers = {"Authorization": f"Bearer {os.environ['CARDTRADER_TOKEN']}",
               "Accept": "application/json"}
    for attempt in range(3):
        r = ctx.http.get(API + path, params=params, timeout=90, headers=headers)
        if r.status_code != 429:
            break
        time.sleep(3 * (attempt + 1))      # limite: 10 richieste/secondo sulle offerte
    r.raise_for_status()
    time.sleep(0.25)
    return r.json()


def _csv_cards_by_set():
    """nome o codice del set (normalizzato) -> carte artistiche del CSV."""
    idx: dict[str, list] = {}
    for rows in dati.cards().values():
        for c in rows:
            for key in (c.set, c.set_code):
                k = normalize(key).strip()
                if k:
                    idx.setdefault(k, []).append(c)
    return idx


def _limit(card, lang: str = "") -> float | None:
    """Prezzo massimo oltre il quale l'offerta non puo' essere in soglia.

    Le soglie della carta valgono solo per la stessa lingua del prezzo
    (inglese o giapponese); per le altre lingue vale la carta piu' economica
    del cardex, come in matching.evaluate.
    """
    entry = dati.cardex().get(card.dex)
    owned = bool(entry and entry.owned)
    if owned and config.NOTIFY_OWNED == "mai":
        return None
    same = (lang == "en" and card.lang == "EN") or (lang in ("jp", "ja") and card.lang == "JP")
    src = card if (same or not lang) else entry
    if src is None:
        return None
    return src.super if (owned and config.NOTIFY_OWNED == "super") else src.good


def _targets(expansions):
    """[(espansione, {numero: carta CSV})] per le espansioni con carte da cercare."""
    idx = _csv_cards_by_set()
    out = []
    for e in expansions:
        found = {}
        for key in (normalize(e.get("name", "")).strip(), normalize(e.get("code", "")).strip()):
            for c in idx.get(key, []):
                if _limit(c) is not None:
                    found.setdefault(c.num_key, c)
        if found:
            out.append((e, found))
    return out


def cardtrader(ctx):
    if not os.getenv("CARDTRADER_TOKEN"):
        ctx.skip("cardtrader", "manca CARDTRADER_TOKEN")
        return []
    if ctx.state.get("runs", 0) % config.CARDTRADER_EVERY_N_RUNS:
        return []          # non a ogni giro: le offerte sono tante
    out = []
    try:
        exps = [e for e in _get(ctx, "/expansions") if e.get("game_id") == POKEMON_GAME_ID]
        targets = _targets(exps)
        if not targets:
            ctx.ok("cardtrader", "nessuna espansione abbinata ai CSV")
            return []
        start = ctx.state.get("cardtrader_rotation", 0) % len(targets)
        batch = (targets + targets)[start:start + min(config.CARDTRADER_MAX_EXPANSIONS, len(targets))]
        ctx.state["cardtrader_rotation"] = start + len(batch)
        seen_offers = 0
        for exp, by_num in batch:
            wanted = {}
            for b in _get(ctx, "/blueprints/export", expansion_id=exp["id"]):
                fp = b.get("fixed_properties") or {}
                card = by_num.get(number_key(str(fp.get("collector_number", ""))))
                if card:
                    wanted[str(b["id"])] = (b, card)
            if not wanted:
                continue
            products = _get(ctx, "/marketplace/products", expansion_id=exp["id"])
            for bid, (b, card) in wanted.items():
                for p in products.get(bid, []):
                    seen_offers += 1
                    props = p.get("properties_hash") or {}
                    lang = str(props.get("pokemon_language") or "").lower()
                    if p.get("graded") or p.get("on_vacation") or props.get("pokemon_reverse"):
                        continue
                    if lang and lang not in LANG_WORD:
                        continue            # francese, tedesco, spagnolo, portoghese...
                    limit = _limit(card, lang)
                    price = p.get("price") or {}
                    cents = price.get("cents", p.get("price_cents"))
                    currency = price.get("currency", p.get("price_currency", "EUR"))
                    if cents is None:
                        continue
                    eur = cents / 100 * config.FX_TO_EUR.get(currency, 1.0)
                    if limit is None or eur > limit:
                        continue            # sopra soglia gia' senza spedizione
                    extra = [w for w, flag in (("signed", props.get("signed")),
                                               ("altered", props.get("altered"))) if flag]
                    user = p.get("user") or {}
                    title = " ".join(x for x in (
                        b.get("name", ""), b.get("version") or "", exp.get("name", ""),
                        LANG_WORD.get(lang, ""), *extra) if x)
                    out.append({
                        "native_id": f"cardtrader:{p.get('id')}", "title": title,
                        "url": f"https://www.cardtrader.com/cards/{b['id']}",
                        "price": cents / 100, "currency": currency, "shipping": None,
                        "image": b.get("image_url", ""), "source": "cardtrader",
                        "platform": "cardtrader",
                        "seller": user.get("username", ""), "seller_name": user.get("username", ""),
                        "seller_url": f"https://www.cardtrader.com/users/{user.get('username')}" if user.get("username") else "",
                        "country": user.get("country_code", ""),
                        "condition": props.get("condition") or "",
                        "zero": bool(user.get("can_sell_via_hub")),
                        "card_hint": card,       # sappiamo gia' quale carta e'
                    })
        ctx.ok("cardtrader", f"{len(batch)} espansioni su {len(targets)}, {seen_offers} offerte guardate")
    except Exception as e:
        ctx.fail("cardtrader", e)
    return out
