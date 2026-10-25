#!/usr/bin/env python3
"""Backtest dei giocatori: le probabilità di giallo (P(giallo) della pagina) sono calibrate?

Uso:  python backtest_giocatori.py
Per ogni giornata già giocata di quest'anno ricostruisce tutto il contesto usando solo i dati precedenti a quel giorno
(partite, storico dei cambi, statistiche dei giocatori), calcola con calcoli.analizza_partita la probabilità di titolari e
panchinari delle formazioni reali e la confronta con chi è stato ammonito davvero.
Stampa: punteggio contro medie semplici (più basso = meglio), calibrazione per fascia di probabilità, titolari/panchina/ruolo
e, se in git ci sono le quote DAZN Bet salvate, il confronto con il mercato e le puntate che la pagina avrebbe segnalato.
Dura circa mezzo minuto con la cache piena. Limiti: le quote 1X2 di ESPN non ci sono più a partita finita (si usano quelle di
football-data), le giornate d'inizio stagione hanno poco storico, e le quote DAZN Bet coprono solo le partite viste da quando
il PC le salva (pochi ammoniti: il confronto con il mercato è indicativo).
"""
import json
import subprocess
import sys
import warnings
from datetime import timedelta

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import calcoli  # noqa: E402
import config  # noqa: E402
import presenza  # noqa: E402
from fonti import (aia, api_football, arbitri_espn, espn, espn_dettaglio, football_data, kickest,  # noqa: E402
                   transfermarkt)


def _git(*a):
    try:
        return subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8", cwd=str(config.BASE)).stdout
    except OSError:
        return ""


def quote_salvate():
    """Ultima versione delle quote DAZN Bet di ogni partita, dalla storia di quote_daznbet.json in git."""
    quote = {}
    for c in [c for c in _git("log", "--format=%H", "--reverse", "--", "quote_daznbet.json").split() if c]:
        try:
            d = json.loads(_git("show", "{}:quote_daznbet.json".format(c)))
        except ValueError:
            continue
        for p in d["partite"]:
            quote[(p["casa"], p["trasf"])] = [(t, s, q) for t, s, q in p["righe"]]
    return quote


def raccogli():
    """Una riga per giocatore e partita: probabilità prevista con i dati di prima, esito reale."""
    anno, oggi = config.STAGIONE_CORRENTE, config.adesso().date()
    fd = football_data.carica()
    arb_api = api_football.carica(config.STAGIONI_STORICO)
    date_fd = set(fd[fd["stagione"] == anno]["data"].dt.date)
    ultimo = max(date_fd)
    giorni = date_fd | {ultimo + timedelta(k) for k in range(1, (oggi - ultimo).days + 1)}
    finite, viste = [], set()
    for g in sorted(giorni):
        for ev in espn.partite_del_giorno(g):
            if ev["stato"] == "post" and ev["id"] not in viste:
                viste.add(ev["id"])
                finite.append((ev, espn.formazioni(ev["id"], "post")))
    finite = [(ev, f) for ev, f in finite if len(f) == 2]
    arb_api = pd.concat([arb_api, arbitri_espn.carica(fd, finite, anno, set(arb_api["arbitro"]))], ignore_index=True)
    arb_api = arb_api.drop_duplicates(["stagione", "casa", "trasf"], keep="first")
    arbitro_reale = {(r.stagione, r.casa, r.trasf): r.arbitro for r in arb_api[arb_api["stagione"] == anno].itertuples()}
    kick = kickest.carica()
    tm = transfermarkt.carica(range(max(2022, anno - 4), anno))
    designazioni = aia.designazioni(aia.aggiorna())
    dettagli = espn_dettaglio.carica(sorted(set(arbitri_espn.id_partite(anno - 1)) | {ev["id"] for ev, _ in finite}))
    quote = quote_salvate()
    print("partite finite con formazioni: {} | partite con quote DAZN Bet salvate: {}".format(len(finite), len(quote)))

    righe = []
    for D in sorted({ev["inizio"].date() for ev, _ in finite}):
        prima = [(ev, f) for ev, f in finite if ev["inizio"].date() < D]
        fd_p, _ = calcoli.integra_con_espn(fd[fd["data"] < pd.Timestamp(D)], prima, anno)
        df, aia_ris, _ = calcoli.prepara_partite(fd_p, arb_api, designazioni)
        aia_ris = {**aia_ris, **arbitro_reale}    # l'arbitro è designato prima della partita: non è informazione futura
        tabelle = calcoli.costruisci_tabelle(df, anno)
        df = calcoli.aggiungi_tipo(df, tabelle, anno)
        giocatori_espn, _ = calcoli.aggrega_espn(prima)
        poisson, stato = calcoli.prepara_modello(df)
        pm = presenza.ModelloPresenza(dettagli, prima_del=D.isoformat(), stagione_corrente=anno)
        ctx = {"quote_giocatori": quote, "quote_ora": None, "anno": anno, "df": df, "lungo": calcoli.formato_lungo(df),
               "tabelle": tabelle, "designazioni": designazioni, "aia_risolte": aia_ris, "poisson": poisson,
               "stato_modello": stato, "rapporto_var": 1.0, "presenza": pm,
               "profili": calcoli.ProfiliGiocatori(kick, tm, giocatori_espn, anno, pm)}
        for ev, forma in [(e, f) for e, f in finite if e["inizio"].date() == D]:
            ev = dict(ev)
            if not ev.get("quote"):   # ESPN toglie le quote 1X2 a partita finita: uso quelle di football-data
                r = fd[(fd["stagione"] == anno) & (fd["casa"] == ev["casa"]) & (fd["trasf"] == ev["trasf"])]
                if len(r) and not pd.isna(r.iloc[0]["pH"]):
                    ev["quote"] = (float(r.iloc[0]["pH"]), float(r.iloc[0]["pD"]), float(r.iloc[0]["pA"]))
            analisi = calcoli.analizza_partita(ev, forma, True, ctx)
            reali = {g["id"]: g for lato in forma.values() for g in lato["giocatori"]}
            for sq in analisi["squadre"]:
                for gruppo, titolare in ((sq["titolari"], True), (sq["panchina"], False)):
                    for p in gruppo:
                        righe.append({"data": D.isoformat(), "partita": ev["casa"] + "-" + ev["trasf"], "squadra": sq["nome"],
                                      "nome": p["nome"], "ruolo": p["ruolo"], "titolare": titolare,
                                      "p": float(p["p_giallo"]), "y": int(reali.get(p["id"], {}).get("gialli", 0) > 0),
                                      "quota": p.get("quota_book")})
    return pd.DataFrame(righe)


def _brier(p, y):
    return float(((p - y) ** 2).mean())


def _logloss(p, y):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def stampa_calibrazione(R):
    y, p = R["y"].values.astype(float), R["p"].values
    print("\nrighe giocatore-partita: {} | ammoniti: {} ({:.1f}%) | probabilità media del modello: {:.1f}%".format(
        len(R), int(y.sum()), y.mean() * 100, p.mean() * 100))
    print("ammoniti previsti {:.0f} contro {:.0f} reali".format(p.sum(), y.sum()))
    print("\n--- punteggio (più basso = meglio) ---")
    for nome, q in (("sempre la media di tutti", np.full(len(y), y.mean())),
                    ("media per titolare/panchina", R.groupby("titolare")["y"].transform("mean").values),
                    ("media per ruolo e titolare/panchina", R.groupby(["titolare", "ruolo"])["y"].transform("mean").values),
                    ("MODELLO", p)):
        print("{:<38s} Brier {:.4f}   log-loss {:.4f}".format(nome, _brier(q, y), _logloss(q, y)))
    print("\n--- calibrazione: probabilità prevista contro frequenza reale ---")
    R = R.assign(fascia=pd.cut(R["p"], [0, .02, .04, .06, .08, .10, .13, .17, .22, 1]))
    t = R.groupby("fascia", observed=True).agg(n=("y", "size"), prevista=("p", "mean"), reale=("y", "mean"), ammoniti=("y", "sum"))
    for fascia, r in t.iterrows():
        print("{:<14s} n={:4d}  prevista {:5.1f}%  reale {:5.1f}%  ammoniti {:3d}".format(
            str(fascia), int(r["n"]), r["prevista"] * 100, r["reale"] * 100, int(r["ammoniti"])))
    print("\n--- per gruppo ---")
    for nome, s in (("titolari", R[R["titolare"]]), ("panchina", R[~R["titolare"]])):
        print("{:<10s} n={:4d}  prevista {:.1f}%  reale {:.1f}%".format(nome, len(s), s["p"].mean() * 100, s["y"].mean() * 100))
    for r in "PDCA":
        s = R[(R["ruolo"] == r) & R["titolare"]]
        print("titolari {}  n={:4d}  prevista {:.1f}%  reale {:.1f}%  (ammoniti {}, previsti {:.0f})".format(
            r, len(s), s["p"].mean() * 100, s["y"].mean() * 100, int(s["y"].sum()), s["p"].sum()))


def stampa_mercato(R):
    Q = R[R["quota"].notna() & (R["quota"] > 0)].copy()
    if not len(Q):
        print("\n(nessuna quota DAZN Bet salvata per le partite giocate: confronto con il mercato non disponibile)")
        return
    y, p, q = Q["y"].values.astype(float), Q["p"].values, Q["quota"].values
    imp = 1 / q
    c = min(np.linspace(0.2, 1.0, 161), key=lambda c: _logloss(np.clip(imp * c, 1e-4, .99), y))
    mercato = np.clip(imp * c, 1e-4, .99)
    print("\n--- confronto con il mercato: {} giocatori quotati, {} partite, {} ammoniti ---".format(
        len(Q), Q["partita"].nunique(), int(y.sum())))
    print("probabilità implicita media delle quote (1/q) {:.1f}% contro {:.1f}% di ammoniti reali "
          "(puntando su tutti: ritorno {:+.0f}%)".format(imp.mean() * 100, y.mean() * 100, ((y * q) - 1).mean() * 100))
    print("{:<38s} Brier {:.4f}   log-loss {:.4f}".format("MODELLO", _brier(p, y), _logloss(p, y)))
    print("{:<38s} Brier {:.4f}   log-loss {:.4f}   (margine tolto con un solo coefficiente, favorevole al mercato)".format(
        "MERCATO (1/q ripulito)", _brier(mercato, y), _logloss(mercato, y)))
    Q["ev"] = Q["p"] * Q["quota"] - 1
    print("\npuntate con valore atteso > 0 secondo il modello:")
    for soglia in (0, .1, .25):
        s = Q[Q["ev"] > soglia]
        print("  EV > {:+.0f}%: {:3d} puntate, {:2d} vinte, ritorno reale {}".format(
            soglia * 100, len(s), int(s["y"].sum()),
            "{:+.0f}%".format(((s["y"] * s["quota"]) - 1).mean() * 100) if len(s) else "-"))
    print("(poche puntate: non dicono se il valore atteso funziona; ripeti quando le partite con quote saranno di più)")


def main():
    R = raccogli()
    if not len(R):
        print("Nessuna partita da valutare.")
        return 1
    stampa_calibrazione(R)
    stampa_mercato(R)
    return 0


if __name__ == "__main__":
    sys.exit(main())
