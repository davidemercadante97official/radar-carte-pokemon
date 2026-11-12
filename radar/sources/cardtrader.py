"""CardTrader (API ufficiale, facoltativa): serve CARDTRADER_TOKEN.

Il token si crea gratis dal proprio profilo CardTrader (Impostazioni -> API).
NOTA: scritto seguendo la struttura nota dell'API v2 ma NON ancora provato con
un token vero. Se qualcosa non torna, il radar lo segnala come errore della
fonte "cardtrader" e continua con gli altri siti.

Per ogni espansione che contiene carte artistiche di Pokémon mancanti legge
tutte le offerte e crea un annuncio "grezzo" per ciascuna, con un titolo
costruito (nome, set, numero, lingua, condizione) che passa dagli stessi
filtri degli altri siti.
"""
from __future__ import annotations

import os
import time

from .. import config, dati
from ..dati import normalize

API = "https://api.cardtrader.com/api/v2"
LANG_WORD = {"en": "english", "it": "italiano", "jp": "japanese", "ja": "japanese",
             "kr": "korean", "ko": "korean", "zh-cn": "chinese", "zh-tw": "chinese",
             "zh": "chinese", "fr": "french", "de": "german", "es": "spanish",
             "pt": "portuguese", "th": "thai", "id": "indonesian"}


def _get(ctx, path, **params):
    r = ctx.http.get(API + path, params=params, timeout=40,
                     headers={"Authorization": f"Bearer {os.environ['CARDTRADER_TOKEN']}",
                              "Accept": "application/json"})
    if r.status_code == 429:
        time.sleep(5)
        r = ctx.http.get(API + path, params=params, timeout=40,
                         headers={"Authorization": f"Bearer {os.environ['CARDTRADER_TOKEN']}"})
    r.raise_for_status()
    time.sleep(0.3)
    return r.json()


def _target_expansions(expansions):
    """Espansioni CardTrader che contengono carte artistiche di Pokémon mancanti."""
    cdx = dati.cardex()
    wanted = {}
    for dex, rows in dati.cards().items():
        if dex in cdx and cdx[dex].owned:
            continue
        for c in rows:
            for key in (c.set, c.set_code):
                wanted.setdefault(normalize(key).strip(), set()).add(c.set_code)
    out = []
    for e in expansions:
        keys = {normalize(e.get("name", "")).strip(), normalize(e.get("code", "")).strip()}
        codes = set().union(*(wanted.get(k, set()) for k in keys if k))
        if codes:
            out.append(e)
    return out


def cardtrader(ctx):
    if not os.getenv("CARDTRADER_TOKEN"):
        ctx.skip("cardtrader", "manca CARDTRADER_TOKEN")
        return []
    runs = ctx.state.get("runs", 0)
    if runs % config.CARDTRADER_EVERY_N_RUNS:
        return []          # non a ogni giro: le offerte sono tante
    out = []
    try:
        games = _get(ctx, "/games")
        games = games.get("array", games) if isinstance(games, dict) else games
        game_id = next(g["id"] for g in games if "pok" in (g.get("name", "") + g.get("display_name", "")).lower())
        exps = [e for e in _get(ctx, "/expansions") if e.get("game_id") == game_id]
        targets = _target_expansions(exps)
        if not targets:
            ctx.ok("cardtrader", "nessuna espansione abbinata ai CSV")
            return []
        start = ctx.state.get("cardtrader_rotation", 0) % len(targets)
        batch = (targets + targets)[start:start + config.CARDTRADER_MAX_EXPANSIONS]
        ctx.state["cardtrader_rotation"] = start + len(batch)
        for exp in batch:
            bps = {}
            for b in _get(ctx, "/blueprints/export", expansion_id=exp["id"]):
                fp = b.get("fixed_properties") or {}
                bps[b["id"]] = (b.get("name", ""), fp.get("collector_number", ""))
            products = _get(ctx, "/marketplace/products", expansion_id=exp["id"])
            if isinstance(products, dict):
                products = [p for lst in products.values() for p in lst]
            for p in products:
                if p.get("graded"):
                    continue
                name, num = bps.get(p.get("blueprint_id"), (p.get("name_en", ""), ""))
                props = p.get("properties_hash") or {}
                lang = str(props.get("pokemon_language", "")).lower()
                extra = []
                if props.get("signed"):
                    extra.append("signed")
                if props.get("altered"):
                    extra.append("altered")
                price = p.get("price") or {}
                cents = p.get("price_cents", price.get("cents"))
                user = p.get("user") or {}
                title = f"{name} {exp.get('name', '')} {num} {LANG_WORD.get(lang, lang)} {' '.join(extra)}".strip()
                out.append({
                    "native_id": f"cardtrader:{p.get('id')}", "title": title,
                    "url": f"https://www.cardtrader.com/cards/{p.get('blueprint_id')}",
                    "price": (cents or 0) / 100 if cents is not None else None,
                    "currency": p.get("price_currency", price.get("currency", "EUR")),
                    "shipping": None, "image": "", "source": "cardtrader", "platform": "cardtrader",
                    "seller": user.get("username", ""), "seller_name": user.get("username", ""),
                    "seller_url": f"https://www.cardtrader.com/users/{user.get('username')}" if user.get("username") else "",
                    "country": user.get("country_code", ""),
                    "condition": props.get("condition", ""),
                    "zero": bool(user.get("can_sell_via_hub")),
                })
        ctx.ok("cardtrader", f"{len(batch)} espansioni")
    except Exception as e:
        ctx.fail("cardtrader", e)
    return out
