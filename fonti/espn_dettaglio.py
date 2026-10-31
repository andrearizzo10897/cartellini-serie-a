"""Dettaglio di ogni partita ESPN in forma compatta: formazioni con cartellini e minuto di cambi e ammonizioni.

Serve a stimare, con molte partite, due cose che altrimenti sarebbero ipotesi:
- quando entrano i subentrati e quanti ne entrano per squadra;
- quanto gli ammoniti si concentrano nei minuti finali.
L'archivio dati/cache/espn_dettaglio.json tiene solo i campi necessari: dopo la prima esecuzione
(circa 380 richieste per il 2025/26) si scaricano solo le partite nuove.
"""
from config import CACHE
from fonti import espn
from fonti.api_football import _breve
from utils import leggi_json, scarica_json, scrivi_json, squadra

ARCHIVIO = CACHE / "espn_dettaglio.json"
VERSIONE = 1


def compatta(js):
    """Riduce il dettaglio ESPN di una partita ai campi che servono."""
    forma = espn._leggi_formazioni(js)
    eventi = []
    for e in js.get("keyEvents", []):
        tipo = (e.get("type") or {}).get("type")
        if tipo not in ("substitution", "yellow-card", "red-card"):
            continue
        minuto = (e.get("clock") or {}).get("value")
        if minuto is None:
            continue
        persone = [str(((p or {}).get("athlete") or {}).get("id")) for p in e.get("participants", [])]
        eventi.append({"tipo": tipo, "minuto": round(float(minuto) / 60.0, 1),
                       "testo": (e.get("clock") or {}).get("displayValue"),   # «90'+4'»: nel recupero il valore resta 90:00
                       "squadra": squadra((e.get("team") or {}).get("displayName", "")),
                       "persone": persone})
    data = None
    try:
        data = js["header"]["competitions"][0]["date"][:10]
    except (KeyError, IndexError, TypeError):
        pass
    ufficiali = (js.get("gameInfo") or {}).get("officials") or []
    arbitro = None
    if ufficiali:
        primo = next((o for o in ufficiali if o.get("order") == 1), ufficiali[0])
        arbitro = _breve((primo.get("fullName") or primo.get("displayName") or "").strip()) or None
    return {"data": data, "formazioni": forma, "eventi": eventi, "arbitro": arbitro, "finita": espn.finita(js)}


def _da_cache_completa(id_partita):
    percorso = CACHE / "espn" / "partita_{}.json".format(id_partita)
    return leggi_json(percorso) if percorso.exists() else None


_archivio = None


def _archivio_corrente():
    global _archivio
    if _archivio is None:
        _archivio = leggi_json(ARCHIVIO) if ARCHIVIO.exists() else {}
        if _archivio.get("_versione") != VERSIONE:
            _archivio = {"_versione": VERSIONE}
    return _archivio


def salva():
    if _archivio is not None:
        scrivi_json(ARCHIVIO, _archivio)


def _completa(voce):
    """Voce di una partita finita e con il minuto scritto ("testo", dal 29/10/2026): le altre si rifanno dal file completo, se c'è."""
    return voce.get("finita") is True and all("testo" in e for e in voce.get("eventi", []))


def dettaglio(id_partita):
    """Dettaglio compatto di una partita finita: dall'archivio, dalla cache completa o dalla rete (solleva se non risponde)."""
    archivio = _archivio_corrente()
    voce = archivio.get(id_partita)
    if voce is not None and _completa(voce):
        return voce
    js = _da_cache_completa(id_partita)
    if voce is not None and js is None:
        return voce   # voce dell'archivio iniziale (partite di stagioni passate, scaricate a partita finita)
    if js is None:
        js = scarica_json(espn.BASE + "/summary", params={"event": id_partita})
    archivio[id_partita] = compatta(js)   # voce nuova, o rifatta da un file salvato prima della fine della partita
    return archivio[id_partita]


def carica(ids):
    """{id: dettaglio compatto} per gli id richiesti (solo partite finite). Scarica quelli che mancano."""
    archivio = _archivio_corrente()
    nuovi = 0
    for id_partita in ids:
        voce = archivio.get(id_partita)
        if voce is not None and (_completa(voce) or not (CACHE / "espn" / "partita_{}.json".format(id_partita)).exists()):
            continue
        try:
            dettaglio(id_partita)
        except Exception as e:  # si riprova al prossimo giro
            print("  ! dettaglio ESPN {}: {}".format(id_partita, e))
            continue
        nuovi += 1
        if nuovi % 40 == 0:
            salva()
            print("    dettagli ESPN scaricati: {}".format(nuovi), flush=True)
    if nuovi:
        salva()
    richiesti = set(ids)
    return {k: v for k, v in archivio.items() if k in richiesti}
