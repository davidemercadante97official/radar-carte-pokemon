"""Richieste HTTP con header da browser, timeout e piccoli ritardi."""
from __future__ import annotations

import random
import time

import requests

try:  # sul PC di casa usa i certificati di Windows (antivirus che filtrano HTTPS)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
    })
    return s


def get(s: requests.Session, url: str, **kw) -> requests.Response:
    kw.setdefault("timeout", 25)
    for attempt in range(3):
        r = s.get(url, **kw)
        if r.status_code not in (429, 503) or attempt == 2:
            break
        # il sito chiede di rallentare: aspettiamo quanto dice (max 30 s)
        wait = r.headers.get("Retry-After", "")
        time.sleep(min(int(wait) if wait.isdigit() else 8 * (attempt + 1), 30))
    r.raise_for_status()
    time.sleep(random.uniform(0.6, 1.4))   # non martelliamo i siti
    return r


def to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    txt = str(value).replace("\xa0", " ").replace("€", "").replace("EUR", "").strip()
    txt = "".join(c for c in txt if c.isdigit() or c in ".,")
    if not txt:
        return None
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").replace(",", ".") if txt.rfind(",") > txt.rfind(".") else txt.replace(",", "")
    elif "," in txt:
        txt = txt.replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return None
