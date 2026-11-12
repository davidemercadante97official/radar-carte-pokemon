"""Decide se un annuncio e' una carta artistica (o un lotto) e se e' un affare.

Due passi:
  1. classify(titolo)  -> che cos'e' (Pokémon, carta, lingua, lotto, esclusioni)
  2. evaluate(info, prezzo totale) -> super affare / buon affare / niente
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from . import config, dati
from .dati import HAN, HANGUL, KANA, THAI, normalize, term_pattern

# Frasi "buone" che contengono una parola da scartare: le proteggiamo
# (oltre a quelle della sezione 9, es. "non gradata", "mai giocata").
EXTRA_POSITIVE = ["not graded", "no graded", "non graduata", "senza grading",
                  "psa 10 candidate", "psa10 candidate", "potential psa 10",
                  "candidata psa 10", "possibile psa 10"]
CONDITION_CLASSES = ("pos", "check", "excl")
LANG_ACCEPTED = {"IT", "EN", "JP", "KO", "CN"}

# 215/203, 161 / 131, TG05/TG30, GG01/GG70, SV107/SV122
NUM_TOTAL = re.compile(r"(?<![a-z0-9])(tg|gg|sv|rc|swsh)?0*(\d{1,3}) / (?:tg|gg|sv|rc)?0*(\d{1,3})(?![a-z0-9])")
NUM_GALLERY = re.compile(r"(?<![a-z0-9])(tg|gg)0*(\d{1,2})(?![0-9])")
LOOSE_NUM = re.compile(r"(?<![a-z0-9])(\d{1,3})(?![a-z0-9])")
NUM_HASH = re.compile(r"#\s?0*(\d{1,3})\b")
LOT_COUNT = re.compile(r"(?<![a-z0-9])(\d{1,3}) ?(carte|cards|card|pz|pezzi|pcs|units|full art|fa|ir|sir|ar|sar|sr|"
                       r"alt art|illustration rare|illustrazioni rare)(?![a-z])"
                       r"|(?<![a-z0-9])x ?(\d{1,4})(?![a-z0-9])")


class Matcher:
    """Un'unica regex per gruppo di termini: il termine piu' lungo vince."""

    def __init__(self, terms):
        self.terms = sorted(set(t for t in terms if t), key=len, reverse=True)
        self.rx = re.compile("|".join(term_pattern(t) for t in self.terms)) if self.terms else None

    def find(self, text):
        if not self.rx:
            return []
        return [(m.start(), m.end(), m.group(0)) for m in self.rx.finditer(text)]


@lru_cache(maxsize=1)
def matchers():
    groups: dict[str, list[str]] = {k: [] for k in
                                     ("art", "pos", "check", "excl", "lot", "multi", "ctx", "set")}
    lang_of: dict[str, str] = {}
    for kw in dati.keywords():
        s = kw.section
        if s in config.ART_SECTIONS:
            groups["art"].append(kw.norm)
        elif s == config.POSITIVE_SECTION:
            groups["pos"].append(kw.norm)
        elif s == config.CHECK_SECTION:
            groups["check"].append(kw.norm)
        elif s == config.EXCLUDE_SECTION:
            groups["excl"].append(kw.norm)
        elif s == config.LOT_SECTION:
            groups["multi" if kw.sub.startswith("acquisto multiplo") else "lot"].append(kw.norm)
        elif s == 3:
            lang = next((v for k, v in dati.LANG_SUBSECTIONS.items() if kw.sub.startswith(k)), None)
            if lang:
                lang_of[kw.norm] = lang
        elif s == 6:
            groups["set"].append(kw.norm)
        elif s in (7, 8):
            groups["ctx"].append(kw.norm)
    groups["pos"] += [normalize(x).strip() for x in EXTRA_POSITIVE]
    m = {k: Matcher(v) for k, v in groups.items()}
    m["lang"] = Matcher(lang_of)
    m["names"] = Matcher(dati.name_index())
    m["setidx"] = Matcher(dati.set_index())
    return m, lang_of


@dataclass
class Info:
    text: str
    excluded: str = ""                         # motivo dello scarto
    art: list[str] = field(default_factory=list)
    check: list[str] = field(default_factory=list)
    lot: list[str] = field(default_factory=list)
    multi: list[str] = field(default_factory=list)
    langs: set[str] = field(default_factory=set)
    dex: list[int] = field(default_factory=list)   # Pokémon trovati, in ordine
    number: tuple | None = None                     # (num_key, totale|None)
    sets: set[str] = field(default_factory=set)
    loose_numbers: set[str] = field(default_factory=set)
    count: int | None = None                        # carte nel lotto
    is_lot: bool = False


def _drop_contained(spans):
    """Toglie i termini 'condizione' contenuti in un termine piu' lungo di altro tipo.

    'non gradata' (buono) protegge 'gradata' (escludi); 'heavily played'
    (escludi) assorbe 'played' (da verificare).
    """
    keep = []
    for cls, s, e, t in spans:
        inside = any(c2 != cls and s2 <= s and e <= e2 and (e2 - s2) > (e - s)
                     for c2, s2, e2, _ in spans)
        if not inside:
            keep.append((cls, s, e, t))
    return keep


def classify(title: str, extra: str = "") -> Info:
    """Analizza titolo (+ eventuale testo extra, es. condizione dichiarata)."""
    text = normalize(f"{title} {extra}")
    m, lang_of = matchers()
    info = Info(text=text)

    if THAI.search(title or ""):
        info.excluded = "lingua thailandese"
        return info

    spans = [(cls, s, e, t) for cls in CONDITION_CLASSES for s, e, t in m[cls].find(text)]
    spans = _drop_contained(spans)
    excl = [t for cls, _, _, t in spans if cls == "excl"]
    if excl:
        info.excluded = "contiene: " + ", ".join(dict.fromkeys(excl))
        return info
    info.check = list(dict.fromkeys(t for cls, _, _, t in spans if cls == "check"))

    info.art = list(dict.fromkeys(t for _, _, t in m["art"].find(text)))
    info.lot = list(dict.fromkeys(t for _, _, t in m["lot"].find(text)))
    info.multi = list(dict.fromkeys(t for _, _, t in m["multi"].find(text)))
    info.langs = {lang_of[t] for _, _, t in m["lang"].find(text)}
    raw = title or ""
    if KANA.search(raw):
        info.langs.add("JP")
    if HANGUL.search(raw):
        info.langs.add("KO")
    if HAN.search(raw) and not KANA.search(raw):
        info.langs.add("CN")

    n = NUM_TOTAL.search(text)
    if n:
        info.number = ((n.group(1) or "") + str(int(n.group(2))), int(n.group(3)))
    else:
        n = NUM_GALLERY.search(text) or None
        if n:
            info.number = (n.group(1) + str(int(n.group(2))), None)
        else:
            n = NUM_HASH.search(title or "")
            if n:
                info.number = (str(int(n.group(1))), None)

    for _, _, t in m["setidx"].find(text):
        info.sets |= dati.set_index().get(t, set())
    if info.sets and not info.number:
        info.loose_numbers = {str(int(x)) for x in LOOSE_NUM.findall(text)}
    has_set_term = bool(m["set"].find(text)) or bool(info.sets)
    context = bool(info.art or info.number or has_set_term or m["ctx"].find(text)
                   or " pokemon " in text)

    pk = dati.pokemon()
    idx = dati.name_index()
    for _, _, t in m["names"].find(text):
        dex = idx.get(t)
        if dex is None or dex in info.dex:
            continue
        if pk[dex].ambiguous and not context:
            continue        # nome ambiguo (es. Mew, Golem) senza un termine della carta
        info.dex.append(dex)

    info.is_lot = bool(info.lot and info.art)
    if info.is_lot:
        c = LOT_COUNT.search(text)
        if c:
            info.count = int(c.group(1) or c.group(3))
            if info.count < 2:
                info.count = None
    return info


# --- Prezzo -------------------------------------------------------------------
def price_group(langs: set[str]) -> str | None:
    """Lingua del prezzo di riferimento: EN (anche per IT) o JP (anche per KO/CN)."""
    if langs & {"JP", "KO", "CN"} and not langs & {"IT", "EN"}:
        return "JP"
    if langs & {"IT", "EN"} and not langs & {"JP", "KO", "CN"}:
        return "EN"
    return None


def identify_card(info: Info, dex: int):
    """Trova la carta precisa nel CSV (numero/totale o set). None se non si sa."""
    rows = dati.cards().get(dex, [])
    if not rows:
        return None
    group = price_group(info.langs)
    cand = []
    if info.number:
        key, total = info.number
        cand = [c for c in rows if c.num_key == key and (total is None or c.total in (None, total)
                                                         or not key.isdigit())]
    if not cand and info.sets and info.loose_numbers:
        # "Excadrill ex BLK 160": set riconosciuto + numero senza totale
        cand = [c for c in rows if c.set_code in info.sets and c.num_key in info.loose_numbers]
    # Solo il set, senza numero (es. "Eevee Promo ... Evoluzioni Prismatiche"):
    # non basta per sapere quale carta e'. Si usa il riferimento del cardex.
    if not cand:
        return None
    if group:
        same = [c for c in cand if c.lang == group]
        cand = same or cand
    # piu' candidate: la meno cara (soglie piu' basse = piu' prudente)
    priced = [c for c in cand if c.good is not None]
    return min(priced, key=lambda c: c.trend or 0) if priced else None


LEVEL_RANK = {"super": 0, "buono": 1, "valutare": 2}


def evaluate(info: Info, total_eur: float | None, card_hint=None) -> dict | None:
    """Ritorna il verdetto (dict) se l'annuncio e' in soglia, altrimenti None."""
    if info.excluded or total_eur is None or total_eur <= 0:
        return None
    cdx = dati.cardex()

    if info.is_lot:
        named = [d for d in info.dex if d in cdx]
        missing = [d for d in named if not cdx[d].owned and cdx[d].good]
        level = None
        detail = []
        if missing:
            s_good = sum(cdx[d].good for d in missing)
            s_super = sum(cdx[d].super or 0 for d in missing)
            if total_eur <= s_super:
                level = "super"
            elif total_eur <= s_good:
                level = "buono"
            detail.append(f"Pokémon mancanti citati: {len(missing)} (soglia somma {s_good:.2f} €)".replace(".", ","))
        if info.count:
            per = total_eur / info.count
            lv = ("super" if per <= config.LOT_SUPER_PER_CARD else
                  "buono" if per <= config.LOT_GOOD_PER_CARD else None)
            if lv and (level is None or LEVEL_RANK[lv] < LEVEL_RANK[level]):
                level = lv
            detail.append(f"{info.count} carte → {per:.2f} € a carta".replace(".", ","))
        if level is None and not missing and not info.count and total_eur <= config.LOT_MAX_TOTAL_UNKNOWN:
            level = "valutare"
        if level is None:
            return None
        all_owned = bool(named) and not missing
        return {"type": "lotto", "level": level, "missing": not all_owned,
                "missing_names": [cdx[d].name for d in missing],
                "count": info.count, "detail": detail}

    if card_hint is not None:
        # la fonte sa gia' quale carta e' (es. CardTrader): niente indovinelli dal titolo
        dex, card = card_hint.dex, card_hint
    else:
        if not info.dex:
            return None
        dex = info.dex[0]
        card = identify_card(info, dex)
        if not info.art and card is None:
            return None          # niente termine artistico e carta non riconosciuta
    entry = cdx.get(dex)
    if card is not None:
        good, sup, trend = card.good, card.super, card.trend
        ref = card.label()
        ref_kind = "carta"
    elif entry and entry.good is not None:
        good, sup, trend = entry.good, entry.super, entry.trend
        ref = entry.cheapest
        ref_kind = "cardex"      # la carta artistica piu' economica di quel Pokémon
    else:
        return None
    if good is None:
        return None
    level = "super" if sup is not None and total_eur <= sup else "buono" if total_eur <= good else None
    if level is None:
        return None
    owned = bool(entry and entry.owned)
    if owned and (config.NOTIFY_OWNED == "mai" or (config.NOTIFY_OWNED == "super" and level != "super")):
        return None
    group = price_group(info.langs)
    lang_note = ""
    if card is not None and card.lang == "EN" and "IT" in info.langs:
        lang_note = "prezzo di riferimento dell'edizione inglese"
    elif card is not None and card.lang == "JP" and info.langs & {"KO", "CN"}:
        lang_note = "prezzo di riferimento dell'edizione giapponese"
    elif card is not None and group is None:
        lang_note = "lingua non indicata: controllala"
    return {"type": "carta", "level": level, "missing": not owned, "dex": dex,
            "pokemon": entry.name if entry else dati.pokemon()[dex].name,
            "ref": ref, "ref_kind": ref_kind, "trend": trend, "good": good, "super": sup,
            "cardex_cheapest": entry.cheapest if entry and ref_kind == "carta" else "",
            "cardex_good": entry.good if entry else None, "lang_note": lang_note}
