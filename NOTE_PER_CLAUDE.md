# Note di passaggio per una nuova sessione di Claude

Progetto: pagina `index.html` con statistiche sui cartellini gialli della Serie A, per le schedine.
Costruito il 12/10/2026. Cartella originale: Scrivania del Mac di lavoro, "Statistiche football".

## Cosa fa
`python server.py` (o Avvia.bat) apre la pagina con il pulsante Aggiorna; `python aggiorna.py --apri` scarica i dati, calcola e rigenera `index.html`. Vedi README.md per la struttura.
Fonti: football-data.co.uk (squadre), ESPN (calendario, formazioni, giocatori 2026/27), Kickest (giocatori 2023-2025,
endpoint interno getStats; il 2026/27 non c'è ancora), API-Football free (arbitri 2023/24 e 2024/25), AIA (designazioni).

## Decisioni e limiti già emersi
- Il piano gratuito di API-Football non dà la stagione in corso: serve solo per l'arbitro del 2023-2024.
- Arbitri: 2023/24 e 2024/25 da API-Football; dal 2025/26 da ESPN (`fonti/arbitri_espn.py`, campo gameInfo.officials, cache compatta in dati/cache/arbitri_espn.json). L'AIA mostra solo l'ultima giornata: `dati/designazioni.json` la accumula per le partite future.
- Backtest del fattore arbitro (k=15) su 2025/26-2026/27: Brier 0,1817 -> 0,1731.
- Contrasti per giocatore solo da Kickest (stagioni passate). Minuti 2026/27 stimati da ESPN.
- Gialli di squadra: regressione di Poisson con ridge in `modello.py` (livello di lega adattivo, effetti squadra, casa, quote 1X2 e falli), x fattore arbitro x fattore tipo di partita.
- Probabilità di giallo del giocatore = 1 - exp(-gialli/90 x k x minuti/90), con riduzione verso la media del ruolo; k è scelto in modo che la somma dei giocatori coincida col totale della squadra (`fattore_riconciliazione`).
- Backtest walk-forward in `backtest.py` (python3 backtest.py, ~1 minuto): il modello del 14/10/2026 ha Brier 0,181 contro 0,193 del precedente su 2025/26-2026/27 (mai usate per tarare), bias +0,01 contro +0,27.
- Verificato e scartato: binomiale negativa/Conway-Maxwell (nessun guadagno stabile), altri parametri (la superficie è piatta: non ritoccarli senza un backtest).
- Le quote future vengono dallo scoreboard ESPN (DraftKings), che le toglie a partita finita; lo storico usa la media dei bookmaker di football-data. Se mancano la partita è trattata come media.
- Non verificabile col backtest: i giocatori prima del 2026/27 (Kickest dà solo totali di stagione). La riconciliazione è stata controllata sulle 60 partite ESPN 2026/27.
- Utente: usa un Mac vecchio al lavoro e un PC Windows con Anaconda a casa. Vuole l'aggiornamento anche da telefono.

## Da fare (idee)
- Pubblicare con GitHub Actions + Pages (workflow già in `.github/workflows/aggiorna.yml`, serve il secret APIFOOTBALL_KEY).
- Eventuale aggiunta di altri campionati. Rifare `python3 backtest.py` dopo ogni modifica al modello e tenerla solo se Brier e log-verosimiglianza migliorano.

## Versione online (attiva dal 12/10/2026)
- Repository pubblico: https://github.com/andrearizzo10897/cartellini-serie-a
- Pagina: https://andrearizzo10897.github.io/cartellini-serie-a/ (si aggiorna da sola ogni 20 minuti, dalle 10 a mezzanotte)
- Il secret APIFOOTBALL_KEY è nei Secrets del repository. Per aggiornare subito a mano: scheda Actions -> "Aggiorna cartellini" -> Run workflow.
- Per modificare il codice: cambia i file in locale, poi git add/commit/push (il push rilancia da solo la pubblicazione al prossimo ciclo).
- Su GitHub gli aggiornamenti programmati si fermano se il repository resta 60 giorni senza attività: basta un commit.

## Giocatori: tempi di gioco, sostituzioni (14/10/2026)
- `presenza.py` stima da `dati/cache/espn_dettaglio.json` (formazioni + minuto di cambi e gialli, 2025/26 e 2026/27):
  curva oraria dei gialli (5% nel primo quarto d'ora, 35% dal 75'), probabilità di essere sostituito per ruolo e giocatore,
  probabilità di entrare per giocatore con vincolo sul numero di cambi della squadra (livello recente 4,96, differenze reali tra squadre).
- `calcoli.ProfiliGiocatori`: gialli attesi in una partita intera (`lam`) misurati sull'"esposizione" (non sui minuti); storico Kickest,
  Transfermarkt come ripiego. `riconcilia_squadra` porta la somma dei giocatori al totale atteso della squadra.
- Test su 58 partite 2026/27 (solo dati precedenti): P(entra) log-loss 0,545 contro 0,586; gialli panchina 1,7% -> 2,3% previsto (reale 2,6%).
  Transfermarkt al posto di Kickest: non migliora (lo usa solo come ripiego, equivale). Nuovi dati Transfermarkt: `fonti/transfermarkt.py`
  (una richiesta ogni 2 secondi, come da robots.txt; prima esecuzione circa 5 minuti).
- Allenatori: `fonti/allenatori.py` e opzione `usa_allenatore` in `modello.py` (SPENTA). Provati: l'effetto allenatore peggiora il backtest
  (Brier 0,1879 -> 0,1892-0,1915) e gli allenatori appena arrivati non hanno residui diversi da zero. Non ripetere senza nuovi dati.
- Storico arbitri Transfermarkt prima del 2023: guadagno < 1% (Brier 0,1811 -> 0,1803), non integrato.
- Siti che bloccano le richieste automatiche e non vanno aggirati: WhoScored, abseits.at, BetExplorer, Goldbet e altri bookmaker.
