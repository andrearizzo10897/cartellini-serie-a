#!/usr/bin/env python3
"""Scarica le quote DAZN Bet dal PC e le pubblica su GitHub, così compaiono anche nella pagina online.

I server di GitHub non riescono a leggere il sito di DAZN Bet, quindi le scarica questo PC e le salva in
quote_daznbet.json; il workflow online le legge da lì al prossimo aggiornamento (entro 20 minuti).
Di solito non serve lanciarlo a mano: lo fanno aggiorna.py (a ogni aggiornamento dal PC) e server.py
(ogni 30 minuti mentre Avvia è aperto).
Uso a mano:  python pubblica_quote.py
Ogni controllo fa un commit con l'orario aggiornato (ora italiana).
"""
import subprocess
import sys

import config
from fonti import daznbet


def git(*args):
    r = subprocess.run(["git", *args], cwd=config.BASE, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("git {}: {}".format(" ".join(args), (r.stderr or r.stdout).strip()))
    return r.stdout


def pubblica(nuove):
    """Salva `nuove` (quote scaricate ora) in quote_daznbet.json e le pubblica. Restituisce un messaggio."""
    daznbet.salva(nuove)  # l'orario cambia a ogni controllo, quindi c'è sempre qualcosa da pubblicare
    git("add", daznbet.FILE.name)
    if not git("status", "--porcelain", "--", daznbet.FILE.name).strip():
        return "Quote DAZN Bet già pubblicate."
    git("commit", "-m", "Quote DAZN Bet: {} partite".format(len(nuove)), "--", daznbet.FILE.name)
    git("push", "origin", "main")  # se GitHub è avanti si ferma qui: niente rebase automatici su un albero con altre modifiche
    return "Pubblicate le quote DAZN Bet di {} partite.".format(len(nuove))


def main():
    try:
        nuove = daznbet.scarica_quote()
    except Exception as e:  # noqa: BLE001 - rete, JSON, formato: in ogni caso non si pubblica nulla
        print("DAZN Bet non risponde ({}): non pubblico nulla.".format(e))
        return 1
    if not nuove:
        print("Nessuna quota DAZN Bet trovata: non pubblico nulla.")
        return 1
    try:
        print(pubblica(nuove))
    except RuntimeError as e:
        print("Quote scaricate ma non pubblicate: {}".format(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
