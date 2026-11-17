"""Legge i file della cartella dati/: parole chiave, nomi dei 1025 Pokémon, prezzi."""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from . import config

# Caratteri giapponesi, cinesi, coreani e thailandesi: non hanno spazi tra le
# parole, quindi li cerchiamo come "testo contenuto" e non come parola intera.
ASIAN = re.compile(r"[฀-๿ᄀ-ᇿ぀-ヿ㐀-鿿가-힯豈-﫿ｦ-ﾟ]")
KANA = re.compile(r"[぀-ヿｦ-ﾟ]")
HANGUL = re.compile(r"[ᄀ-ᇿ가-힯]")
HAN = re.compile(r"[㐀-鿿豈-﫿]")
THAI = re.compile(r"[฀-๿]")


def normalize(text: str) -> str:
    """minuscolo, accenti latini tolti, punteggiatura -> spazio, '/' tenuto.

    'Pokémon N.M. 215/203' -> ' pokemon n m 215 / 203 '
    I caratteri giapponesi/coreani/cinesi restano come sono.
    """
    text = unicodedata.normalize("NFKC", text or "").lower().replace("ß", "ss")
    out = []
    for ch in unicodedata.normalize("NFD", text):
        if unicodedata.combining(ch) and out and out[-1].isascii():
            continue                      # é -> e, ma ド resta ド
        out.append(ch)
    text = unicodedata.normalize("NFC", "".join(out)).replace("/", " / ")
    text = "".join(c if (c.isalnum() or c == "/") else " " for c in text)
    return " " + " ".join(text.split()) + " "


def term_pattern(term: str) -> str:
    """Regex per un termine gia' normalizzato (senza gli spazi esterni)."""
    if ASIAN.search(term):
        return re.escape(term)
    return r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"


def read_csv(path):
    """Legge un CSV con ';' (UTF-8, oppure come lo salva Excel su Windows)."""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    lines = text.splitlines()
    head = lines[0] if lines else ""
    delim = ";" if head.count(";") >= head.count(",") else ","
    return list(csv.DictReader(lines, delimiter=delim))


def to_float(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value.replace(".", "").replace(",", "."))
    except ValueError:
        return None


# --- Parole chiave ----------------------------------------------------------------
SECTION_RE = re.compile(r"^# (\d{1,2})\. [A-Z]")
SUBSECTION_RE = re.compile(r"^# --- (.+?) ---")
LANG_SUBSECTIONS = {"italiano": "IT", "inglese": "EN", "giapponese": "JP",
                    "coreano": "KO", "cinese": "CN"}


@dataclass
class Keyword:
    text: str          # come scritto nel file
    norm: str          # normalizzato, senza spazi esterni
    section: int
    sub: str           # sottosezione (es. "italiano", "acquisto multiplo ...")


@lru_cache(maxsize=1)
def keywords() -> list[Keyword]:
    out, section, sub = [], 0, ""
    for raw in config.KEYWORDS_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = SECTION_RE.match(line)
            if m:
                section, sub = int(m.group(1)), ""
            else:
                m = SUBSECTION_RE.match(line)
                if m:
                    sub = m.group(1).strip().lower()
            continue
        norm = normalize(line).strip()
        if norm and section:
            out.append(Keyword(line, norm, section, sub))
    return out


# --- Nomi dei Pokémon -----------------------------------------------------------
NAME_HEADER = re.compile(r"^# (\d{4}) (.+?)\s*(⚠.*)?$")


@dataclass
class Pokemon:
    dex: int
    name: str
    ambiguous: bool
    variants: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def pokemon() -> dict[int, Pokemon]:
    out, cur = {}, None
    for raw in config.NAMES_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = NAME_HEADER.match(line)
        if m:
            cur = Pokemon(int(m.group(1)), m.group(2).strip(), bool(m.group(3)))
            out[cur.dex] = cur
            continue
        if line.startswith("#") or cur is None:
            continue
        norm = normalize(line).strip()
        if norm:
            cur.variants.append(norm)
    return out


@lru_cache(maxsize=1)
def name_index() -> dict[str, int]:
    """variante normalizzata -> numero Pokédex (la prima vince)."""
    idx = {}
    for p in pokemon().values():
        for v in p.variants:
            idx.setdefault(v, p.dex)
    return idx


# --- Prezzi -------------------------------------------------------------------
THR_GOOD = "Soglia buon affare € (70% trend)"
THR_SUPER = "Soglia super affare € (50% trend)"
NUM_SPLIT = re.compile(r"^([A-Za-z]*)0*(\d+)$")


def number_key(num: str) -> str:
    """'064' -> '64', 'TG05' -> 'tg5', 'GG01' -> 'gg1'."""
    m = NUM_SPLIT.match((num or "").strip())
    if not m:
        return (num or "").strip().lower()
    return m.group(1).lower() + str(int(m.group(2)))


@dataclass
class Card:
    lang: str            # "EN" o "JP"
    dex: int
    pokemon: str
    name: str
    set: str
    set_code: str
    number: str
    num_key: str
    total: int | None
    category: str
    illustrator: str
    trend: float | None
    good: float | None
    super: float | None
    kind: str = ""       # IR, SIR, ALT, TG, GG oppure FA, SECRET, ALTRO (vedi KIND_LABEL)

    def label(self) -> str:
        lang = "EN" if self.lang == "EN" else "JP"
        return f"[{lang}] {self.name} · {self.set} #{self.number} · {KIND_LABEL.get(self.kind, self.category)}"


KIND_LABEL = {"IR": "IR / AR", "SIR": "SIR / SAR", "ALT": "Alternate art",
              "TG": "Trainer Gallery", "GG": "Galarian Gallery"}


def _base_kind(category: str) -> str:
    c = category.lower()
    if c.startswith("sir"):
        return "SIR"
    if c.startswith("ir"):
        return "IR"
    if c.startswith(("trainer gallery", "chr", "csr")):
        return "TG"          # CHR/CSR = equivalente giapponese della Trainer Gallery
    if c.startswith("galarian gallery"):
        return "GG"
    if c.startswith("full art"):
        return "FA"
    if c.startswith("secret"):
        return "SECRET"
    return "ALTRO"           # hyper rare/oro, Mega, Pikachu rare, BWR...


def _mark_alt_art(all_cards):
    """Le alternate art nei CSV sono dentro "Full art" o "Secret".

    Schema dei set Spada e Scudo / Sole e Luna (verificato su CardTrader, es.
    Evolving Skies): quando la stessa carta compare due volte con numeri
    consecutivi nella stessa categoria, la seconda e' l'alternate art
    (Glaceon V 174 full art -> 175 alternate art; Umbreon VMAX 214 rainbow
    -> 215 alternate art). Le oro hanno numeri lontani e restano escluse.
    """
    groups = {}
    for c in all_cards:
        if c.kind in ("FA", "SECRET") and c.num_key.isdigit():
            groups.setdefault((c.lang, c.set_code, c.kind, normalize(c.name)), []).append(c)
    for same in groups.values():
        same.sort(key=lambda c: int(c.num_key))
        for a, b in zip(same, same[1:]):
            if int(b.num_key) == int(a.num_key) + 1:
                b.kind = "ALT"


@lru_cache(maxsize=1)
def cards() -> dict[int, list[Card]]:
    out: dict[int, list[Card]] = {}
    for r in read_csv(config.ALL_CARDS_CSV):
        try:
            dex = int(r["N° Pokédex"])
        except (KeyError, ValueError):
            continue
        tot = r.get("Totale ufficiale set", "").strip()
        out.setdefault(dex, []).append(Card(
            lang="JP" if r["Lingua"].lower().startswith("giap") else "EN",
            dex=dex, pokemon=r["Pokémon"], name=r["Nome carta"], set=r["Set"],
            set_code=r["Codice set"], number=r["Numero"], num_key=number_key(r["Numero"]),
            total=int(tot) if tot.isdigit() else None, category=r["Categoria"],
            illustrator=r.get("Illustratore", ""),
            trend=to_float(r["Prezzo trend Cardmarket €"]),
            good=to_float(r[THR_GOOD]), super=to_float(r[THR_SUPER]),
            kind=_base_kind(r["Categoria"]),
        ))
    _mark_alt_art([c for rows in out.values() for c in rows])
    return out


def wanted(card) -> bool:
    return card.kind in config.WANTED_KINDS


@lru_cache(maxsize=1)
def wanted_cards() -> dict[int, list[Card]]:
    """Solo le rarita' che interessano (config.WANTED_KINDS)."""
    out = {}
    for dex, rows in cards().items():
        keep = [c for c in rows if wanted(c)]
        if keep:
            out[dex] = keep
    return out


@dataclass
class CardexEntry:
    dex: int
    name: str
    owned: bool
    cheapest: str
    trend: float | None
    good: float | None
    super: float | None


YES = {"si", "sì", "s", "yes", "y", "x", "1", "presa", "ok", "true"}


@lru_cache(maxsize=1)
def cardex() -> dict[int, CardexEntry]:
    out = {}
    for r in read_csv(config.CARDEX_CSV):
        try:
            dex = int(r["N° Pokédex"])
        except (KeyError, ValueError):
            continue
        # riferimento = la carta PIU' ECONOMICA tra le rarita' volute (non quella
        # del CSV cardex, che puo' essere una full art)
        priced = [c for c in wanted_cards().get(dex, []) if c.good is not None and c.trend]
        best = min(priced, key=lambda c: c.trend) if priced else None
        out[dex] = CardexEntry(
            dex=dex, name=r["Pokémon (EN/IT)"],
            owned=(r.get("Presa (sì/no)", "") or "").strip().lower() in YES,
            cheapest=best.label() if best else "",
            trend=best.trend if best else None,
            good=best.good if best else None, super=best.super if best else None,
        )
    return out


SET_COMMENT = re.compile(r"^#\s+(.+?/.+?)\s+-\s+\d")


def set_aliases() -> list[list[str]]:
    """Dai commenti della sezione 6: ['luce nera', 'black bolt', 'blk'] ecc."""
    out, section = [], 0
    for raw in config.KEYWORDS_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        m = SECTION_RE.match(line)
        if m:
            section = int(m.group(1))
            continue
        if section == 6:
            m = SET_COMMENT.match(line)
            if m:
                out.append([normalize(x).strip() for x in m.group(1).split("/") if x.strip()])
    return out


@lru_cache(maxsize=1)
def set_index() -> dict[str, set[str]]:
    """nome o codice del set normalizzato -> codici set (per riconoscere il set nel titolo)."""
    idx: dict[str, set[str]] = {}
    for rows in cards().values():
        for c in rows:
            for key in (c.set, c.set_code):
                n = normalize(key).strip()
                # codici troppo corti o solo numeri ("151") sono ambigui
                if n and (len(n) >= 4 or ASIAN.search(n)) and not n.isdigit():
                    idx.setdefault(n, set()).add(c.set_code)
    # nomi italiani e sigle (BLK, PAL, EVS...) presi dalla sezione 6
    for group in set_aliases():
        codes = set().union(*(idx.get(n, set()) for n in group))
        if codes:
            for n in group:
                if n and not n.isdigit() and len(n) >= 3:
                    idx.setdefault(n, set()).update(codes)
    return idx
