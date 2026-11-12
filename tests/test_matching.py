"""Esegui con:  python -m tests.test_matching"""
from radar import matching
from radar.main import analyze, group_key

# (titolo, prezzo totale) -> livello atteso
DEALS = {
    ("Bulbasaur IR 166/165 151 inglese near mint", 20): "super",
    ("フシギダネ AR M1L 064/063", 4.0): "buono",
    ("Charizard full art non gradata", 3): "super",          # "non gradata" non scarta
    ("Mewtwo slightly played full art", 2): "super",          # "slightly played" non e' da verificare
    ("Lotto 30 carte pokemon full art e IR", 40): "buono",    # 1,33 € a carta
    ("Lotto full art Pikachu Eevee Snorlax", 5): "super",
    ("Umbreon VMAX alt art Evoluzioni Eteree 215", 900): "super",
    ("ブラッキー SAR", 10): "super",                           # giapponese, riferimento cardex
}
CHECK = {
    "Pidgeot ex SIR lightly played": ["lightly played"],
    "Charizard full art graffi": ["graffi"],
}
DROP = [
    "Carta Pokemon Mew ex SIR 151 PSA 10",               # gradata
    "Charizard full art PSA 9",
    "Pikachu illustration rare francese",                # lingua esclusa
    "Glurak ex full art",                                # nome tedesco
    "Umbreon VMAX alt art 215/203 heavily played",       # rovinata
    "Charizard alt art proxy",                           # falso
    "Gengar full art custom art",                        # alterata
    "Pikachu SIR ภาษาไทย",                               # thailandese
    "Cerco Umbreon alt art",                             # chi compra
    "Lotto energie base full art",                       # lotto inutile
    "Golem vintage",                                     # nome ambiguo senza termini carta
    "Gengar ex Japanisch 30th Anniversary",              # nessun termine artistico, carta non riconosciuta
    "Raihan full art 202/203",                           # allenatore, nessun Pokémon
]


def main():
    bad = 0
    for (title, price), want in DEALS.items():
        v = matching.evaluate(matching.classify(title), price)
        got = v and v["level"]
        if got != want:
            bad += 1
            print(f"ATTESO {want!r}, OTTENUTO {got!r}: {title}")
    for title, want in CHECK.items():
        info = matching.classify(title)
        if info.excluded or info.check != want:
            bad += 1
            print(f"DA VERIFICARE atteso {want}, ottenuto {info.check} / {info.excluded!r}: {title}")
    for title in DROP:
        v = matching.evaluate(matching.classify(title), 0.5)
        if v:
            bad += 1
            print(f"DOVEVA ESSERE SCARTATO: {title} -> {v['level']}")

    # eBay: condizione "Graded" scarta; spedizione sommata al prezzo
    graded = {"native_id": "ebay:1", "title": "Umbreon ex 161/131 SIR", "url": "u", "price": 10,
              "currency": "EUR", "shipping": 2, "platform": "ebay", "condition": "Graded"}
    if analyze(graded):
        bad += 1
        print("DOVEVA ESSERE SCARTATO: condizione Graded")
    ok = dict(graded, condition="Ungraded")
    a = analyze(ok)
    if not a or a["total"] != 12 or a["ship_estimated"]:
        bad += 1
        print("Prezzo + spedizione sbagliato:", a and a["total"])
    # stesso venditore -> stesso gruppo; senza venditore -> gruppi separati
    if group_key({"platform": "ebay", "seller": "x", "native_id": "1"}) != \
            group_key({"platform": "ebay", "seller": "x", "native_id": "2"}):
        bad += 1
        print("Raggruppamento per venditore non funziona")

    total = len(DEALS) + len(CHECK) + len(DROP) + 3
    print(f"\n{total - bad}/{total} controlli superati")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
