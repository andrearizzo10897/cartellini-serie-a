# Cartellini Serie A

Pagina `index.html` con arbitri, squadre, tipo di partita, soglie over 3,5 / 4,5 / 5,5 e probabilità di giallo
per ogni giocatore (titolari e panchina) delle prossime partite.

## Come si usa
1. **Doppio clic su `Avvia.bat`** (Windows) o `Avvia.command` (Mac). Si apre la pagina nel browser.
2. Nella pagina premi **Aggiorna**: scarica i dati nuovi, ricalcola e si ricarica da sola.
3. Lascia aperta la finestra nera mentre usi la pagina; chiudila per spegnere tutto.
- Dal **telefono**, a casa e con il telefono sul wifi: usa `Avvia-da-telefono.bat` e apri l'indirizzo che compare nella finestra.
- Il pulsante funziona solo se la pagina è aperta tramite Avvia: se apri `index.html` con doppio clic, il browser non permette di scaricare i dati.
- Quando premere Aggiorna: dopo ogni partita (gialli aggiornati) e circa **1 ora prima** di ogni calcio d'inizio
  (escono le formazioni ufficiali: la pagina passa da "formazione probabile" a "Formazioni ufficiali").
- Senza Avvia, da terminale: `python aggiorna.py --apri`.
- Serve Python con pandas, requests e python-dateutil (già inclusi in Anaconda).

## Struttura
- `aggiorna.py` – lo script principale
- `calcoli.py` – statistiche e probabilità
- `modello.py` – modello di Poisson dei gialli di squadra (quote, falli, livello di lega)
- `presenza.py` – quanto e quando gioca ciascun giocatore: curva oraria dei gialli, sostituzioni, probabilità di entrare
- `backtest.py` – verifica il modello sui gialli di squadra: `python3 backtest.py`
- `backtest_giocatori.py` – verifica le probabilità dei singoli giocatori (calibrazione) e le confronta con le quote DAZN Bet salvate: `python backtest_giocatori.py`
- `tests/` – prove automatiche dei lettori (Sky, SosFanta, DAZN Bet, cache ESPN): `python -m unittest` (offline, meno di un secondo; da rifare dopo ogni modifica ai lettori)
- `pagina.py` – genera `index.html`
- `transfermarkt_passato.json` – copia delle stagioni finite di Transfermarkt (fonte principale dello storico dei giocatori); serve alla pagina online, perché GitHub non può leggere il sito. Si aggiorna da sola sul PC e parte con le quote.
- `fonti/` – un modulo per ogni sito (football-data, Transfermarkt, Kickest, ESPN, dettagli e arbitri ESPN, AIA, API-Football, allenatori,
  DAZN Bet: quota «giocatore ammonito» di ogni giocatore, con valore atteso accanto a P(giallo); se il sito non risponde la colonna resta «–»;
  Sky Sport e SosFanta: formazioni ufficiali, di solito prima di ESPN)
- La scheda «Come funziona» della pagina mostra quale fonte ha risposto a ogni aggiornamento; in alto «Dati di N min fa» avvisa quando la pagina è vecchia.
- `dati/` – dati salvati (cache + `designazioni.json`, lo storico degli arbitri che cresce da solo)
- `.env` – chiave API-Football (non condividerla fuori dalla cerchia di fiducia)

Per condividere con altre persone basta copiare la cartella: serve Python 3 con `pandas` e `requests`.
Le 100 richieste al giorno di API-Football sono in comune a chi usa la stessa chiave, ma ne servono solo 2 in tutto.
