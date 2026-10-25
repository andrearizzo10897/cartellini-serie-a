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

## Sessione del 25/10/2026: dati, formazioni ufficiali, verifica dei giocatori
- **Cache ESPN**: `espn.formazioni(id, 'post')` tiene il file per sempre, ma solo se salvato a partita finita (`espn.finita`, stato nell'header).
  Prima 8 partite su 78 avevano gialli sbagliati (Bologna-Inter 0 invece di 7...: 26 gialli mancanti) perché salvate prima del fischio o durante.
  `espn_dettaglio` ha ora il campo `finita` e rifà le voci vecchie. Controllo utile: `controllo gialli ESPN vs football-data` stampato da aggiorna.py
  (deve dare quasi tutte «uguali»; restano 2 partite con gialli mancanti in ESPN stessa: Roma-Atalanta, Genoa-Frosinone).
- **Giorni letti da ESPN**: tutti i giorni dopo l'ultimo dato di football-data (che ritarda anche di 6 giorni), non solo ieri e oggi.
- **Ultima formazione**: ESPN a volte manda una squadra senza giocatori (Roma-Genoa 17/10): non deve cancellare l'ultima buona (`aggrega_espn`).
- **Formazioni ufficiali**, in ordine: ESPN, Sky (`fonti/sky.py`), SosFanta (`fonti/sosfanta.py`, articolo «formazioni-ufficiali-casa-trasferta», blocco «LE FORMAZIONI UFFICIALI»,
  senza modulo), poi l'ultima schierata. Sky ha due pagine: `.../formazioni` (tabella con numero di maglia e link `/atleti/<nome-completo>/<id>` per ogni giocatore;
  «probabili» con soli titolari, poi «ufficiali» con anche la panchina vera) e `.../risultato-gol` (la diretta, che pubblica per prima gli undici in testo con i soli cognomi).
  Se la tabella è ufficiale si legge da lì (nomi completi, nessuna ambiguità); altrimenti si usa il testo della diretta e i soprannomi si traducono con i nomi completi
  della stessa tabella (anche quella probabile) o con `SOPRANNOMI` (Pote = Pedro Gonçalves). Abbinamento alla rosa ESPN: `sky._trova` (cognomi) e `sky._trova_completo`
  (nome completo; a parità numero di maglia o portiere). **Un nome che non si riconosce con certezza fa scartare la fonte: non si indovina.** Provato e scartato:
  ricavarlo «per esclusione» tra i titolari abituali (prova su 78 partite con soprannomi finti: se il giocatore è un titolare fisso 99% giusto, ma se ruota sbaglia quasi sempre,
  e dalle liste non si distingue: precisione complessiva 66% con un solo nome sconosciuto, 33% con due). I test in `tests/` coprono i formati visti (spazio prima dei due punti, ecc.).
- **Test dei giocatori** (`backtest_giocatori.py`, 78 partite 2026/27, solo dati precedenti): ammoniti previsti 239 contro 255 reali, calibrazione buona per fascia;
  una ricalibrazione logistica NON migliora (leave-one-day-out). Brier 0,0599 contro 0,0605 della media per ruolo: lo storico del singolo aggiunge poco.
  Con le quote (17 partite, 55 ammoniti): modello log-loss 0,266 contro 0,288 del mercato ripulito; campione troppo piccolo per concludere.
- **Quote DAZN Bet «ammonito»**: margine enorme (1/q medio ~20% contro 8-11% reale): puntando su tutti si perde il 46-58%. Valore atteso > 0 rarissimo (8 su 644).
- **Workflow su GitHub**: i cron `*/10` e `*/20` rendono lo stesso, ~2 avvii all'ora (25-31 al giorno), mediana 32 minuti. Non è un problema di orario:
  GitHub scarta gli avvii programmati. L'unico modo per avere di più è lanciarlo da fuori (workflow_dispatch con un token) – non fatto.
  Un giro dura circa 1-2 minuti. Nella pagina online non c'è alcun token (il pulsante Aggiorna è solo nascosto, `.az{display:none}`).
- Pagina: pillola «Dati di N min fa» (verde < 45 min, gialla fino a 3 h, rossa oltre) con pulsante Ricarica (cache-busting `?r=`), riquadro «Fonti di questo aggiornamento».
- **Storico dei giocatori (25/10/2026)**: Transfermarkt è la fonte primaria (2022/23-2025/26, ~96-97% dei gialli di ogni stagione), Kickest la riserva e l'unica
  per falli e contrasti (`config.FONTE_PRIMARIA`, `ProfiliGiocatori(primaria=...)`; il ruolo resta quello di Kickest perché le medie per ruolo sono calcolate con i suoi).
  Con il backtest dei giocatori le due scelte rendono uguale (log-loss 0,2213 in entrambi i casi). Prima, per chi era solo in Transfermarkt, i falli/90 erano sbagliati (minuti di TM, falli solo di quest'anno).
- **Transfermarkt non risponde ai server di GitHub**: le stagioni finite sono in `transfermarkt_passato.json` (nel repository, fuori da dati/); su GitHub si legge solo quello,
  sul PC si legge il sito e il file si riscrive solo se i dati cambiano (e parte con `pubblica_quote.py`). A ogni cambio di stagione servirà un giro dal PC per aggiungere la stagione finita.
- **Collegamento ESPN -> storico per nome** (`calcoli._Collegamento`): il cognome (ultima parola) deve comparire nell'altro nome. Prima bastava lo stesso nome di battesimo nella
  stessa squadra (punteggio 0,63 > soglia 0,55): Comotto prendeva lo storico di Pulisic, Mitaj quello di Balotelli ecc. (27 giocatori distinti nelle prime 20 partite).
- **Stagione in corso, ESPN o altro**: ESPN resta la fonte (partita per partita, formazioni, minuto di cambi e cartellini; funziona anche da GitHub). Confronto con Transfermarkt 2026/27:
  255 gialli in entrambi, uguali per 490 giocatori su 498 (TM ha 7 gialli in più su panchinari che ESPN non attribuisce). Kickest 2026/27 non è ancora pubblicato; TM non è raggiungibile da GitHub
  e non ha il minuto dei cambi. Non servono altre fonti.

