"""Modello dei gialli di squadra: regressione di Poisson con effetti squadra regolarizzati.

Per ogni squadra e partita (una riga per squadra) i gialli attesi sono
    livello_lega * exp(casa + attacco(squadra) + difesa(avversaria) + b1*equilibrio + b2*forza + b3*falli ...)
- il livello_lega segue la media recente (i gialli per partita sono calati ogni anno);
- gli effetti squadra sono "tirati" verso zero (ridge): poche partite = poca fiducia;
- le partite vecchie pesano meno (dimezzano ogni EMIVITA_GIORNI);
- equilibrio e forza vengono dalle quote 1X2 (media dei bookmaker nello storico, DraftKings per le partite future).
Tutto ciò che entra in una riga è noto PRIMA della partita: nessuna informazione dal futuro.
"""
import numpy as np
import pandas as pd

PARAMETRI = {
    "emivita_giorni": 400,   # dopo quanti giorni una partita pesa la metà
    "lambda_squadra": 25.0,  # forza del ridge sugli effetti squadra
    "emivita_livello": 150,  # partite dopo cui la media di lega "dimentica" metà del passato
    "alfa_falli": 0.12,      # velocità con cui la media dei falli di una squadra segue le ultime partite
    "variabili": ("equilibrio", "forza", "falli_f", "falli_s"),
    "usa_allenatore": False,    # effetto dell'allenatore della squadra (e, con allenatore_avv, di quello avversario)
    "allenatore_avv": False,
    "lambda_allenatore": 15.0,  # forza del ridge sugli effetti allenatore
}


# ---------------------------------------------------------------------------------------------
# Quote -> probabilità
# ---------------------------------------------------------------------------------------------
def probabilita_da_quote(q1, qx, q2):
    """Quote decimali 1X2 -> probabilità senza il margine del bookmaker."""
    inv = np.array([1.0 / q1, 1.0 / qx, 1.0 / q2])
    return inv / inv.sum()


def probabilita_da_moneyline(ml1, mlx, ml2):
    """Quote americane (+145, -140...) -> probabilità senza margine."""
    def a_decimale(ml):
        return 1.0 + ml / 100.0 if ml > 0 else 1.0 + 100.0 / abs(ml)
    return probabilita_da_quote(a_decimale(ml1), a_decimale(mlx), a_decimale(ml2))


# ---------------------------------------------------------------------------------------------
# Righe di squadra con le variabili note prima della partita
# ---------------------------------------------------------------------------------------------
def _equilibrio_forza(p_t, p_o, p_x):
    """equilibrio: 0 = partita molto sbilanciata, 1 = pari; forza: vantaggio della squadra secondo le quote."""
    return 1.0 - abs(p_t - p_o), p_t - p_o


def prepara_righe(df, par=PARAMETRI, allenatori=None):
    """Trasforma il DataFrame delle partite (colonne di football_data + pH, pD, pA) in righe di squadra.

    `allenatori` è una funzione (squadra, 'AAAA-MM-GG') -> nome dell'allenatore o None.
    Ritorna (righe, stato). `stato` contiene livello e falli aggiornati dopo l'ultima partita: serve
    per costruire le righe delle partite future.
    """
    cerca = allenatori or (lambda sq, data: None)
    df = df.sort_values("data", kind="stable").reset_index(drop=True)
    decad = 0.5 ** (1.0 / par["emivita_livello"])
    num, den = 3.9 * 20, 20.0            # livello iniziale: 3.9 gialli a partita, pesato come 20 partite
    falli_f, falli_s = {}, {}
    lega_f_somma, lega_f_n = 0.0, 0
    righe = []
    for i, r in enumerate(df.itertuples()):
        livello = (num / den) / 2.0      # gialli attesi per squadra, prima di questa partita
        lega_f = (lega_f_somma / lega_f_n) if lega_f_n else 12.0
        quote = not (pd.isna(r.pH) or pd.isna(r.pA) or pd.isna(r.pD))
        for casa in (1, 0):
            sq, op = (r.casa, r.trasf) if casa else (r.trasf, r.casa)
            y = r.g_c if casa else r.g_t
            fo_f = r.f_c if casa else r.f_t
            fo_s = r.f_t if casa else r.f_c
            p_t, p_o = (r.pH, r.pA) if casa else (r.pA, r.pH)
            eq, fo = _equilibrio_forza(p_t, p_o, r.pD) if quote else (np.nan, np.nan)
            righe.append({
                "partita": i, "data": r.data, "stagione": r.stagione, "squadra": sq, "avversaria": op,
                "allenatore": cerca(sq, str(r.data.date())), "allenatore_avv": cerca(op, str(r.data.date())),
                "casa": casa, "y": y, "livello": livello,
                "equilibrio": eq, "forza": fo,
                "falli_f": np.log(falli_f.get(sq, lega_f) / lega_f),   # quanto la squadra commette falli
                "falli_s": np.log(falli_s.get(op, lega_f) / lega_f),   # quanti falli subisce l'avversaria
            })
        # aggiornamento dello stato DOPO la partita
        num = num * decad + (r.g_c + r.g_t)
        den = den * decad + 1.0
        a = par["alfa_falli"]
        for sq, fo_f, fo_s in ((r.casa, r.f_c, r.f_t), (r.trasf, r.f_t, r.f_c)):
            falli_f[sq] = falli_f.get(sq, lega_f) * (1 - a) + fo_f * a
            falli_s[sq] = falli_s.get(sq, lega_f) * (1 - a) + fo_s * a
        lega_f_somma += r.f_c + r.f_t
        lega_f_n += 2
    stato = {"livello": (num / den) / 2.0, "falli_f": falli_f, "falli_s": falli_s,
             "lega_f": lega_f_somma / max(lega_f_n, 1)}
    return pd.DataFrame(righe), stato


def righe_future(casa, trasf, quote, stato, data, stagione, allenatori=None):
    """Le due righe di squadra di una partita non ancora giocata. `quote` = (p1, pX, p2) o None."""
    out = []
    lf = stato["lega_f"]
    cerca = allenatori or (lambda sq, d: None)
    for c in (1, 0):
        sq, op = (casa, trasf) if c else (trasf, casa)
        if quote is not None:
            p1, px, p2 = quote
            p_t, p_o = (p1, p2) if c else (p2, p1)
            eq, fo = _equilibrio_forza(p_t, p_o, px)
        else:
            eq, fo = np.nan, np.nan
        out.append({
            "partita": -1, "data": data, "stagione": stagione, "squadra": sq, "avversaria": op, "casa": c,
            "allenatore": cerca(sq, str(data.date())), "allenatore_avv": cerca(op, str(data.date())),
            "y": np.nan, "livello": stato["livello"], "equilibrio": eq, "forza": fo,
            "falli_f": np.log(stato["falli_f"].get(sq, lf) / lf),
            "falli_s": np.log(stato["falli_s"].get(op, lf) / lf),
        })
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------------------------
# Regressione di Poisson con ridge
# ---------------------------------------------------------------------------------------------
class ModelloPoisson:
    def __init__(self, par=None):
        self.par = dict(PARAMETRI)
        if par:
            self.par.update(par)

    def _matrice(self, righe, medie=None):
        var = list(self.par["variabili"])
        if medie is None:
            medie = {v: float(righe[v].mean()) if righe[v].notna().any() else 0.0 for v in var}
        cols = [righe["casa"].astype(float).values]
        for v in var:
            cols.append(righe[v].fillna(medie[v]).values - medie[v])   # quote assenti = partita media
        denso = np.column_stack(cols)
        n = len(self.squadre)
        att = np.zeros((len(righe), n))
        dif = np.zeros((len(righe), n))
        for k, (s, o) in enumerate(zip(righe["squadra"], righe["avversaria"])):
            if s in self.indice:
                att[k, self.indice[s]] = 1.0
            if o in self.indice:
                dif[k, self.indice[o]] = 1.0
        blocchi = [denso, att, dif]
        if self.par["usa_allenatore"]:
            for col in ("allenatore", "allenatore_avv") if self.par["allenatore_avv"] else ("allenatore",):
                m = np.zeros((len(righe), len(self.allenatori)))
                for k, nome in enumerate(righe[col]):
                    if nome in self.indice_all:
                        m[k, self.indice_all[nome]] = 1.0
                blocchi.append(m)
        return np.hstack(blocchi), medie

    def fit(self, righe):
        self.squadre = sorted(set(righe["squadra"]) | set(righe["avversaria"]))
        self.indice = {s: i for i, s in enumerate(self.squadre)}
        self.allenatori = sorted({n for n in set(righe["allenatore"]) | set(righe["allenatore_avv"]) if isinstance(n, str)})
        self.indice_all = {n: i for i, n in enumerate(self.allenatori)}
        X, self.medie = self._matrice(righe)
        y = righe["y"].values.astype(float)
        off = np.log(righe["livello"].values)
        eta_giorni = (righe["data"].max() - righe["data"]).dt.days.values
        w = 0.5 ** (eta_giorni / self.par["emivita_giorni"])
        n_denso = 1 + len(self.par["variabili"])
        pen = np.concatenate([np.full(n_denso, 1.0), np.full(2 * len(self.squadre), self.par["lambda_squadra"])])
        pen[0] = 1e-3
        if self.par["usa_allenatore"]:
            n_blocchi = 2 if self.par["allenatore_avv"] else 1
            pen = np.concatenate([pen, np.full(n_blocchi * len(self.allenatori), self.par["lambda_allenatore"])])
        beta = np.zeros(X.shape[1])
        for _ in range(12):
            eta = X @ beta + off
            mu = np.exp(np.clip(eta, -5, 5))
            z = eta - off + (y - mu) / mu
            Wm = w * mu
            A = X.T @ (X * Wm[:, None]) + np.diag(pen)
            nuovo = np.linalg.solve(A, X.T @ (Wm * z))
            if np.max(np.abs(nuovo - beta)) < 1e-6:
                beta = nuovo
                break
            beta = nuovo
        self.beta = beta
        return self

    def atteso(self, righe):
        X, _ = self._matrice(righe, self.medie)
        return righe["livello"].values * np.exp(np.clip(X @ self.beta, -5, 5))

    def coefficienti(self):
        nomi = ["casa"] + list(self.par["variabili"])
        return dict(zip(nomi, self.beta[:len(nomi)]))
