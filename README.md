# 🎴 Radar carte Pokémon artistiche

È il gemello del radar delle maglie del Bari. Controlla eBay, Subito, Vinted,
Wallapop e (se vuoi) CardTrader. Quando trova una carta artistica (full art,
IR/AR, SIR/SAR, alt art, Trainer Gallery…) sotto la soglia di prezzo, ti scrive
su Telegram.

## Come decide

- **Che cosa cerca**: le parole di `dati/parole-chiave-carte-pokemon-artistiche.txt`
  e i 1025 nomi di `dati/nomi-pokemon-1025-ricerca.txt` (inglese, italiano,
  giapponese, coreano, cinese). Un nome segnato ⚠ conta solo se nel titolo c'è
  anche un termine della carta.
- **Scarta** gli annunci con una parola della sezione 11: gradate, rovinate,
  disegnate, false, lingue escluse (FR, DE, ES, PT, thai, indonesiano), "cerco",
  e così via. Scarta anche quelli con caratteri thailandesi.
  Le frasi "buone" proteggono la parola cattiva che contengono: "non gradata"
  non viene scartata, "slightly played" non diventa "da verificare".
- **🔎 Da verificare**: c'è una parola della sezione 10 (LP, graffi, curvata…).
  L'annuncio arriva lo stesso, con l'etichetta.
- **Prezzo**: prezzo + spedizione. Se il sito non dice quanto costa la spedizione,
  il radar usa una stima (in `radar/config.py`). Su Vinted conta il prezzo con la
  protezione acquisti.
  - Se il titolo permette di capire **quale carta** è (numero `161/131`, `TG05`,
    oppure sigla del set + numero, es. `BLK 160`), usa le soglie di quella carta
    in `dati/tutte-le-carte-artistiche.csv`. Per una carta italiana vale il
    prezzo dell'edizione inglese; per una coreana o cinese, quello giapponese.
  - Altrimenti confronta con la **carta artistica più economica** di quel
    Pokémon in `dati/cardex-1025-carte-artistiche.csv`.
  - 🚨 **Super affare** (con suono): sotto la soglia del 50% del trend.
    💡 **Buon affare** (senza suono): sotto la soglia del 70%.
  - Sotto il 35% del trend il messaggio ti avvisa: "controlla che non sia falsa".
- **Pokémon mancanti prima**: sono le righe con la colonna `Presa (sì/no)` vuota.
  Per i Pokémon che hai già (scrivi `sì` in quella colonna) arrivano solo i super
  affari. Puoi cambiarlo con `NOTIFY_OWNED` in `radar/config.py`.
- **Lotti**: una parola della sezione 12 più un termine artistico. Il lotto è
  in soglia in tre casi:
  - il prezzo sta sotto la somma delle soglie dei Pokémon mancanti citati nel titolo;
  - il prezzo a carta sta sotto i 2 € (super affare sotto 1 €), quando il titolo
    dice quante carte ci sono;
  - altrimenti, se costa meno di 40 €, arriva come "📦 lotto da valutare".
- **Stesso venditore**: più annunci in soglia dello stesso venditore arrivano in
  **un unico messaggio**, con il totale e una sola spedizione. Il messaggio dice
  anche se quel venditore ha altri annunci in soglia già segnalati negli ultimi
  7 giorni.
- Ogni annuncio arriva una volta sola. Torna solo se il prezzo scende a un
  livello migliore, per esempio da "buon affare" a "super affare".

## Primo avvio (10 minuti)

1. **Python** è già installato sul PC (è lo stesso del radar del Bari).
   Apri questa cartella, scrivi `cmd` nella barra degli indirizzi e premi Invio. Poi:
   ```
   pip install -r requirements.txt truststore
   ```
2. **Bot Telegram**. Puoi usare lo stesso bot del Bari oppure crearne uno nuovo
   con @BotFather (`/newbot`, per esempio "Radar carte"). Il token e il chat id si
   trovano come spiegato nel README del radar del Bari.
3. Apri `.env` con il Blocco note e scrivi il token dopo `TELEGRAM_BOT_TOKEN=`.
   Scrivi "ciao" al bot su Telegram, poi fai doppio clic su `trova-chat-id.bat`:
   il chat id viene trovato e scritto nel `.env` da solo.
   Se vuoi eBay, aggiungi anche `EBAY_CLIENT_ID` e `EBAY_CLIENT_SECRET`: vanno
   bene le stesse chiavi del radar del Bari.
4. **Prova**: doppio clic su `prova-telegram.bat`. Parte il test automatico e
   arrivano su Telegram due notifiche finte, segnate [PROVA]: un super affare e un
   gruppo di 3 annunci dello stesso venditore. Senza `.env` le stampa a video.
5. **Avvio**: doppio clic su `avvia-radar.bat`. Il radar fa un giro ogni 15
   minuti finché la finestra resta aperta. Il primo giro può mandare parecchi
   messaggi (al massimo 20, poi un riepilogo).

Da riga di comando:
```
python -m radar.main --dry-run      # un giro, stampa i messaggi senza mandarli
python -m radar.main                # un giro
python -m radar.main --ogni 15      # un giro ogni 15 minuti
python -m radar.main --only vinted  # solo alcuni siti (ebay, subito, vinted, wallapop, cardtrader)
python -m tests.test_matching       # test dei filtri
```

## Farlo girare su GitHub (anche a PC spento)

Come il radar del Bari: GitHub Actions lo fa girare ogni 15 minuti
(`.github/workflows/radar.yml`) e salva la memoria in `data/` con un commit.
- Le password stanno nei *secret* del repository (Settings → Secrets and
  variables → Actions): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` e, se li
  hai, `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `CARDTRADER_TOKEN`.
- **Quando gira su GitHub non avviare anche `avvia-radar.bat`**, altrimenti ricevi i
  messaggi due volte.
- Se cambi i file in `dati/` (per esempio segni le carte prese), devi
  ricaricarli su GitHub perché il radar li veda.
- GitHub sospende i workflow pianificati dopo 60 giorni senza attività. Il radar fa un
  commit a ogni novità, quindi di norma resta attivo. Se si ferma, riattivalo da *Actions*.

## Personalizzare

- **Parole e nomi**: modifica i file in `dati/`. Basta aggiungere o togliere
  righe, senza cambiare i titoli delle sezioni (`# 11. PAROLE DA ESCLUDERE…`).
- **Carte che hai già**: in `dati/cardex-1025-carte-artistiche.csv` scrivi `sì`
  nella colonna `Presa (sì/no)`. Excel va bene: salva come "CSV UTF-8".
- **Ricerche sui siti, spedizioni stimate, soglie dei lotti**: `radar/config.py`.
- **Prezzi**: sono i prezzi Cardmarket dell'11/11/2026. Per aggiornarli,
  rigenera i due CSV con le stesse colonne.

## Cosa trovi in `data/`

- `affari.json`: gli annunci in soglia segnalati, i più recenti per primi.
- `siti.json`: lo stato di ogni sito all'ultimo giro (ok / errore / saltato).
- `stato.json`: la memoria del radar. Se lo cancelli, ti riavvisa di tutto.

## Limiti da conoscere

- **Cardmarket** non dà più accesso alle API a nuovi utenti e blocca i robot.
  Usa la sua **lista desideri** (Wants), che trova da sola la combinazione di
  venditori più economica.
- **CardTrader**: il radar usa l'API ufficiale (`CARDTRADER_TOKEN`, ogni 4 giri).
  Questa parte è scritta ma **non ancora provata con un token vero**. Se dà
  errore lo vedi in `data/siti.json`, e gli altri siti continuano a funzionare.
  Anche CardTrader ha la sua lista desideri e **CardTrader Zero**, che raccoglie
  più venditori in una sola spedizione.
- **Subito** blocca chi fa troppe ricerche: durante la prova del 12/11/2026 ha
  risposto "403" (accesso negato). Il radar va avanti con gli altri siti. Per Subito puoi
  usare anche le "ricerche salvate" con notifica nell'app.
- **Catawiki** e i **gruppi Facebook** non si possono leggere in automatico.
  Per Catawiki salva una ricerca e ricevi le email. Su Facebook attiva le
  notifiche dei gruppi.
- **Vinted** nella ricerca non mostra il venditore: il radar apre la pagina
  dell'annuncio solo per quelli in soglia (al massimo 15 per giro).
- eBay: solo annunci "Compralo Subito". Le aste mostrano il prezzo del momento,
  che non è quello finale. Se l'annuncio parte da fuori UE, il messaggio
  ricorda che potresti pagare la dogana.
- Il radar legge **solo il titolo** (e la condizione dichiarata). Prima di
  comprare guarda sempre le foto fronte/retro: lo spiega
  `dati/guida-acquisto-carte-artistiche.md`.
