"""Un giro del radar carte Pokémon: legge i siti, filtra, valuta il prezzo, avvisa.

Uso:
    python -m radar.main                 # un giro
    python -m radar.main --ogni 15       # un giro ogni 15 minuti, finche' non chiudi
    python -m radar.main --dry-run       # niente Telegram, stampa i messaggi a video
    python -m radar.main --only subito,vinted
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from datetime import datetime, timedelta, timezone

from . import config, notify
from .matching import LEVEL_RANK, classify, evaluate
from .net import session
from .sources import cardtrader, marketplaces

STATE = config.ROOT / "data" / "stato.json"
DEALS = config.ROOT / "data" / "affari.json"
STATUS = config.ROOT / "data" / "siti.json"

SOURCES = {
    "ebay": marketplaces.ebay,
    "subito": marketplaces.subito,
    "vinted": marketplaces.vinted,
    "wallapop": marketplaces.wallapop,
    "cardtrader": cardtrader.cardtrader,
}
MAX_SELLER_LOOKUPS = 15      # pagine Vinted lette per trovare il venditore


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf8")
    tmp.replace(path)


class Context:
    def __init__(self, state):
        self.http = session()
        self.state = state
        self.status = {}

    def ok(self, name, note=""):
        self.status[name] = {"ok": True, "note": note, "at": now()}

    def fail(self, name, err):
        msg = f"{type(err).__name__}: {err}"[:300]
        self.status[name] = {"ok": False, "note": msg, "at": now()}
        print(f"[ERRORE] {name}: {msg}")

    def skip(self, name, note):
        self.status[name] = {"ok": None, "note": note, "at": now()}


def to_eur(value, currency):
    if value is None:
        return None
    return round(value * config.FX_TO_EUR.get((currency or "EUR").upper(), 1.0), 2)


def analyze(raw) -> dict | None:
    """Annuncio grezzo -> avviso (dict) se e' in soglia, altrimenti None."""
    if not raw.get("title") or not raw.get("url") or raw.get("price") is None:
        return None
    info = classify(raw["title"], raw.get("condition", ""))
    if info.excluded:
        return None
    price = to_eur(raw["price"], raw.get("currency"))
    ship_est = raw.get("shipping") is None
    ship = (config.DEFAULT_SHIPPING.get(raw.get("platform"), 3.0) if ship_est
            else to_eur(raw["shipping"], raw.get("currency")))
    total = round(price + ship, 2)
    verdict = evaluate(info, total)
    if not verdict:
        return None
    return {**raw, "price_eur": price, "ship_eur": ship, "ship_estimated": ship_est,
            "total": total, "level": verdict["level"], "verdict": verdict,
            "check": info.check, "multi": info.multi}


def group_key(a):
    if a.get("seller"):
        return f"{a['platform']}|{a['seller']}"
    return f"solo|{a['native_id']}"


def run(only=None, dry_run=False):
    state = load(STATE, {})
    state.setdefault("items", {})
    ctx = Context(state)
    t = now()
    started = time.time()

    raw_items = []
    for name, fn in SOURCES.items():
        if only and name not in only:
            continue
        print(f"→ {name}")
        try:
            got = fn(ctx)
            print(f"   {len(got)} risultati grezzi")
            raw_items.extend(got)
        except Exception as e:  # nessuna fonte deve fermare il giro
            traceback.print_exc()
            ctx.fail(name, e)

    alerts, seen = [], set()
    for raw in raw_items:
        iid = raw.get("native_id")
        if not iid or iid in seen:
            continue
        seen.add(iid)
        a = analyze(raw)
        if not a:
            continue
        old = state["items"].get(iid)
        if old:
            old["last_seen"] = t
            # gia' segnalato: riavvisa solo se il prezzo e' sceso a un livello migliore
            if LEVEL_RANK[a["level"]] >= LEVEL_RANK.get(old.get("level"), 9):
                continue
            a["price_drop_from"] = old.get("total")
        alerts.append(a)

    # Vinted: il venditore si legge dalla pagina dell'annuncio
    lookups = 0
    for a in alerts:
        if a.get("needs_seller") and not a.get("seller") and lookups < MAX_SELLER_LOOKUPS:
            marketplaces.vinted_seller(ctx, a)
            lookups += 1

    # raggruppa per venditore
    groups: dict[str, list] = {}
    for a in alerts:
        groups.setdefault(group_key(a), []).append(a)
    ordered = sorted(groups.values(), key=lambda g: (
        min(LEVEL_RANK[a["level"]] for a in g),
        not any(a["verdict"]["missing"] for a in g),
        min(a["total"] for a in g)))
    for g in ordered:
        g.sort(key=lambda a: (LEVEL_RANK[a["level"]], not a["verdict"]["missing"], a["total"]))

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    sent = 0
    print(f"\nAnnunci in soglia da segnalare: {len(alerts)} (in {len(ordered)} messaggi)")
    for g in ordered[: config.MAX_ALERTS_PER_RUN]:
        ids = {a["native_id"] for a in g}
        older = 0
        if not group_key(g[0]).startswith("solo|"):
            older = sum(1 for k, v in state["items"].items()
                        if k not in ids and v.get("group") == group_key(g[0])
                        and v.get("last_seen", "") >= cutoff)
        if dry_run or not notify.enabled():
            print("\n" + ("-" * 60))
            print(notify.single_text(g[0]) if len(g) == 1 and not older else notify.group_text(g, older))
        else:
            sent += notify.send_alert(g, older)
            time.sleep(1.2)
    extra = len(ordered) - config.MAX_ALERTS_PER_RUN
    if extra > 0 and notify.enabled() and not dry_run:
        notify.send_text(f"…e altri <b>{extra}</b> messaggi in soglia: li trovi in data/affari.json.",
                         silent=True)

    for a in alerts:
        state["items"][a["native_id"]] = {
            "title": a["title"], "url": a["url"], "source": a["source"], "total": a["total"],
            "level": a["level"], "group": group_key(a), "first_seen": t, "last_seen": t,
            "missing": a["verdict"]["missing"], "check": a["check"]}
    if len(state["items"]) > config.MAX_STORED:
        keep = sorted(state["items"].items(), key=lambda kv: kv[1].get("last_seen", ""))[-config.MAX_STORED:]
        state["items"] = dict(keep)
    state["runs"] = state.get("runs", 0) + 1
    state["last_run"] = t
    if not dry_run:
        save(STATE, state)
    save(DEALS, sorted(state["items"].values(), key=lambda x: x.get("last_seen", ""), reverse=True)[:500])
    prev = load(STATUS, {}).get("sources", {})
    prev.update(ctx.status)
    save(STATUS, {"last_run": t, "seconds": round(time.time() - started, 1),
                  "raw": len(raw_items), "alerts": len(alerts), "sent": sent, "sources": prev})
    print(f"Fatto in {time.time() - started:.0f} s: {len(raw_items)} annunci letti, "
          f"{len(alerts)} in soglia, {sent} messaggi inviati.")
    return alerts


def cli():
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # emoji nella console di Windows
    ap = argparse.ArgumentParser(description="Radar carte Pokémon artistiche")
    ap.add_argument("--dry-run", action="store_true", help="non manda messaggi Telegram")
    ap.add_argument("--only", default="", help="fonti separate da virgola: " + ",".join(SOURCES))
    ap.add_argument("--ogni", type=float, default=0, help="ripeti ogni N minuti")
    a = ap.parse_args()
    only = set(filter(None, a.only.split(","))) or None
    if not notify.enabled() and not a.dry_run:
        print("Telegram non configurato (manca il file .env): stampo i messaggi a video.")
    while True:
        try:
            run(only=only, dry_run=a.dry_run)
        except Exception:
            traceback.print_exc()
        if not a.ogni:
            break
        print(f"Prossimo giro tra {a.ogni:g} minuti (Ctrl+C per fermare).")
        time.sleep(a.ogni * 60)


if __name__ == "__main__":
    cli()
