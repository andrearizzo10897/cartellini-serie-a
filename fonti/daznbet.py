"""DAZN Bet: quota "giocatore ammonito (sì)" di ogni giocatore delle prossime partite di Serie A.

Il sito carica le quote da un servizio pubblico (lo stesso che usa la sua pagina Scommesse -> Calcio ->
Serie A -> Sanzioni Giocatori). Una sola richiesta per aggiornamento, senza login né cookie. Se il sito
non risponde o cambia formato, la pagina resta com'è e mostra "–" al posto della quota.
"""
import re
from datetime import datetime

import requests

import config
from utils import leggi_json, scrivi_json, senza_accenti, squadra

# Fuori da dati/: il workflow di GitHub ripristina quella cartella da una cache e riporterebbe indietro il file
FILE = config.BASE / "quote_daznbet.json"

URL = "https://www.daznbet.it/XSportDatastore/getTorneoCentrale"
PARAMETRI = {"systemCode": "DAZNBET", "lingua": "IT", "hash": "", "sportId": 1,
             "categoryId": 31, "tournamentId": 33,   # Calcio - Italia - Serie A
             "idAggregata": 2262}                     # scheda "Sanzioni Giocatori"
UA = {"User-Agent": "cartellini-serie-a (uso personale)"}
MERCATO = "GIOCATORE AMMONITO"


def _token(nome):
    s = re.sub(r"[^a-z ]", " ", senza_accenti(nome).lower())
    return [t for t in s.split() if len(t) > 1]


def scarica_quote():
    """{(casa, trasf): [(token del nome, squadra, quota), ...]} con i nomi squadra in forma canonica."""
    r = requests.get(URL, params=PARAMETRI, headers=UA, timeout=30)
    r.raise_for_status()
    return interpreta(r.json())


def interpreta(js):
    """Dal JSON del servizio di DAZN Bet alle quote «giocatore ammonito» di ogni partita (vedi scarica_quote)."""
    out = {}
    for av in js.get("avs", []):
        try:
            casa, trasf = (squadra(x) for x in av["dsl"]["IT"].split(" - ", 1))
        except (KeyError, ValueError):
            continue
        righe = []
        for sc in av.get("scs") or []:
            if not str(sc.get("d", "")).upper().startswith(MERCATO):
                continue
            m = re.match(r"(.*?)\s*\(([^)]*)\)\s*$", sc.get("dia") or "")
            q = next((e["q"] for e in sc.get("eqs") or [] if e.get("ce") == 1), 0)
            if m and q > 0:
                righe.append((_token(m.group(1)), squadra(m.group(2)), q / 100.0))
        if righe:
            out[(casa, trasf)] = righe
    return out


def salva(quote, percorso=FILE):
    """Salva le quote scaricate dal PC (il sito non risponde ai server di GitHub) in un file del repository."""
    righe = [{"casa": c, "trasf": t, "righe": r} for (c, t), r in quote.items()]
    scrivi_json(percorso, {"scaricato": config.adesso().isoformat(timespec="minutes"), "partite": righe})


def da_file(percorso=FILE):
    """(quote, data del download) dal file salvato, o ({}, None) se manca o è illeggibile."""
    try:
        dati = leggi_json(percorso)
        quote = {(p["casa"], p["trasf"]): [(t, s, q) for t, s, q in p["righe"]] for p in dati["partite"]}
        return quote, datetime.fromisoformat(dati["scaricato"])
    except (OSError, ValueError, KeyError, TypeError):
        return {}, None


def carica():
    """(quote, nota per la pagina, quando sono state scaricate). Prima prova il sito; se non risponde (succede da GitHub)
    usa il file salvato dal PC."""
    try:
        quote = scarica_quote()
        if quote:
            return quote, None, config.adesso()
    except Exception as e:  # noqa: BLE001 - rete o formato cambiato: la pagina deve generarsi comunque
        print("  ! DAZN Bet: {}".format(e))
    quote, quando = da_file()
    if not quote:
        return {}, "DAZN Bet non ha risposto e non c'è un file di quote salvato: le quote dei giocatori non sono disponibili.", None
    ore = (config.adesso() - quando).total_seconds() / 3600
    nota = "Quote DAZN Bet scaricate dal PC il {:%d/%m alle %H:%M}.".format(quando)
    if ore > config.QUOTE_MAX_ORE:
        nota += " Sono vecchie di {:.0f} ore: il valore atteso non è mostrato, controllale sul sito.".format(ore)
    return quote, nota, quando


def associa(quote_partita, sq, giocatori):
    """Scrive g["quota_book"] su ogni giocatore della squadra `sq` (nome canonico) trovato tra le quote.

    L'abbinamento è sul nome: tutte le parti del nome ESPN devono comparire nel nome DAZN Bet
    (che è "Cognome Nome"), oppure basta il cognome se un solo giocatore della squadra lo ha.
    """
    righe = [r for r in (quote_partita or []) if r[1] == sq]
    for g in giocatori:
        g["quota_book"] = None
    liberi = list(range(len(righe)))

    def assegna(va_bene):
        """Ogni riga di DAZN Bet va a un giocatore solo: se due giocatori si contendono la stessa riga, nessuno dei due."""
        scelte = {}
        for g in giocatori:
            if g["quota_book"] is None and _token(g["nome"]):
                adatte = [i for i in liberi if va_bene(g, righe[i])]
                if len(adatte) == 1:
                    scelte.setdefault(adatte[0], []).append(g)
        for i, chi in scelte.items():
            if len(chi) == 1:
                chi[0]["quota_book"] = righe[i][2]
                liberi.remove(i)

    assegna(lambda g, r: set(_token(g["nome"])) <= set(r[0]))
    assegna(lambda g, r: _token(g["nome"])[-1] in r[0])
