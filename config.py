"""Percorsi e impostazioni generali."""
from datetime import datetime
from pathlib import Path

from dateutil import tz

BASE = Path(__file__).resolve().parent
DATI = BASE / "dati"
CACHE = DATI / "cache"
OUTPUT = BASE / "index.html"


def stagione_di(d):
    """Anno di inizio della stagione a cui appartiene una data (2026 = 2026/27)."""
    return d.year if d.month >= 7 else d.year - 1


def adesso():
    """Ora attuale in Italia (anche sui server di GitHub, che usano l'ora UTC)."""
    return datetime.now(tz.gettz("Europe/Rome")).replace(tzinfo=None)


STAGIONE_CORRENTE = stagione_di(adesso().date())
STAGIONI_STORICO = [STAGIONE_CORRENTE - 3, STAGIONE_CORRENTE - 2, STAGIONE_CORRENTE - 1, STAGIONE_CORRENTE]
# Lo storico parte dal 2023/24 come richiesto: se la stagione corrente cambia, si sposta in avanti
STAGIONI_STORICO = [s for s in STAGIONI_STORICO if s >= 2023]

# Quante partite considerare per la "forma recente"
FORMA_BREVE = 5
FORMA_LUNGA = 10

# Pesi con cui le stagioni pesano sul profilo di un giocatore (la più recente conta di più)
PESO_STAGIONE = {0: 1.0, 1: 0.8, 2: 0.5, 3: 0.3}  # distanza dalla stagione corrente
MINUTI_PRIOR = 900  # "minuti virtuali" con cui si tira il giocatore verso la media del suo ruolo


def leggi_env():
    """Legge le variabili dal file .env (chiave API-Football)."""
    percorso = BASE / ".env"
    valori = {}
    if percorso.exists():
        for riga in percorso.read_text(encoding="utf-8").splitlines():
            riga = riga.strip()
            if riga and not riga.startswith("#") and "=" in riga:
                k, v = riga.split("=", 1)
                valori[k.strip()] = v.strip().strip('"').strip("'")
    return valori
