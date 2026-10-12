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
- `pagina.py` – genera `index.html`
- `fonti/` – un modulo per ogni sito (football-data, Kickest, ESPN, AIA, API-Football)
- `dati/` – dati salvati (cache + `designazioni.json`, lo storico degli arbitri che cresce da solo)
- `.env` – chiave API-Football (non condividerla fuori dalla cerchia di fiducia)

Per condividere con altre persone basta copiare la cartella: serve Python 3 con `pandas` e `requests`.
Le 100 richieste al giorno di API-Football sono in comune a chi usa la stessa chiave, ma ne servono solo 2 in tutto.
