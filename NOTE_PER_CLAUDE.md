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
- **Quote DAZN Bet «ammonito»**: margine enorme (5/11/2026, 33 partite: 1/q medio 21% contro 8,3% reale, puntando su tutti -62%). Vedi la sezione del 5/11: sui soli titolari il modello non batte il mercato.
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


## Sessione del 29/10/2026: pagina «Giocatori», cartellini giornata per giornata
- **Scheda «Giocatori»** (`pagina.sezione_giocatori`, dati da `calcoli.cartellini_giornate`): una riga per giocatore sceso in campo (o ammonito) nel 2026/27, una colonna per giornata.
  Pallino giallo / rosso (anche doppio giallo) / vuoto = in campo senza cartellini / puntino = la sua squadra ha giocato ma lui no / niente = giornata non ancora giocata.
  Toccando una riga: partite e minuti dei cartellini. Filtri: squadra, «Più ammoniti» (tutte le squadre in classifica), ricerca senza accenti.
- I dati vanno nella pagina come JSON compatto (`#gg-dati`, ~50 KB) e la griglia la disegna il JS alla prima apertura della scheda: in HTML sarebbero ~19.000 elementi.
- **Telefono** (fino a 640 px): metà stagione per volta (1ª–19ª / 20ª–38ª, di partenza quella in corso) con pallini da ~10 px e nomi corti («L. Martínez»); «Tutte» mostra le 38
  fitte (~5 px). In orizzontale, su tablet e computer sempre tutte le 38. Campi di ricerca a 16 px (sotto, iOS ingrandisce la pagina). Sul telefono si ridisegna solo se cambia la larghezza.
- **Numero della giornata** (`calcoli.numera_giornate`): ESPN non lo dà. Data tipica di ogni giornata = mediana delle partite in cui le due squadre sono entrambe alla n-esima partita;
  poi, dalla partita più vicina alla data tipica, ognuna va nella giornata più vicina se le squadre sono libere; recuperi e anticipi nella giornata dove mancano entrambe
  (prima quelle passate) e, se non c'è posto, si sposta la partita che lo occupa. Calendari ufficiali 2023/24 e 2024/25 (API-Football, in `tests/fixtures/calendari_serie_a.json`):
  0 errori, anche rifacendo il calcolo giorno per giorno con le sole partite note (finite + 8 giorni). Scartati: blocchi di date consecutive (125 errori su 380) e centri senza
  lo spostamento (giusto sulle stagioni intere ma non sul 2025/26: Supercoppa a dicembre, Milan-Como della 24ª giocata il 18/02 per le Olimpiadi a San Siro).
- **Doppio giallo**: ESPN azzera il giallo, segna il rosso e lascia l'evento del primo giallo (stato "d"). I conteggi della pagina sono quelli di ESPN, come nelle tabelle delle partite.
- **Minuto nel recupero**: ESPN ferma `clock.value` a 45:00/90:00 (46 cartellini su 287 nel 2026/27); `espn_dettaglio.compatta` salva anche `clock.displayValue` («90'+4'») nel campo
  "testo". Le voci vecchie dell'archivio senza "testo" si rifanno dal file completo in cache (niente rete); quelle senza file restano come sono (minuto dal tempo di gioco).
- **Giallo e poi rosso diretto** (Gaspar, Lecce-Juventus): ESPN conta tutti e due (gialli 1, rossi 1). Pallino rosso, ma il dettaglio elenca anche il giallo e il totale lo conta.
- Totali nella testata di ogni squadra = cartellini presi con quella squadra (dai dati delle partite), non la somma di chi ci gioca adesso.
- Revisione separata (code-reviewer) prima del commit: corretti anche `<` nel JSON (`\u003c`), pallini senza `aspect-ratio`/`inset` (iPhone vecchi), ridisegno dopo una rotazione
  fatta con un'altra scheda aperta, partita rifatta con un nuovo id ESPN (giornata cercata anche per coppia di squadre). Disegno: ~0,1 s con CPU 4 volte più lenta (prima 0,7-1,4 s).

## 31/10/2026: aggiornamento del PC fermo per una risposta vuota di ESPN
- Alle 12:51 Avvia non ha aggiornato: il calendario ESPN del giorno è arrivato con il codice 200 ma vuoto (`JSONDecodeError: Expecting value: line 1 column 1`),
  `espn.partite_del_giorno` non lo gestiva e si fermava tutto. La pagina locale restava al 29/10, «Ricarica» rileggeva lo stesso file e il server riprovava solo dopo 30 minuti.
  L'errore si legge nella finestra nera di Avvia (letto con AttachConsole + ReadConsoleOutputCharacterW, script `leggi_console.py` nella cartella temporanea di quella sessione).
- `utils.scarica_json`: riprova anche le risposte vuote o troncate (usato da `espn` e `espn_dettaglio`). `partite_del_giorno` usa l'ultima copia salvata del giorno se ESPN
  continua a non rispondere; senza copia si ferma come prima (meglio la pagina vecchia che una con giorni mancanti).
- `server.py`: dopo un aggiornamento non riuscito riprova dopo 3 minuti, poi 10, poi ogni 30 (`attesa_dopo`). Vale dal prossimo avvio di Avvia.

## 01/11/2026: arbitri della domenica spariti (10ª giornata)
- La pagina AIA della 10ª giornata (ID 28806) per le cinque partite di domenica 1/11 scriveva solo l'ora («h. 12.30»), senza «Domenica 01/11»: `aia._interpreta`
  voleva il giorno nella riga dopo le squadre e le saltava (archivio con 5 partite su 10, «da designare» nella pagina). Ora accetta anche la sola ora e prende la data
  della partita prima (il giorno dopo se l'ora è più presto). Test con la pagina vera in `tests/fixtures/aia_designazioni_10a_giornata.html`.

## 05/11/2026: revisione critica (agente critic) e correzioni
- **Valore atteso**: `calcoli.motivo_senza_ev` lo nasconde se la formazione è probabile, se le quote hanno più di `QUOTE_MAX_ORE` (2) o sono scaricate più di `QUOTE_PRIMA_DEL_FISCHIO_MIN` (90) prima
  del fischio, o a partita iniziata. Verde solo se positivo anche con `PRUDENZA_EV` (p x 0,8). Motivo: solo il 74,7% dei titolari dell'ultima partita riparte titolare (dato del critico).
- **Confronto col mercato** (`backtest_giocatori.py`, 33 partite con quote, 1207 giocatori): tutti log-loss 0,2545 contro 0,2812, ma **solo titolari 0,3878 contro 0,3902**: il vantaggio veniva dal sapere chi è in
  panchina, il mercato quota uguale chi non gioca. EV > 0 sui titolari: 12 puntate, 2 vinte, -25%; con p x 0,8: 1 puntata, 0 vinte. Nessuna prova che l'EV funzioni. Calibrazione 100 partite: 305 previsti contro 319 reali, Brier 0,0583 contro 0,0593.
- **Squalifiche** (`calcoli.squalificati`, tolti solo dalla formazione probabile): soglie verificate sul 2025/26: assenti la partita dopo il 97% al 5° giallo (97 casi) e il 100% al 10° (5 casi), 0-6% agli altri. 14° e 17° in `config.SOGLIE_SQUALIFICA`
  sono a memoria, MAI osservati: da verificare col regolamento. Squalifiche di più giornate e gialli portati dalla stagione prima non sono noti.
- **Tipo di partita**: il fattore è tolto (solo informativo). Rifatto walk-forward dal critico su 480 partite: Brier -0,0005, IC [-0,0020;+0,0010]. Non rifatto da me.
- **Riquadro fonti**: «ok» solo se il dato serve così com'è. Arbitro mancante entro 24 ore (non 48: l'AIA pubblica anche il giorno prima), calendario da copia salvata o nessuna quota = «no» e avviso in cima a Partite. Ufficiali mancanti a 45 minuti, errori Sky/SosFanta (`sky.problemi`, distinti da «non pubblicato»), gialli ESPN/football-data diversi, push rifiutato = «att».
- **ESPN non dà più l'arbitro** (50 partite su 100 del 2026/27, ricontrollato scaricando di nuovo: `officials` assente): lo storico dipende dall'AIA, quindi `dati/designazioni.json` ora parte con le quote (`pubblica_quote`). Se GitHub perde la cache riparte da quel file.
- **File**: `utils.scrivi_testo`/`scrivi_json` atomici, `leggi_json_o` per le letture che non devono fermare il giro. **Server**: `ServerUnico` senza SO_REUSEADDR su Windows e bind prima dell'aggiornamento: un secondo Avvia apre la pagina e si ferma.
- **Sky**: due omonimi nello stesso ruolo = None. **DAZN**: ogni riga a un solo giocatore; `carica` non si ferma se cambia il formato. **Kickest**: `ProfiliGiocatori` ignora la stagione in corso. **Workflow**: `requirements.txt` fisso (versioni risolte per Python 3.11), niente token iniettato e niente `--short`; il cron non è stato toccato.
- **Aperto**: regole DAZN su chi non entra (per i panchinari cambia la formula: oggi è prudente, P(entra) x P(giallo se entra)); non trovate in rete, da leggere sul sito.
- **Dopo la revisione del codice**: gli archivi che non si ricostruiscono (`designazioni.json`, `arbitri_espn.json`, `espn_dettaglio.json`) NON usano `leggi_json_o`: bloccati o rovinati fermano il giro, altrimenti un archivio vuoto si salverebbe sopra a quello vero e partirebbe online. La squalifica vale solo per la prossima partita della squadra (`calcoli.formazioni_per_partita`, nella finestra di 8 giorni possono essere due). Il valore atteso scade anche nella pagina aperta: il JS lo nasconde a partita iniziata o con dati oltre 45 minuti. L'alias Sky non decide fra omonimi.
- **`--short` tolto da staticrypt**: la password attuale è lunga, quindi va bene; con una password sotto i 14 caratteri staticrypt chiede conferma, non scrive `site/` e il giro fallisce (pagina vecchia online).
- **Riferimento per i cartellini: tabellino Lega Serie A** (`legaseriea.it/serie-a/match/<id>/<casa>-vs-<trasf>`, dal calendario `serie-a/calendario-risultati`; risponde solo a un browser vero). Il 5/11 coincide con ESPN su Roma-Atalanta, Genoa-Frosinone, Lecce-Juventus, Lazio-Cagliari, Juventus-Napoli: il doppio giallo non conta come giallo, solo come rosso. football-data conta i due gialli (e su Roma-Atalanta ha un giallo in più alla Roma). `calcoli.controllo_espn` tiene conto dei doppi gialli e segnala solo le differenze vere, con i numeri. Lo storico da football-data resta non omogeneo con le partite recenti da ESPN: differenza piccola, non corretta.
- **ESPN corregge i cartellini dopo la partita**: Gaspar (Lecce-Juventus): copia di GitHub 0 gialli + rosso (sembrava doppio giallo), copia del PC salvata 4 giorni dopo 1 giallo + rosso, come la Lega. Unica differenza su 497 giocatori fra PC e online il 5/11. `espn._da_rileggere`: una copia salvata entro 24 ore dal calcio d'inizio si rilegge una volta, dopo le 24 ore. Il dettaglio compatto (`espn_dettaglio`) non si rifà: i cartellini della pagina vengono da `formazioni`. Se l'avviso su Lecce-Juventus resta dopo il primo giro online, GitHub non conserva la data dei file nella cache: da ricontrollare.

## 06/11/2026: ufficiali di Venezia-Udinese non prese
- SosFanta ha cambiato indirizzo: `/squadra/<squadra>/<casa>-<trasf>-formazioni-ufficiali-fantacalcio/` (il blocco di testo è lo stesso, con «:»). Il programma cercava solo `/news/formazioni-ufficiali-...` e il riquadro diceva «non hanno ancora pubblicato». Ora nessun indirizzo è fisso: `sosfanta._articoli` prende dagli elenchi e dalla ricerca del sito (`?s=`) qualunque link il cui ultimo pezzo contiene «ufficial» e le due squadre nell'ordine casa-trasferta; `ufficiali` scarta gli articoli non del giorno della partita (testo «6 novembre» o data ISO).
- Refuso nell'articolo («Abakwah»): `sky._trova` accetta una lettera di differenza solo su parole di almeno 5 lettere e se il giocatore possibile è uno solo. ESPN può avere gli undici di una sola squadra: ora si usano per quella squadra, con la partita sempre «probabile».
- Ancora debole: un cambio di formato delle fonti che non dà errore sembra «non pubblicato»; l'avviso «att» a 45 minuti dal fischio è il solo segnale.
