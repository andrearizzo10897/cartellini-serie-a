#!/usr/bin/env python3
"""Backtest walk-forward: per ogni partita già giocata ricalcola la previsione usando solo i dati precedenti.

Uso:  python3 backtest.py
Misura quanto il modello sbaglia sul totale dei gialli e sulle soglie over 3,5 / 4,5 / 5,5, cosa che
da sola dice se un cambio al modello migliora davvero o no. Confronta il modello attuale (modello.py)
con due medie semplici e con la versione precedente (media mescolata di stagione, storico e forma).
Metriche: bias (media atteso - reale), MAE, RMSE, log-verosimiglianza (Poisson), Brier delle soglie
(più basso = meglio). Dura un paio di minuti e non scarica nulla se i dati sono già in cache.
"""
import math
import warnings

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import calcoli  # noqa: E402
import modello  # noqa: E402
from fonti import football_data  # noqa: E402

SOGLIE = calcoli.SOGLIE
PRIMA_STAGIONE_TEST = 2024   # il 2023/24 serve solo come storico di partenza


def poisson_pmf(k, media):
    return math.exp(-media + k * math.log(media) - math.lgamma(k + 1))


def previsioni(df, modello_bt, stagioni_test=None):
    """Una riga per partita di test: gialli attesi dal `modello` e gialli reali."""
    righe = []
    stagioni_test = stagioni_test or [s for s in sorted(df["stagione"].unique()) if s >= PRIMA_STAGIONE_TEST]
    for s in stagioni_test:
        for data in sorted(df[df["stagione"] == s]["data"].unique()):
            passato = df[df["data"] < data]
            oggi = df[df["data"] == data]
            ctx = modello_bt.prepara(passato, s)
            for r in oggi.itertuples():
                righe.append({"stagione": s, "data": data, "casa": r.casa, "trasf": r.trasf,
                              "reale": r.g_tot, "atteso": modello_bt.atteso(ctx, r)})
    return pd.DataFrame(righe)


def valuta(p, rapporto_var=1.0):
    """MAE, log-verosimiglianza media (Poisson) e Brier delle soglie."""
    out = {"n": len(p), "bias": float((p["atteso"] - p["reale"]).mean()),
           "mae": float((p["atteso"] - p["reale"]).abs().mean()),
           "rmse": float(np.sqrt(((p["atteso"] - p["reale"]) ** 2).mean()))}
    ll = []
    for m, k in zip(p["atteso"], p["reale"]):
        ll.append(math.log(max(poisson_pmf(int(k), max(m, 0.05)), 1e-12)))
    out["logl"] = float(np.mean(ll))
    for s in SOGLIE:
        pr = np.array([calcoli.prob_oltre(m, rapporto_var, s) for m in p["atteso"]])
        y = (p["reale"] > s).astype(float).values
        out["brier_{}".format(s)] = float(((pr - y) ** 2).mean())
    out["brier"] = float(np.mean([out["brier_{}".format(s)] for s in SOGLIE]))
    return out


def calibrazione(p, soglia, rapporto_var=1.0, classi=5):
    pr = np.array([calcoli.prob_oltre(m, rapporto_var, soglia) for m in p["atteso"]])
    y = (p["reale"] > soglia).astype(float).values
    t = pd.DataFrame({"pr": pr, "y": y})
    t["classe"] = pd.qcut(t["pr"], classi, duplicates="drop")
    return t.groupby("classe", observed=True).agg(n=("y", "size"), prevista=("pr", "mean"), reale=("y", "mean"))


# ---------------------------------------------------------------------------------------------
# Modelli
# ---------------------------------------------------------------------------------------------
def _attesa_precedente(lungo, sq, campo, colonna, anno, media_lega):
    """Versione precedente del calcolo: media di stagione + storico + forma recente, mescolate a mano."""
    t = lungo[lungo["squadra"] == sq]
    storico = t[(t["stagione"] < anno) & (t["campo"] == campo)][colonna]
    stagione = t[(t["stagione"] == anno) & (t["campo"] == campo)][colonna]
    m_stor = storico.mean() if len(storico) >= 5 else media_lega
    n = len(stagione)
    base = (n * stagione.mean() + 8.0 * m_stor) / (n + 8.0) if n else m_stor
    recenti = t.tail(5)[colonna]
    riferimento = t.tail(35)[colonna].mean() if len(t) else None
    if len(recenti) and riferimento:
        r = recenti.mean() / riferimento if riferimento > 0 else 1.0
        r = 1.0 + (r - 1.0) * len(recenti) / (len(recenti) + 5.0)
        base *= 1.0 + 0.5 * (r - 1.0)
    return float(base)


class ModelloPrecedente:
    """Il calcolo usato fino al 14/10/2026 (senza arbitro, che per il 2025/26 non c'è)."""
    nome = "precedente (media mescolata)"

    def prepara(self, passato, anno):
        lungo = calcoli.formato_lungo(passato)
        return {"anno": anno, "lungo": lungo, "lega_c": lungo[lungo["campo"] == "casa"]["fatti"].mean(),
                "lega_t": lungo[lungo["campo"] == "trasf"]["fatti"].mean()}

    def atteso(self, ctx, r):
        lungo, anno = ctx["lungo"], ctx["anno"]
        e_c = 0.5 * (_attesa_precedente(lungo, r.casa, "casa", "fatti", anno, ctx["lega_c"])
                     + _attesa_precedente(lungo, r.trasf, "trasf", "subiti", anno, ctx["lega_c"]))
        e_t = 0.5 * (_attesa_precedente(lungo, r.trasf, "trasf", "fatti", anno, ctx["lega_t"])
                     + _attesa_precedente(lungo, r.casa, "casa", "subiti", anno, ctx["lega_t"]))
        return e_c + e_t


class Costante:
    """Riferimento: media di tutte le partite precedenti, uguale per tutti."""
    nome = "media lega (tutto lo storico)"

    def prepara(self, passato, anno):
        return passato["g_tot"].mean()

    def atteso(self, ctx, r):
        return ctx


class CostanteStagione:
    """Riferimento: media della stagione in corso (se ci sono almeno 20 partite), altrimenti ultima stagione."""
    nome = "media lega (stagione corrente)"

    def prepara(self, passato, anno):
        s = passato[passato["stagione"] == anno]
        if len(s) >= 20:
            return s["g_tot"].mean()
        prec = passato[passato["stagione"] == passato["stagione"].max()]
        return prec["g_tot"].mean()

    def atteso(self, ctx, r):
        return ctx


class ModelloPoissonBT:
    """Regressione di Poisson di modello.py, rifittata ad ogni giornata solo sui dati precedenti."""

    def __init__(self, df, par=None, nome="poisson"):
        self.nome = nome
        self.par = par or {}
        pieno = dict(modello.PARAMETRI)
        pieno.update(self.par)
        righe, _ = modello.prepara_righe(df, pieno)
        self.righe = righe
        self.indice = {}
        for k, r in righe.iterrows():
            self.indice.setdefault((r["data"], r["squadra"], r["avversaria"]), k)

    def prepara(self, passato, anno):
        ultimo = passato["data"].max()
        train = self.righe[self.righe["data"] <= ultimo]
        m = modello.ModelloPoisson(self.par).fit(train)
        return m

    def atteso(self, m, r):
        a = self.indice[(r.data, r.casa, r.trasf)]
        b = self.indice[(r.data, r.trasf, r.casa)]
        mu = m.atteso(self.righe.loc[[a, b]])
        return float(mu.sum())


def stampa(nome, v):
    print("{:<38} n={:<4} bias={:+.3f}  MAE={:.3f}  RMSE={:.3f}  logL={:.4f}  Brier={:.4f}  ({})".format(
        nome, v["n"], v["bias"], v["mae"], v["rmse"], v["logl"], v["brier"],
        " ".join("{:.4f}".format(v["brier_{}".format(s)]) for s in SOGLIE)))


def main():
    df = football_data.carica()
    candidati = [
        Costante(), CostanteStagione(), ModelloPrecedente(),
        ModelloPoissonBT(df, {"variabili": ()}, "poisson: solo squadre"),
        ModelloPoissonBT(df, {"variabili": ("equilibrio", "forza")}, "poisson + quote"),
        ModelloPoissonBT(df, {"variabili": ("falli_f", "falli_s")}, "poisson + falli"),
        ModelloPoissonBT(df, {}, "poisson + quote + falli"),
    ]
    for modello_bt in candidati:
        p = previsioni(df, modello_bt)
        stampa(modello_bt.nome, valuta(p))
    print("\nCalibrazione del modello completo (probabilità prevista contro frequenza reale)")
    for s in SOGLIE:
        print("over {}".format(s))
        print(calibrazione(p, s).round(3).to_string())


if __name__ == "__main__":
    main()
