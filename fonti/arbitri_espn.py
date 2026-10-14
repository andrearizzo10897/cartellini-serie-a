"""Arbitri da ESPN: il campo "officials" nel dettaglio di ogni partita.

Serve per le stagioni che API-Football (piano gratuito) non dà, cioè dal 2025/26 in poi.
Per ogni partita finita si salva solo il nome dell'arbitro in dati/cache/arbitri_espn.json,
quindi dopo la prima esecuzione (circa 480 richieste) si scaricano solo le partite nuove.
"""
import pandas as pd

from config import CACHE
from fonti import espn, espn_dettaglio
from fonti.api_football import STAGIONI_GRATIS
from utils import leggi_json, scrivi_json

ARCHIVIO = CACHE / "arbitri_espn.json"


def _arbitro_partita(id_partita):
    """Arbitro di una partita finita (stesso scaricamento dei dettagli: ESPN si interroga una volta sola)."""
    return espn_dettaglio.dettaglio(id_partita).get("arbitro")


def _allinea(nome, noti):
    """ESPN scrive "J. Luca Sacchi", API-Football "J. Sacchi": se iniziale e cognome coincidono con un solo
    nome già noto, uso quello, così lo storico dell'arbitro non si spezza in due."""
    if nome in noti or not noti:
        return nome
    iniziale, cognome = nome[:2], nome.split()[-1]
    candidati = [n for n in noti if n[:2] == iniziale and n.split()[-1] == cognome]
    return candidati[0] if len(candidati) == 1 else nome


def carica(fd, finite, anno_corrente, noti=()):
    """DataFrame (stagione, casa, trasf, arbitro) per le stagioni senza dati API-Football.

    fd: partite di football-data (le date delle giornate); finite: partite finite della stagione in corso
    già lette da ESPN come (evento, formazioni).
    """
    archivio = leggi_json(ARCHIVIO) if ARCHIVIO.exists() else {}
    nuovi = 0
    eventi = []   # (stagione, evento)
    for anno in sorted(int(a) for a in fd["stagione"].unique()):
        if anno in STAGIONI_GRATIS:
            continue
        if anno == anno_corrente:
            eventi += [(anno, ev) for ev, _ in finite]
            continue
        for giorno in sorted(set(fd[fd["stagione"] == anno]["data"].dt.date)):
            eventi += [(anno, ev) for ev in espn.partite_del_giorno(giorno) if ev["stato"] == "post"]
    for anno, ev in eventi:
        if ev["id"] in archivio:
            continue
        try:
            arbitro = _arbitro_partita(ev["id"])
        except Exception as e:  # una partita che non risponde non ferma le altre: si riprova al prossimo giro
            print("  ! arbitro ESPN {}: {}".format(ev["id"], e))
            continue
        archivio[ev["id"]] = [anno, ev["casa"], ev["trasf"], arbitro]
        nuovi += 1
        if nuovi % 40 == 0:
            scrivi_json(ARCHIVIO, archivio)
            espn_dettaglio.salva()
            print("    arbitri ESPN scaricati: {}".format(nuovi), flush=True)
    if nuovi:
        scrivi_json(ARCHIVIO, archivio)
        espn_dettaglio.salva()
    noti = set(noti)
    righe = [{"stagione": s, "casa": c, "trasf": t, "arbitro": _allinea(a, noti)}
             for s, c, t, a in archivio.values() if a]
    return pd.DataFrame(righe, columns=["stagione", "casa", "trasf", "arbitro"])


def id_partite(da_stagione):
    """Id ESPN delle partite finite già note dall'archivio, dalla stagione indicata in poi."""
    archivio = leggi_json(ARCHIVIO) if ARCHIVIO.exists() else {}
    return [k for k, v in archivio.items() if v[0] >= da_stagione]
