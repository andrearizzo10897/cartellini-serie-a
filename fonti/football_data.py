"""football-data.co.uk: risultati, gialli, rossi e falli per squadra, partita per partita."""
import io

import pandas as pd

from config import CACHE, STAGIONE_CORRENTE, STAGIONI_STORICO
from utils import fresca, scarica, squadra

URL = "https://www.football-data.co.uk/mmz4281/{codice}/I1.csv"


def _codice(anno):
    return "{:02d}{:02d}".format(anno % 100, (anno + 1) % 100)


def carica():
    """DataFrame con una riga per partita giocata, dal 2023/24 a oggi."""
    pezzi = []
    for anno in STAGIONI_STORICO:
        percorso = CACHE / "football_data_{}.csv".format(_codice(anno))
        ttl = 2 if anno == STAGIONE_CORRENTE else None
        if not fresca(percorso, ttl):
            try:
                testo = scarica(URL.format(codice=_codice(anno))).content.decode("utf-8-sig")
                percorso.parent.mkdir(parents=True, exist_ok=True)
                percorso.write_text(testo, encoding="utf-8")
            except Exception as e:  # se manca la rete uso l'ultima copia salvata
                print("  ! football-data {}: {}".format(anno, e))
                if not percorso.exists():
                    continue
        df = pd.read_csv(io.StringIO(percorso.read_text(encoding="utf-8").lstrip("﻿")))
        df = df.dropna(subset=["HomeTeam", "AwayTeam", "HY", "AY"])
        # quote 1X2: media dei bookmaker, altrimenti Bet365; poi tolgo il margine -> probabilità
        q = {}
        for lato in "HDA":
            q[lato] = df["Avg" + lato].fillna(df["B365" + lato])
        inv = pd.DataFrame({k: 1.0 / v for k, v in q.items()})
        prob = inv.div(inv.sum(axis=1), axis=0)
        out = pd.DataFrame({
            "pH": prob["H"], "pD": prob["D"], "pA": prob["A"],
            "stagione": anno,
            "data": pd.to_datetime(df["Date"], dayfirst=True),
            "casa": df["HomeTeam"].map(squadra),
            "trasf": df["AwayTeam"].map(squadra),
            "gol_c": df["FTHG"].astype(int),
            "gol_t": df["FTAG"].astype(int),
            "g_c": df["HY"].astype(int),
            "g_t": df["AY"].astype(int),
            "r_c": df["HR"].fillna(0).astype(int),
            "r_t": df["AR"].fillna(0).astype(int),
            "f_c": df["HF"].fillna(0).astype(int),
            "f_t": df["AF"].fillna(0).astype(int),
        })
        pezzi.append(out)
    if not pezzi:
        raise RuntimeError("Nessun dato da football-data.co.uk (e nessuna copia in cache)")
    df = pd.concat(pezzi, ignore_index=True).sort_values("data").reset_index(drop=True)
    df["g_tot"] = df["g_c"] + df["g_t"]
    df["r_tot"] = df["r_c"] + df["r_t"]
    return df
