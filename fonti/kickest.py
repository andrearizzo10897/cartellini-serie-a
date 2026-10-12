"""Kickest: statistiche stagionali per giocatore (minuti, gialli, falli, contrasti).

Usa lo stesso indirizzo interno che alimenta il "tabellone" del sito: non è un'API ufficiale,
quindi se Kickest la cambia questo modulo va adattato. La stagione in corso al momento non è
pubblicata da Kickest: in quel caso restituisce una tabella vuota e i dati vengono da ESPN.
"""
import pandas as pd

from config import CACHE, STAGIONE_CORRENTE, STAGIONI_STORICO
from utils import fresca, leggi_json, scarica, scrivi_json, senza_accenti, squadra

URL = "https://www.kickest.it/dev/stats/players/table/getStats"
ID_STAGIONE = {2023: 10, 2024: 11, 2025: 12, 2026: 13, 2027: 14}  # 10 = 2023/24
RUOLI = {"1": "P", "2": "D", "3": "C", "4": "A"}
COLONNE = ["stagione", "id", "nome", "nome_completo", "squadra", "ruolo", "presenze", "titolare",
           "minuti", "gialli", "rossi", "falli", "falli_sub", "contrasti", "contrasti_vinti"]


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _nome_da_url(url):
    ultimo = (url or "").rstrip("/").split("/")[-1]
    return senza_accenti(ultimo.replace("-", " "))


def _scarica_stagione(anno):
    percorso = CACHE / "kickest_{}.json".format(anno)
    ttl = 12 if anno == STAGIONE_CORRENTE else None
    if fresca(percorso, ttl):
        return leggi_json(percorso)
    giornate = " ".join(str(i) for i in range(38, 0, -1))
    try:
        r = scarica(URL, params={"category": "1", "season": str(ID_STAGIONE[anno]), "matchdays": giornate,
                                 "mode": "1", "language": "it"},
                    headers={"X-Requested-With": "XMLHttpRequest",
                             "Referer": "https://www.kickest.it/it/serie-a/statistiche/giocatori/tabellone"},
                    timeout=120, tentativi=3)
        js = r.json()
    except Exception as e:
        print("  ! Kickest {}: {}".format(anno, e))
        return leggi_json(percorso) if percorso.exists() else []
    righe = js.get("data") if isinstance(js, dict) else None
    righe = righe if isinstance(righe, list) else []
    scrivi_json(percorso, righe)
    return righe


def carica():
    pezzi = []
    for anno in STAGIONI_STORICO:
        if anno not in ID_STAGIONE:
            continue
        for r in _scarica_stagione(anno):
            pezzi.append({
                "stagione": anno,
                "id": str(r.get("player_id")),
                "nome": r.get("player", ""),
                "nome_completo": _nome_da_url(r.get("player_url")),
                "squadra": squadra(r.get("team_name_long", "")),
                "ruolo": RUOLI.get(str(r.get("position_id")), "C"),
                "presenze": _num(r.get("apps")),
                "titolare": _num(r.get("starter")),
                "minuti": _num(r.get("mins")),
                "gialli": _num(r.get("yellow_cards")),
                "rossi": _num(r.get("red_cards")),
                "falli": _num(r.get("fouls_made")),
                "falli_sub": _num(r.get("fouls_received")),
                "contrasti": _num(r.get("tackles")),
                "contrasti_vinti": _num(r.get("tackles_won")),
            })
    return pd.DataFrame(pezzi, columns=COLONNE)
