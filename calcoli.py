"""Tutte le statistiche: arbitri, squadre, tipo di partita, soglie over e probabilità di giallo."""
import math
import re

import pandas as pd

import modello
from config import FONTE_PRIMARIA, FORMA_BREVE, FORMA_LUNGA, MINUTI_PRIOR, PESO_STAGIONE
from fonti import daznbet
from presenza import SOGLIA_STORICO
from utils import e_derby, nome_squadra, senza_accenti

SOGLIE = [3.5, 4.5, 5.5]


# ---------------------------------------------------------------------------------------------
# Probabilità sul numero di gialli
# ---------------------------------------------------------------------------------------------
def prob_oltre(media, rapporto_var, soglia):
    """P(gialli totali > soglia). Binomiale negativa (i gialli variano un po' più di Poisson)."""
    k = int(math.floor(soglia))  # oltre 3.5 = almeno 4 -> 1 - P(X <= 3)
    if media <= 0:
        return 0.0
    if rapporto_var <= 1.02:
        pmf = math.exp(-media)
        cdf = pmf
        for n in range(k):
            pmf *= media / (n + 1)
            cdf += pmf
    else:
        r = media / (rapporto_var - 1.0)
        p = r / (r + media)
        pmf = p ** r
        cdf = pmf
        for n in range(k):
            pmf *= (n + r) / (n + 1) * (1 - p)
            cdf += pmf
    return max(0.0, min(1.0, 1.0 - cdf))


def frequenza_oltre(serie, soglia):
    serie = pd.Series(serie).dropna()
    return float((serie > soglia).mean()) if len(serie) else None


# ---------------------------------------------------------------------------------------------
# Arbitri
# ---------------------------------------------------------------------------------------------
def risolvi_arbitro(nome_aia, noti):
    """L'AIA scrive "ROSSI C." o "DI BELLO": cerco il nome completo nello storico di API-Football."""
    testo = re.sub(r"\s*\(.*$", "", nome_aia.strip()).strip()   # "MASSA (Imperia)" o "MASSA (" -> "MASSA"
    iniziale = ""
    m = re.match(r"^(.*?)\s+((?:[A-Z]\.)+)$", testo)            # "ROSSI C." o "SACCHI J.L." -> prima iniziale
    if m:
        testo, iniziale = m.group(1), m.group(2)[0].lower()
    cognome = senza_accenti(testo).lower()
    candidati = [pieno for norm, pieno in noti.items() if norm == cognome or norm.endswith(" " + cognome)]
    if iniziale:
        candidati = [c for c in candidati if senza_accenti(c).lower().startswith(iniziale)] or candidati
    if candidati:
        return candidati[0]
    return testo.title()


def integra_con_espn(fd, finite, anno):
    """Aggiunge le partite finite che football-data.co.uk non ha ancora (di solito le ultime 1-3 giornate).

    I gialli, i rossi e i falli di squadra sono la somma di quelli dei giocatori in ESPN.
    """
    presenti = set(zip(fd["stagione"], fd["casa"], fd["trasf"]))
    righe = []
    for ev, forma in finite:
        if (anno, ev["casa"], ev["trasf"]) in presenti or "home" not in forma or "away" not in forma:
            continue
        somma = lambda lato, campo: int(sum(g[campo] for g in forma[lato]["giocatori"]))
        righe.append({
            "stagione": anno, "data": pd.Timestamp(ev["inizio"].date()), "casa": ev["casa"], "trasf": ev["trasf"],
            "gol_c": int(ev["gol_c"] or 0), "gol_t": int(ev["gol_t"] or 0),
            "g_c": somma("home", "gialli"), "g_t": somma("away", "gialli"),
            "r_c": somma("home", "rossi"), "r_t": somma("away", "rossi"),
            "f_c": somma("home", "falli"), "f_t": somma("away", "falli"),
            "pH": (ev.get("quote") or (None,) * 3)[0], "pD": (ev.get("quote") or (None,) * 3)[1],
            "pA": (ev.get("quote") or (None,) * 3)[2],
        })
    if not righe:
        return fd, 0
    extra = pd.DataFrame(righe)
    extra["g_tot"] = extra["g_c"] + extra["g_t"]
    extra["r_tot"] = extra["r_c"] + extra["r_t"]
    out = pd.concat([fd, extra], ignore_index=True).sort_values("data").reset_index(drop=True)
    return out, len(righe)


def controllo_espn(fd, finite, anno):
    """Confronta i gialli sommati da ESPN con quelli di football-data sulle partite presenti in entrambi."""
    ref = {(r.casa, r.trasf): (r.g_c, r.g_t) for r in fd[fd["stagione"] == anno].itertuples()}
    ok = diversi = 0
    for ev, forma in finite:
        if (ev["casa"], ev["trasf"]) in ref and "home" in forma and "away" in forma:
            e = (int(sum(g["gialli"] for g in forma["home"]["giocatori"])),
                 int(sum(g["gialli"] for g in forma["away"]["giocatori"])))
            if e == ref[(ev["casa"], ev["trasf"])]:
                ok += 1
            else:
                diversi += 1
    return ok, diversi


def prepara_partite(fd, arbitri_api, designazioni_aia):
    """Aggiunge a ogni partita storica l'arbitro (API-Football, poi AIA) e il tipo di partita."""
    df = fd.merge(arbitri_api, on=["stagione", "casa", "trasf"], how="left")
    noti = {senza_accenti(a).lower(): a for a in arbitri_api["arbitro"].dropna().unique()}
    aia = {k: risolvi_arbitro(v, noti) for k, v in designazioni_aia.items()}
    df["arbitro"] = [a if isinstance(a, str) else aia.get((s, c, t))
                     for a, s, c, t in zip(df["arbitro"], df["stagione"], df["casa"], df["trasf"])]
    return df, aia, noti


# ---------------------------------------------------------------------------------------------
# Tipo di partita
# ---------------------------------------------------------------------------------------------
def classifica(df):
    """Squadre ordinate per punti, differenza reti, gol fatti (sulle partite date)."""
    punti, dr, gf, gg = {}, {}, {}, {}
    for r in df.itertuples():
        for sq, fatti, subiti in ((r.casa, r.gol_c, r.gol_t), (r.trasf, r.gol_t, r.gol_c)):
            p = 3 if fatti > subiti else (1 if fatti == subiti else 0)
            punti[sq] = punti.get(sq, 0) + p
            dr[sq] = dr.get(sq, 0) + fatti - subiti
            gf[sq] = gf.get(sq, 0) + fatti
            gg[sq] = gg.get(sq, 0) + 1
    ordine = sorted(punti, key=lambda s: (-punti[s], -dr[s], -gf[s]))
    return ordine, gg


def costruisci_tabelle(df, anno):
    tabelle = {}
    for s in sorted(df["stagione"].unique()):
        ordine, giocate = classifica(df[df["stagione"] == s])
        tabelle[s] = (ordine, giocate)
    return tabelle


def tipo_partita(casa, trasf, stagione, tabelle, anno):
    if e_derby(casa, trasf):
        return "Derby"
    ordine, giocate = tabelle.get(stagione, ([], {}))
    # a inizio stagione la classifica dice poco: uso quella finale dell'anno prima
    if stagione == anno and (not giocate or min(giocate.values()) < 3) and (stagione - 1) in tabelle:
        ordine = tabelle[stagione - 1][0]
    n = len(ordine)
    if casa in ordine and trasf in ordine and n >= 12:
        pos_c, pos_t = ordine.index(casa), ordine.index(trasf)
        if pos_c < 6 and pos_t < 6:
            return "Big match"
        if pos_c >= n - 6 and pos_t >= n - 6:
            return "Scontro salvezza"
    return "Normale"


def aggiungi_tipo(df, tabelle, anno):
    df = df.copy()
    df["tipo"] = [tipo_partita(c, t, s, tabelle, anno) for c, t, s in zip(df["casa"], df["trasf"], df["stagione"])]
    return df


# ---------------------------------------------------------------------------------------------
# Squadre
# ---------------------------------------------------------------------------------------------
def formato_lungo(df):
    """Una riga per squadra e partita: gialli fatti (presi dalla squadra) e subiti (presi dall'avversaria)."""
    casa = pd.DataFrame({"stagione": df["stagione"], "data": df["data"], "squadra": df["casa"],
                         "avversario": df["trasf"], "campo": "casa", "fatti": df["g_c"], "subiti": df["g_t"],
                         "rossi_f": df["r_c"], "falli_f": df["f_c"], "falli_s": df["f_t"]})
    trasf = pd.DataFrame({"stagione": df["stagione"], "data": df["data"], "squadra": df["trasf"],
                          "avversario": df["casa"], "campo": "trasf", "fatti": df["g_t"], "subiti": df["g_c"],
                          "rossi_f": df["r_t"], "falli_f": df["f_t"], "falli_s": df["f_c"]})
    return pd.concat([casa, trasf], ignore_index=True).sort_values("data").reset_index(drop=True)


def _media(serie):
    return float(serie.mean()) if len(serie) else None


def tabella_squadre(lungo, anno, squadre):
    righe = []
    for sq in squadre:
        t = lungo[lungo["squadra"] == sq]
        s = t[t["stagione"] == anno]
        stor = t[t["stagione"] < anno]
        riga = {"squadra": nome_squadra(sq), "g_stag": len(s)}
        for campo in ("casa", "trasf"):
            sc = s[s["campo"] == campo]
            riga[campo + "_fatti"] = _media(sc["fatti"])
            riga[campo + "_subiti"] = _media(sc["subiti"])
            riga[campo + "_n"] = len(sc)
        riga["stag_fatti"] = _media(s["fatti"])
        riga["stag_subiti"] = _media(s["subiti"])
        for etichetta, n in (("f5", FORMA_BREVE), ("f10", FORMA_LUNGA)):
            u = t.tail(n)
            riga[etichetta + "_fatti"] = _media(u["fatti"])
            riga[etichetta + "_subiti"] = _media(u["subiti"])
        riga["stor_fatti"] = _media(stor["fatti"])
        riga["stor_subiti"] = _media(stor["subiti"])
        riga["rossi_stag"] = int(s["rossi_f"].sum())
        riga["falli_stag"] = _media(s["falli_f"])
        righe.append(riga)
    return righe


# ---------------------------------------------------------------------------------------------
# Arbitri: tabella e fattori
# ---------------------------------------------------------------------------------------------
def tabella_arbitri(df, anno):
    con = df.dropna(subset=["arbitro"])
    righe = []
    for nome, g in con.groupby("arbitro"):
        g = g.sort_values("data")
        s = g[g["stagione"] == anno]
        righe.append({
            "arbitro": nome, "partite": len(g), "gialli": float(g["g_tot"].mean()),
            "rossi": float(g["r_tot"].mean()), "gialli_casa": float(g["g_c"].mean()),
            "gialli_trasf": float(g["g_t"].mean()), "ultime5": float(g.tail(5)["g_tot"].mean()),
            "partite_stag": len(s), "gialli_stag": _media(s["g_tot"]),
            "over35": frequenza_oltre(g["g_tot"], 3.5), "over45": frequenza_oltre(g["g_tot"], 4.5),
            "over55": frequenza_oltre(g["g_tot"], 5.5),
        })
    # prima gli arbitri con almeno 5 partite: con 1-2 partite la media non significa nulla
    righe.sort(key=lambda r: (r["partite"] < 5, -r["gialli"]))
    return righe


def fattore_arbitro(df, arbitro):
    """Quanto l'arbitro si discosta dalla media (1.0 = nella media), con prudenza se ha poche partite."""
    if not arbitro:
        return 1.0, None
    con = df.dropna(subset=["arbitro"])
    g = con[con["arbitro"] == arbitro]
    if not len(g):
        return 1.0, None
    lega = con["g_tot"].mean()
    n = len(g)
    f = 1.0 + (g["g_tot"].mean() / lega - 1.0) * n / (n + 15.0)
    return f, {"partite": n, "gialli": float(g["g_tot"].mean()), "rossi": float(g["r_tot"].mean()),
               "lega": float(df["g_tot"].tail(380).mean()), "ultime5": float(g.sort_values("data").tail(5)["g_tot"].mean()),
               "over35": frequenza_oltre(g["g_tot"], 3.5), "over45": frequenza_oltre(g["g_tot"], 4.5),
               "over55": frequenza_oltre(g["g_tot"], 5.5)}


def tabella_tipi(df):
    righe = []
    lega = df["g_tot"].mean()
    for tipo in ("Derby", "Big match", "Scontro salvezza", "Normale"):
        g = df[df["tipo"] == tipo]
        if not len(g):
            continue
        righe.append({"tipo": tipo, "partite": len(g), "gialli": float(g["g_tot"].mean()),
                      "rapporto": float(g["g_tot"].mean() / lega),
                      "over35": frequenza_oltre(g["g_tot"], 3.5), "over45": frequenza_oltre(g["g_tot"], 4.5),
                      "over55": frequenza_oltre(g["g_tot"], 5.5)})
    return righe


def fattore_tipo(df, tipo):
    g = df[df["tipo"] == tipo]
    if not len(g):
        return 1.0
    n = len(g)
    return 1.0 + (g["g_tot"].mean() / df["g_tot"].mean() - 1.0) * n / (n + 30.0)


# ---------------------------------------------------------------------------------------------
# Gialli attesi in una partita
# ---------------------------------------------------------------------------------------------
def prepara_modello(df):
    """Addestra il modello di Poisson (modello.py) su tutte le partite giocate."""
    righe, stato = modello.prepara_righe(df)
    return modello.ModelloPoisson().fit(righe), stato


def gialli_attesi(ctx, ev):
    """Gialli attesi (casa, trasferta) dal modello di Poisson, con le quote 1X2 se ESPN le fornisce."""
    righe = modello.righe_future(ev["casa"], ev["trasf"], ev.get("quote"), ctx["stato_modello"],
                                 pd.Timestamp(ev["inizio"].date()), ctx["anno"])
    mu = ctx["poisson"].atteso(righe)
    return float(mu[0]), float(mu[1])


# ---------------------------------------------------------------------------------------------
# Giocatori
# ---------------------------------------------------------------------------------------------
_RUOLO_ESPN = {
    "G": "P",
    "CD": "D", "CD-L": "D", "CD-R": "D", "LB": "D", "RB": "D", "SW": "D", "D": "D", "LWB": "D", "RWB": "D",
    "CM": "C", "CM-L": "C", "CM-R": "C", "DM": "C", "AM": "C", "LM": "C", "RM": "C", "M": "C", "CAM": "C", "CDM": "C",
    "F": "A", "CF": "A", "CF-L": "A", "CF-R": "A", "LF": "A", "RF": "A", "ST": "A", "LW": "A", "RW": "A", "SS": "A",
}


def aggrega_espn(partite_finite):
    """Somma, per ogni giocatore, le partite 2026/27 giocate (gialli, falli, minuti stimati, panchine)."""
    giocatori, ultima = {}, {}
    for ev, forma in sorted(partite_finite, key=lambda x: x[0]["inizio"]):
        for lato in ("home", "away"):
            f = forma.get(lato)
            if not f:
                continue
            if any(g["titolare"] for g in f["giocatori"]):   # ESPN a volte manda una squadra senza giocatori: non cancella la precedente
                ultima[f["squadra"]] = f["giocatori"]
            for g in f["giocatori"]:
                d = giocatori.setdefault(g["id"], {"nome": g["nome"], "squadra": f["squadra"], "gialli": 0.0,
                                                   "falli": 0.0, "minuti": 0.0, "presenze": 0, "panchine": 0,
                                                   "entrate": 0})
                d["squadra"] = f["squadra"]
                if g["titolare"]:
                    d["presenze"] += 1
                    d["minuti"] += 68 if g["uscito"] else 90
                else:
                    d["panchine"] += 1
                    if g["entrato"] or g["presenze"] > 0:
                        d["entrate"] += 1
                        d["presenze"] += 1
                        d["minuti"] += 15 if g["uscito"] else 25
                d["gialli"] += g["gialli"]
                d["falli"] += g["falli"]
    return giocatori, ultima


class _Collegamento:
    """Collega un giocatore di ESPN a una riga di storico (Kickest o Transfermarkt) dal nome e dalla squadra."""

    def __init__(self, tabella, col_id):
        ultimi = tabella.sort_values("stagione").groupby(col_id).tail(1)
        self.candidati = []
        for r in ultimi.itertuples():
            parole = r.nome_completo.replace("-", " ").replace("'", " ").split()
            self.candidati.append((getattr(r, col_id), set(parole), r.squadra, parole[-1] if parole else ""))
        self.cache = {}

    def trova(self, nome, squadra):
        chiave = (nome, squadra)
        if chiave in self.cache:
            return self.cache[chiave]
        parole = senza_accenti(nome).lower().replace("-", " ").replace("'", " ").split()
        tok = set(parole)
        migliore, punteggio = None, 0.0
        for pid, tk, sq, ultimo in self.candidati:
            comuni = len(tok & tk)
            if not comuni:
                continue
            # il cognome (ultima parola) deve comparire nell'altro nome: due compagni di squadra che condividono solo il nome
            # di battesimo (Christian Comotto / Christian Pulisic) non sono la stessa persona
            if not parole or (parole[-1] not in tk and ultimo not in tok):
                continue
            s = comuni / float(len(tok | tk)) + (0.3 if sq == squadra else 0.0)
            if s > punteggio:
                migliore, punteggio = pid, s
        self.cache[chiave] = migliore if punteggio >= 0.55 else None
        return self.cache[chiave]


class ProfiliGiocatori:
    """Per ogni giocatore: gialli attesi in una partita intera (lam), ruolo, probabilità di uscire/entrare.

    Storico dei cartellini: la fonte primaria (FONTE_PRIMARIA: Transfermarkt, dal 2022/23, copre il 96-97% dei gialli di ogni
    stagione) e, dove non conosce il giocatore, l'altra (Kickest). Falli e contrasti esistono solo in Kickest e vengono
    sempre da lì. Ogni stagione conta secondo PESO_STAGIONE. Il rischio non è sui minuti ma sulla "esposizione": un minuto
    nel finale vale più di uno iniziale (vedi presenza.py), quindi titolari e subentrati si confrontano sulla stessa scala.
    """

    def __init__(self, kick, tm, espn_agg, anno, presenza, primaria=None):
        self.primaria = primaria or FONTE_PRIMARIA
        self.anno = anno
        self.espn = espn_agg
        self.pm = presenza
        kick = kick.assign(entrate=(kick["presenze"] - kick["titolare"]).clip(lower=0))
        self.prior = {}
        for ruolo, g in kick.groupby("ruolo"):
            m = max(g["minuti"].sum(), 1.0)
            self.prior[ruolo] = {"y": g["gialli"].sum() / m * 90, "f": g["falli"].sum() / m * 90,
                                 "t": g["contrasti"].sum() / m * 90}
        self.storia = {pid: g for pid, g in kick.groupby("id")}
        self.collega_k = _Collegamento(kick, "id")
        self.storia_tm, self.collega_tm = {}, None
        if tm is not None and len(tm):
            tm = tm[tm["stagione"] < anno]
            self.storia_tm = {pid: g for pid, g in tm.groupby("id_tm")}
            self.collega_tm = _Collegamento(tm, "id_tm")
        self.exp_titolare = {r: presenza.esposizione_titolare(None, r)[0] for r in "PDCA"}
        self.exp_subentrato = presenza.esposizione_subentrato()
        # gialli per "partita intera" tipici di ogni ruolo: serve da punto di partenza per chi ha poco storico
        y = {r: 0.0 for r in "PDCA"}
        e = {r: 1e-9 for r in "PDCA"}
        for r in kick.itertuples():
            w = PESO_STAGIONE.get(anno - r.stagione, 0.2)
            e[r.ruolo] += w * (r.titolare * self.exp_titolare[r.ruolo] + r.entrate * self.exp_subentrato)
            y[r.ruolo] += w * r.gialli
        self.lam_ruolo = {r: y[r] / e[r] for r in "PDCA"}

    def _esposizione(self, ruolo, titolare, entrate):
        return titolare * self.exp_titolare[ruolo] + entrate * self.exp_subentrato

    def _storie(self, nome, squadra):
        """(storico Kickest, storico Transfermarkt) del giocatore: None dove la fonte non lo conosce."""
        pid = self.collega_k.trova(nome, squadra)
        sk = self.storia.get(pid) if pid else None
        st = None
        if self.collega_tm is not None:
            pid_tm = self.collega_tm.trova(nome, squadra)
            st = self.storia_tm.get(pid_tm) if pid_tm is not None else None
        return sk, st

    def profilo(self, espn_id, nome, squadra, ruolo_espn):
        sk, st = self._storie(nome, squadra)
        if self.primaria == "tm":
            storia = st if st is not None else sk
        else:
            storia = sk if sk is not None else st
        # il ruolo è quello di Kickest quando c'è: le medie per ruolo (self.prior, self.lam_ruolo) sono calcolate con i suoi ruoli
        # e per gli esterni e i trequartisti i due siti non sono d'accordo (95% di ruoli uguali)
        fonte_ruolo = sk if sk is not None else storia
        if fonte_ruolo is not None:
            ruolo = fonte_ruolo.sort_values("stagione").iloc[-1]["ruolo"]
        else:
            ruolo = _RUOLO_ESPN.get(ruolo_espn, "C")
        if espn_id in self.pm.portieri:
            ruolo = "P"
        # -- numeri da mostrare (gialli, falli e contrasti ogni 90 minuti, con la stessa prudenza di prima)
        pr = self.prior.get(ruolo, {"y": 0.2, "f": 1.0, "t": 1.0})
        w_min = w_giallo = 0.0
        gialli_k = minuti_k = 0.0
        # -- gialli attesi in una partita intera
        w_y = w_e = 0.0
        if storia is not None:
            for r in storia.itertuples():
                w = PESO_STAGIONE.get(self.anno - r.stagione, 0.2)
                w_min += w * r.minuti
                w_giallo += w * r.gialli
                gialli_k += r.gialli
                minuti_k += r.minuti
                w_y += w * r.gialli
                w_e += w * self._esposizione(ruolo, r.titolare, r.entrate)
        # falli e contrasti ci sono solo in Kickest: li prendo da lì, con i minuti di Kickest, qualunque sia la fonte dei gialli
        w_min_k = w_falli = w_tack = 0.0
        if sk is not None:
            for r in sk.itertuples():
                w = PESO_STAGIONE.get(self.anno - r.stagione, 0.2)
                w_min_k += w * r.minuti
                w_falli += w * r.falli
                w_tack += w * r.contrasti
        w_min_f = w_min_k
        cur = self.espn.get(espn_id)
        peso0 = PESO_STAGIONE[0]
        if cur:
            w_min += peso0 * cur["minuti"]
            w_giallo += peso0 * cur["gialli"]
            w_min_f += peso0 * cur["minuti"]
            w_falli += peso0 * cur["falli"]
            w_y += peso0 * cur["gialli"]
            w_e += peso0 * self._esposizione(ruolo, max(cur["presenze"] - cur["entrate"], 0), cur["entrate"])
        K = MINUTI_PRIOR / 90.0
        y90 = (w_giallo + pr["y"] * K) / (w_min / 90.0 + K)
        f90 = (w_falli + pr["f"] * K) / (w_min_f / 90.0 + K)
        t90 = (w_tack + pr["t"] * K) / (w_min_k / 90.0 + K)
        lam = (w_y + self.lam_ruolo[ruolo] * K) / (w_e + K)
        return {"id": espn_id, "nome": nome, "ruolo": ruolo, "y90": y90, "f90": f90, "t90": t90, "lam": lam,
                "collegato": storia is not None,
                "gialli_stag": cur["gialli"] if cur else 0, "presenze_stag": cur["presenze"] if cur else 0,
                "gialli_prec": gialli_k, "minuti_prec": minuti_k}


def riconcilia_squadra(profili_titolari, profili_panchina, nome_squadra, atteso_squadra, pm):
    """Calcola le probabilità di tutti i giocatori di una squadra e le riporta al totale atteso dal modello di squadra.

    Passi: (1) probabilità di entrare dei panchinari, con il vincolo del numero di cambi della squadra;
    (2) gialli attesi di ogni giocatore = lam x esposizione (titolari: quanto restano in campo; panchinari:
    probabilità di entrare x quanto resta della partita); (3) un unico fattore k porta la somma dei giocatori
    ai gialli attesi dalla squadra; (4) probabilità = almeno un giallo, tenendo conto di quando può uscire/entrare.
    """
    ids = [g["id"] for g in profili_panchina]
    ruoli = {g["id"]: g["ruolo"] for g in profili_panchina}
    pe = pm.p_entra_squadra(ids, ruoli, pm.cambi_attesi(nome_squadra)) if ids else []
    for g, p_in in zip(profili_panchina, pe):
        g["p_entra"] = float(p_in)
    for g in profili_titolari:
        g["esposizione"], g["p_esce"], _ = pm.esposizione_titolare(g["id"], g["ruolo"])
    atteso = sum(g["lam"] * g["esposizione"] for g in profili_titolari)
    atteso += sum(g["p_entra"] * g["lam"] * pm.esposizione_subentrato() for g in profili_panchina)
    k = max(0.4, min(2.0, atteso_squadra / atteso)) if atteso > 0 else 1.0
    for g in profili_titolari:
        g["p_giallo"] = pm.p_giallo_titolare(g["lam"] * k, g["id"], g["ruolo"])
    for g in profili_panchina:
        g["p_se_entra"] = pm.p_giallo_se_entra(g["lam"] * k)
        g["p_giallo"] = g["p_entra"] * g["p_se_entra"]
    return k


def abbina_cambi(titolari, panchina, pm, soglia=0.05, quanti=3):
    """Per ogni panchinaro "rileva": chi toglie se entra; per ogni titolare "rilevato_da": chi lo sostituisce se esce.

    Solo giocatori della formazione di questa partita. Con meno di SOGLIA_STORICO cambi osservati il giocatore
    ha "poco storico" (campo *_storico = False) e la pagina non mostra percentuali."""
    for g in titolari + panchina:
        g["rileva"], g["rilevato_da"] = [], []
        g["rileva_storico"] = g["rilevato_storico"] = False
    if not titolari or not panchina:
        return
    cond = pm.chi_rileva(panchina, titolari)          # P(esce il titolare s | entra il panchinaro b)
    nomi = {t["id"]: t["nome"] for t in titolari}
    for b in panchina:
        ordinati = sorted(cond[b["id"]].items(), key=lambda kv: -kv[1])
        b["rileva"] = [(nomi[k], v) for k, v in ordinati[:quanti] if v >= soglia]
        b["rileva_storico"] = pm.n_entrate.get(b["id"], 0) >= SOGLIA_STORICO
    for t in titolari:
        pesi = [(b["nome"], b["p_entra"] * cond[b["id"]][t["id"]]) for b in panchina]
        tot = sum(p for _, p in pesi)
        if tot > 0:
            t["rilevato_da"] = [(n, p / tot) for n, p in sorted(pesi, key=lambda x: -x[1])[:quanti] if p / tot >= soglia]
        t["rilevato_storico"] = pm.n_uscite.get(t["id"], 0) >= SOGLIA_STORICO and t["ruolo"] != "P"


# ---------------------------------------------------------------------------------------------
# Una partita completa
# ---------------------------------------------------------------------------------------------
def analizza_partita(ev, forma, e_ufficiale, ctx):
    anno = ctx["anno"]
    casa, trasf = ev["casa"], ev["trasf"]
    df = ctx["df"]
    arbitro_aia = ctx["designazioni"].get((anno, casa, trasf))
    arbitro = ctx["aia_risolte"].get((anno, casa, trasf))
    f_arb, info_arb = fattore_arbitro(df, arbitro)
    tipo = tipo_partita(casa, trasf, anno, ctx["tabelle"], anno)
    f_tipo = fattore_tipo(df, tipo)
    e_c, e_t = gialli_attesi(ctx, ev)
    fattore = f_arb * f_tipo
    totale = (e_c + e_t) * fattore
    soglie = []
    for s in SOGLIE:
        soglie.append({
            "soglia": s, "prob": prob_oltre(totale, ctx["rapporto_var"], s),
            "lega": frequenza_oltre(df.tail(380)["g_tot"], s),
            "tipo": frequenza_oltre(df[df["tipo"] == tipo]["g_tot"], s),
            "arbitro": info_arb["over" + str(int(s * 10))] if info_arb else None,
        })
    squadre = []
    for lato, sq, e_sq in (("home", casa, e_c), ("away", trasf, e_t)):
        atteso_sq = e_sq * fattore
        f = forma.get(lato) if forma else None
        titolari, panchina = [], []
        for g in (f["giocatori"] if f else []):
            pg = ctx["profili"].profilo(g["id"], g["nome"], sq, g["ruolo_espn"])
            (titolari if g["titolare"] else panchina).append(pg)
        riconcilia_squadra(titolari, panchina, sq, atteso_sq, ctx["presenza"])
        daznbet.associa(ctx.get("quote_giocatori", {}).get((casa, trasf)), sq, titolari + panchina)
        abbina_cambi(titolari, panchina, ctx["presenza"])
        ordine = {"P": 0, "D": 1, "C": 2, "A": 3}
        titolari.sort(key=lambda p: (ordine.get(p["ruolo"], 9), -p["p_giallo"]))
        panchina.sort(key=lambda p: -p["p_giallo"])
        con_quote = (casa, trasf) in ctx.get("quote_giocatori", {})
        squadre.append({"nome": nome_squadra(sq), "lato": lato, "formazione": f["formazione"] if f else None,
                        "atteso": atteso_sq, "titolari": titolari, "panchina": panchina,
                        "quote_ora": ctx.get("quote_ora") if con_quote else None,
                        "id_stemma": ev.get("id_casa" if lato == "home" else "id_trasf")})
    return {"ev": ev, "ufficiale": e_ufficiale, "arbitro": arbitro, "arbitro_aia": arbitro_aia,
            "info_arbitro": info_arb, "f_arb": f_arb, "tipo": tipo, "f_tipo": f_tipo,
            "atteso": totale, "atteso_base": e_c + e_t, "soglie": soglie, "squadre": squadre}
