"""API-Football (piano gratuito): arbitro di ogni partita per le stagioni 2022-2024.

Il piano gratuito non include la stagione in corso né la precedente: qui serve solo per
ricostruire lo storico degli arbitri (1 richiesta per stagione, poi resta in cache per sempre).
"""
import re

import pandas as pd

from config import CACHE, leggi_env
from utils import fresca, leggi_json, scarica, scrivi_json, squadra

URL = "https://v3.football.api-sports.io/fixtures"
STAGIONI_GRATIS = [2023, 2024]


def _breve(nome):
    """Uniforma i nomi nel formato "L. Massimi" (la fonte li scrive a volte per esteso)."""
    if not nome or re.match(r"^[A-Z]\. ", nome):
        return nome
    parti = nome.split(" ", 1)
    return "{}. {}".format(parti[0][0], parti[1]) if len(parti) == 2 else nome


def carica(stagioni):
    chiave = leggi_env().get("APIFOOTBALL_KEY")
    righe = []
    for anno in stagioni:
        if anno not in STAGIONI_GRATIS:
            continue
        percorso = CACHE / "apifootball_fixtures_{}.json".format(anno)
        if not fresca(percorso, None):
            if not chiave:
                print("  ! API-Football: chiave mancante nel file .env")
                continue
            try:
                js = scarica(URL, params={"league": 135, "season": anno},
                             headers={"x-apisports-key": chiave}).json()
            except Exception as e:
                print("  ! API-Football {}: {}".format(anno, e))
                continue
            if js.get("errors"):
                print("  ! API-Football {}: {}".format(anno, js["errors"]))
                continue
            scrivi_json(percorso, js.get("response", []))
        for f in leggi_json(percorso):
            arbitro = _breve((f["fixture"].get("referee") or "").split(",")[0].strip())
            if arbitro:
                righe.append({"stagione": anno, "casa": squadra(f["teams"]["home"]["name"]),
                              "trasf": squadra(f["teams"]["away"]["name"]), "arbitro": arbitro})
    return pd.DataFrame(righe, columns=["stagione", "casa", "trasf", "arbitro"])
