"""DAZN Bet: quota "giocatore ammonito (sì)" di ogni giocatore delle prossime partite di Serie A.

Il sito carica le quote da un servizio pubblico (lo stesso che usa la sua pagina Scommesse -> Calcio ->
Serie A -> Sanzioni Giocatori). Una sola richiesta per aggiornamento, senza login né cookie. Se il sito
non risponde o cambia formato, la pagina resta com'è e mostra "–" al posto della quota.
"""
import re

import requests

from utils import senza_accenti, squadra

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
    out = {}
    for av in r.json().get("avs", []):
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


def carica():
    """Quote di tutte le partite, o {} se il sito non risponde (la pagina si genera lo stesso)."""
    try:
        return scarica_quote()
    except (requests.RequestException, ValueError):
        return {}


def associa(quote_partita, sq, giocatori):
    """Scrive g["quota_book"] su ogni giocatore della squadra `sq` (nome canonico) trovato tra le quote.

    L'abbinamento è sul nome: tutte le parti del nome ESPN devono comparire nel nome DAZN Bet
    (che è "Cognome Nome"), oppure basta il cognome se un solo giocatore della squadra lo ha.
    """
    righe = [r for r in (quote_partita or []) if r[1] == sq]
    for g in giocatori:
        g["quota_book"] = None
        t = set(_token(g["nome"]))
        if not t or not righe:
            continue
        piene = [r for r in righe if t <= set(r[0])]
        if len(piene) != 1:
            cognome = _token(g["nome"])[-1]
            piene = [r for r in righe if cognome in r[0]]
        if len(piene) == 1:
            g["quota_book"] = piene[0][2]
