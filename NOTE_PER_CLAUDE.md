# Note di passaggio per una nuova sessione di Claude

Progetto: pagina `index.html` con statistiche sui cartellini gialli della Serie A, per le schedine.
Costruito il 12/10/2026. Cartella originale: Scrivania del Mac di lavoro, "Statistiche football".

## Cosa fa
`python server.py` (o Avvia.bat) apre la pagina con il pulsante Aggiorna; `python aggiorna.py --apri` scarica i dati, calcola e rigenera `index.html`. Vedi README.md per la struttura.
Fonti: football-data.co.uk (squadre), ESPN (calendario, formazioni, giocatori 2026/27), Kickest (giocatori 2023-2025,
endpoint interno getStats; il 2026/27 non c'è ancora), API-Football free (arbitri 2023/24 e 2024/25), AIA (designazioni).

## Decisioni e limiti già emersi
- Il piano gratuito di API-Football non dà la stagione in corso: serve solo per l'arbitro del 2023-2024.
- Arbitro 2025/26 non disponibile gratis. L'AIA mostra solo l'ultima giornata: `dati/designazioni.json` la accumula.
- Contrasti per giocatore solo da Kickest (stagioni passate). Minuti 2026/27 stimati da ESPN.
- Probabilità di giallo = 1 - exp(-gialli/90 x fattori x minuti/90), con riduzione verso la media del ruolo.
- Il modello non è stato calibrato su risultati reali: andrebbe fatto un backtest.
- Utente: usa un Mac vecchio al lavoro e un PC Windows con Anaconda a casa. Vuole l'aggiornamento anche da telefono.

## Da fare (idee)
- Pubblicare con GitHub Actions + Pages (workflow già in `.github/workflows/aggiorna.yml`, serve il secret APIFOOTBALL_KEY).
- Backtest del modello; eventuale aggiunta di altri campionati.
