"""Impostazioni del radar carte Pokémon: dove cercare, spedizioni, soglie.

Le parole chiave e i prezzi NON stanno qui: sono nei file della cartella dati/
(parole chiave, nomi dei 1025 Pokémon, CSV con prezzi e soglie). Qui ci sono
solo le ricerche da lanciare su ogni sito e le regole di notifica.
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # sul PC di casa usa i certificati di Windows (antivirus che filtrano HTTPS)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
DATI = ROOT / "dati"
KEYWORDS_FILE = DATI / "parole-chiave-carte-pokemon-artistiche.txt"
NAMES_FILE = DATI / "nomi-pokemon-1025-ricerca.txt"
ALL_CARDS_CSV = DATI / "tutte-le-carte-artistiche.csv"
CARDEX_CSV = DATI / "cardex-1025-carte-artistiche.csv"


def load_env(path: Path = ROOT / ".env"):
    """Legge le password (token Telegram, eBay...) dal file .env, se c'e'."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            # token e id non hanno mai spazi: li togliamo (errore comune quando si incolla)
            v = "".join(v.split()).strip('"').strip("'")
            if k.strip() == "TELEGRAM_BOT_TOKEN" and v.lower().startswith("bot"):
                v = v[3:]
            os.environ.setdefault(k.strip(), v)


load_env()

# --- Sezioni del file parole chiave ------------------------------------------
SEARCH_SECTIONS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 12}
ART_SECTIONS = {1, 2, 4, 5}      # termini "carta artistica" (full art, IR, SIR, TG...)
POSITIVE_SECTION = 9             # condizioni buone (proteggono "non gradata", "mai giocata")
CHECK_SECTION = 10               # "da verificare"
EXCLUDE_SECTION = 11             # scarta l'annuncio
LOT_SECTION = 12                 # lotti

# --- Regole di notifica --------------------------------------------------------
# Pokémon gia' presi (colonna "Presa (sì/no)" = sì): "super" = avvisa solo per i
# super affari, "tutti" = come i mancanti, "mai" = mai.
NOTIFY_OWNED = "super"
# Le notifiche "buon affare" arrivano senza suono; i super affari con il suono.
NORMAL_SILENT = True
MAX_ALERTS_PER_RUN = 20          # oltre, arriva un riepilogo

# Lotti: se il titolo dice quante carte ci sono ("lotto 20 full art"), il lotto
# e' un buon affare sotto questo prezzo a carta (mediana delle soglie "buon
# affare" del cardex = 2,06 EUR). Super affare sotto LOT_SUPER_PER_CARD.
LOT_GOOD_PER_CARD = 2.0
LOT_SUPER_PER_CARD = 1.0
# Lotto senza numero di carte e senza nomi riconosciuti: avvisa come
# "lotto da valutare" solo se il totale (con spedizione) e' sotto questa cifra.
LOT_MAX_TOTAL_UNKNOWN = 40.0

# --- Spedizione --------------------------------------------------------------
# Usata quando il sito non dice quanto costa spedire (stima prudente, in EUR).
DEFAULT_SHIPPING = {
    "ebay": 2.5, "subito.it": 3.5, "vinted": 2.9, "wallapop": 3.5, "cardtrader": 2.0,
}
# Cambi approssimativi per confrontare i prezzi in euro.
FX_TO_EUR = {"EUR": 1.0, "GBP": 1.17, "USD": 0.92, "JPY": 0.0061, "CHF": 1.05}
EU_COUNTRIES = {
    "IT", "DE", "FR", "ES", "AT", "BE", "NL", "LU", "PT", "IE", "FI", "SE", "DK",
    "PL", "CZ", "SK", "SI", "HR", "HU", "RO", "BG", "GR", "CY", "MT", "EE", "LV", "LT",
}

# --- Ricerche per sito -------------------------------------------------------
# Ricerche ampie ordinate per "piu' recenti": a ogni giro arrivano gli annunci
# nuovi. Il filtro vero (nome Pokémon, termini, esclusioni) lo fa il radar.
SUBITO_QUERIES = [
    "pokemon full art", "pokemon illustrazione rara", "pokemon alt art",
    "pokemon sir", "pokemon ir", "lotto carte pokemon", "carte pokemon giapponesi",
]

VINTED = {
    "www.vinted.it": ["pokemon full art", "pokemon illustration rare", "pokemon alt art",
                      "pokemon sir", "pokemon ir", "pokemon art rare",
                      "lotto carte pokemon", "carte pokemon giapponesi"],
}

WALLAPOP = [
    # (keywords, lat, lon)
    ("pokemon full art", 41.9028, 12.4964),
    ("pokemon illustration rare", 41.9028, 12.4964),
    ("lotto carte pokemon", 41.9028, 12.4964),
]

# eBay Browse API: (a,b,c) = OR. Solo "compralo subito": le aste mostrano il
# prezzo attuale, che non e' quello finale.
EBAY_MARKETPLACES = ["EBAY_IT", "EBAY_DE", "EBAY_GB", "EBAY_US"]
EBAY_QUERIES = [
    "pokemon (full art,alt art,illustration rare,special illustration rare,trainer gallery,galarian gallery)",
    "pokemon (illustrazione rara,rara illustrazione,illustrazione speciale,arte alternativa)",
    "pokemon (japanese,korean,chinese) (ar,sar,sr,chr,csr,art rare)",
    "pokemon (lotto,lot,bundle,joblot) (full art,alt art,ir,sir,illustration rare,art rare)",
]
# A ogni giro cerca anche alcuni Pokémon MANCANTI per nome, a rotazione
# (su EBAY_IT e EBAY_GB). Limite eBay: 5000 ricerche al giorno.
EBAY_ROTATING_PER_RUN = 6
EBAY_ROTATING_MARKETS = ["EBAY_IT", "EBAY_GB"]
EBAY_ROTATING_TERMS = "(full art,illustration rare,art rare,sir,sar,alt art)"

# CardTrader (facoltativo, serve CARDTRADER_TOKEN): ogni quanti giri controllarlo.
CARDTRADER_EVERY_N_RUNS = 1
CARDTRADER_MAX_EXPANSIONS = 40   # espansioni per giro, a rotazione (~160 in tutto: giro completo in 1 ora)

# Siti per cui il nome del venditore NON viene salvato (memoria e dashboard).
NO_PERSIST_SELLER = {"ebay"}

MAX_STORED = 20000               # annunci ricordati (per non riavvisare)
