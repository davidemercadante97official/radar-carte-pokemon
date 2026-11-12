"""Marketplace: eBay (API ufficiale), Subito, Vinted, Wallapop.

Ogni fonte ritorna una lista di dict "grezzi":
  native_id, title, url, price, currency, shipping (None = sconosciuta),
  image, source, platform, seller, seller_name, country, condition
"""
from __future__ import annotations

import base64
import html
import json
import os
import re
import time

from .. import config, dati
from ..net import get, to_float


# --- Subito.it -------------------------------------------------------------
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def subito(ctx):
    out = []
    try:
        for q in config.SUBITO_QUERIES:
            r = get(ctx.http, "https://www.subito.it/annunci-italia/vendita/usato/",
                    params={"q": q, "order": "datedesc"})
            m = NEXT_DATA.search(r.text)
            if not m:
                continue
            data = json.loads(m.group(1))
            items = (data.get("props", {}).get("pageProps", {}).get("initialState", {})
                     .get("items", {}).get("originalList", []))
            for wrap in items:
                it = wrap.get("item", wrap)
                if not it.get("subject"):
                    continue
                urn = it.get("urn", "")
                feat = it.get("features") or {}
                pf = (feat.get("/price") or {}).get("values") or []
                cond = ((feat.get("/item_condition") or {}).get("values") or [{}])[0].get("value", "")
                imgs = it.get("images") or []
                adv = it.get("advertiser") or {}
                geo = (it.get("geo") or {}).get("town", {}) or {}
                out.append({
                    "native_id": "subito:" + urn.split(":")[-1],
                    "title": it["subject"], "url": (it.get("urls") or {}).get("default", ""),
                    "price": to_float(pf[0].get("key")) if pf else None, "currency": "EUR",
                    "shipping": None,
                    "image": (imgs[0].get("cdnBaseUrl", "") + "?rule=gallery-desktop-1x-auto") if imgs else "",
                    "source": "subito.it", "platform": "subito.it",
                    "seller": str(adv.get("userId") or ""), "seller_name": adv.get("name") or "",
                    "country": "IT", "location": geo.get("value", ""),
                    "condition": "",   # "Usato - ottime condizioni" non dice nulla sulla carta
                })
        ctx.ok("subito.it")
    except Exception as e:
        ctx.fail("subito.it", e)
    return out


# --- Vinted (pagina di ricerca) -------------------------------------------------
VINTED_CARD = re.compile(
    r'<img src="(https://images\d*\.vinted\.net/[^"]+)" alt="([^"]+)"[^>]*'
    r'data-testid="product-item-id-(\d+)--image--img"', re.S)
VINTED_PRICES = re.compile(r"(\d+[.,]\d{2})\s*(?:€|£|EUR)")
VINTED_MEMBER = re.compile(r"/member/(\d+)(?:-([^\"?/]+))?")


def vinted(ctx):
    out = []
    for domain, queries in config.VINTED.items():
        name = domain.replace("www.", "")
        try:
            for q in queries:
                r = get(ctx.http, f"https://{domain}/catalog",
                        params={"search_text": q, "order": "newest_first"})
                for img, alt, iid in VINTED_CARD.findall(r.text):
                    alt = html.unescape(alt)
                    # alt = "Titolo, Brand: X, Condizioni: Y, 1.00 €, 1.75 €"
                    title = re.split(r",\s*[A-ZÉÄÖÜ][\wäöüéèà ]{1,20}:\s", alt)[0]
                    cond = re.search(r"(?:Condizioni|Condition|Zustand|État):\s*([^,]+)", alt)
                    prices = VINTED_PRICES.findall(alt)
                    # il secondo prezzo include la "protezione acquisti": usiamo quello
                    price = to_float(prices[-1]) if prices else None
                    slug = re.search(r'href="(/items/%s-[^"?]*)' % iid, r.text)
                    out.append({
                        "native_id": f"vinted:{iid}", "title": title,
                        "url": f"https://{domain}" + (slug.group(1) if slug else f"/items/{iid}"),
                        "price": price, "currency": "GBP" if domain.endswith(".co.uk") else "EUR",
                        "shipping": None, "image": img, "source": name, "platform": "vinted",
                        "seller": "", "seller_name": "", "country": "",
                        "condition": cond.group(1) if cond else "",
                        "needs_seller": True,   # il venditore si legge dalla pagina dell'annuncio
                    })
            ctx.ok(name)
        except Exception as e:
            ctx.fail(name, e)
    return out


def vinted_seller(ctx, item) -> None:
    """Legge il venditore dalla pagina Vinted (solo per gli annunci in soglia)."""
    try:
        r = get(ctx.http, item["url"].split("?")[0])
        m = VINTED_MEMBER.search(r.text)
        if m:
            item["seller"] = m.group(1)
            item["seller_name"] = (m.group(2) or "").replace("-", " ")
            item["seller_url"] = f"https://{item['source'].replace('vinted', 'www.vinted', 1)}/member/{m.group(1)}"
    except Exception as e:
        print(f"[vinted] venditore non letto per {item['url']}: {e}")


# --- Wallapop -------------------------------------------------------------------
def wallapop(ctx):
    out = []
    try:
        for kw, lat, lon in config.WALLAPOP:
            r = get(ctx.http, "https://api.wallapop.com/api/v3/search",
                    params={"keywords": kw, "order_by": "newest", "source": "search_box",
                            "latitude": lat, "longitude": lon},
                    headers={"X-DeviceOS": "0", "Accept": "application/json"})
            items = r.json().get("data", {}).get("section", {}).get("payload", {}).get("items", [])
            for it in items:
                imgs = it.get("images") or [{}]
                price = it.get("price") or {}
                loc = it.get("location") or {}
                country = loc.get("country_code", "")
                host = "es.wallapop.com" if country == "ES" else "it.wallapop.com"
                if (it.get("reserved") or {}).get("flag"):
                    continue
                out.append({
                    "native_id": f"wallapop:{it.get('id')}", "title": it.get("title", ""),
                    "url": f"https://{host}/item/{it.get('web_slug')}",
                    "price": to_float(price.get("amount")), "currency": price.get("currency", "EUR"),
                    "shipping": None, "image": (imgs[0].get("urls") or {}).get("medium", ""),
                    "source": "wallapop", "platform": "wallapop",
                    "seller": it.get("user_id", ""), "seller_name": "",
                    "country": country, "location": loc.get("city", ""), "condition": "",
                })
        ctx.ok("wallapop")
    except Exception as e:
        ctx.fail("wallapop", e)
    return out


# --- eBay Browse API ------------------------------------------------------------
# Servono EBAY_CLIENT_ID e EBAY_CLIENT_SECRET (account developer.ebay.com).
EBAY_HOST = {"EBAY_IT": "ebay.it", "EBAY_DE": "ebay.de", "EBAY_GB": "ebay.co.uk",
             "EBAY_US": "ebay.com", "EBAY_FR": "ebay.fr", "EBAY_ES": "ebay.es"}


def _ebay_token(ctx, cid, secret):
    tok = ctx.http.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers={"Authorization": "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode(),
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials",
              "scope": "https://api.ebay.com/oauth/api_scope"}, timeout=25)
    tok.raise_for_status()
    return tok.json()["access_token"]


def _ebay_search(ctx, token, market, q):
    r = ctx.http.get(
        "https://api.ebay.com/buy/browse/v1/item_summary/search",
        params={"q": q, "sort": "newlyListed", "limit": 200,
                "filter": "buyingOptions:{FIXED_PRICE}"},
        headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": market,
                 # spedizione calcolata verso l'Italia
                 "X-EBAY-C-ENDUSERCTX": "contextualLocation=country%3DIT"}, timeout=25)
    if r.status_code == 429:
        raise RuntimeError("limite giornaliero eBay raggiunto")
    r.raise_for_status()
    out = []
    for it in r.json().get("itemSummaries", []):
        price = it.get("price") or {}
        ship = None
        opts = it.get("shippingOptions") or []
        if opts and opts[0].get("shippingCost"):
            ship = to_float(opts[0]["shippingCost"].get("value"))
        seller = it.get("seller") or {}
        legacy = it.get("legacyItemId") or it.get("itemId", "")
        out.append({
            "native_id": f"ebay:{legacy}", "title": it.get("title", ""),
            "url": it.get("itemWebUrl", ""),
            "price": to_float(price.get("value")), "currency": price.get("currency", ""),
            "shipping": ship, "image": (it.get("image") or {}).get("imageUrl", ""),
            "source": EBAY_HOST.get(market, "ebay"), "platform": "ebay",
            "seller": seller.get("username", ""), "seller_name": seller.get("username", ""),
            "seller_url": f"https://www.ebay.it/usr/{seller.get('username')}" if seller.get("username") else "",
            "country": (it.get("itemLocation") or {}).get("country", ""),
            # "Graded"/"Gradata" viene scartata dalle parole della sezione 11
            "condition": it.get("condition", ""),
        })
    time.sleep(0.3)
    return out


def ebay(ctx):
    cid, secret = os.getenv("EBAY_CLIENT_ID"), os.getenv("EBAY_CLIENT_SECRET")
    if not (cid and secret):
        ctx.skip("ebay", "mancano EBAY_CLIENT_ID / EBAY_CLIENT_SECRET")
        return []
    out = []
    try:
        token = _ebay_token(ctx, cid, secret)
        for market in config.EBAY_MARKETPLACES:
            for q in config.EBAY_QUERIES:
                out += _ebay_search(ctx, token, market, q)
        # Pokémon mancanti cercati per nome, a rotazione
        missing = [e for e in dati.cardex().values() if not e.owned and e.good]
        if missing and config.EBAY_ROTATING_PER_RUN:
            start = ctx.state.get("ebay_rotation", 0) % len(missing)
            batch = (missing + missing)[start:start + config.EBAY_ROTATING_PER_RUN]
            ctx.state["ebay_rotation"] = start + len(batch)
            for e in batch:
                for market in config.EBAY_ROTATING_MARKETS:
                    out += _ebay_search(ctx, token, market,
                                        f'"{e.name}" pokemon {config.EBAY_ROTATING_TERMS}')
        ctx.ok("ebay")
    except Exception as e:
        ctx.fail("ebay", e)
    return out
