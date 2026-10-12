"""Tutte le statistiche: arbitri, squadre, tipo di partita, soglie over e probabilità di giallo."""
import math
import re

import pandas as pd

from config import FORMA_BREVE, FORMA_LUNGA, MINUTI_PRIOR, PESO_STAGIONE
from utils import e_derby, nome_squadra, senza_accenti

SOGLIE = [3.5, 4.5, 5.5]
MINUTI_TITOLARE = 85   # minuti medi attesi per un titolare
MINUTI_SUBENTRO = 25   # minuti medi attesi per chi entra dalla panchina


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
    testo = nome_aia.strip()
    iniziale = ""
    m = re.match(r"^(.*?)\s+([A-Z])\.$", testo)
    if m:
        testo, iniziale = m.group(1), m.group(2).lower()
    cognome = senza_accenti(testo).lower()
    candidati = [pieno for norm, pieno in noti.items() if norm == cognome or norm.endswith(" " + cognome)]
    if iniziale:
        candidati = [c for c in candidati if senza_accenti(c).lower().startswith(iniziale)] or candidati
    if candidati:
        return candidati[0]
    return nome_aia.title()


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
               "lega": float(lega), "ultime5": float(g.sort_values("data").tail(5)["g_tot"].mean()),
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
def _attesa(lungo, sq, campo, colonna, anno, media_lega):
    """Media attesa di una squadra in casa/trasferta: stagione corrente + storico + forma recente."""
    t = lungo[lungo["squadra"] == sq]
    storico = t[(t["stagione"] < anno) & (t["campo"] == campo)][colonna]
    stagione = t[(t["stagione"] == anno) & (t["campo"] == campo)][colonna]
    m_stor = storico.mean() if len(storico) >= 5 else media_lega
    n = len(stagione)
    base = (n * stagione.mean() + 8.0 * m_stor) / (n + 8.0) if n else m_stor
    recenti = t.tail(FORMA_BREVE)[colonna]
    riferimento = t.tail(35)[colonna].mean() if len(t) else None
    if len(recenti) and riferimento:
        r = recenti.mean() / riferimento if riferimento > 0 else 1.0
        r = 1.0 + (r - 1.0) * len(recenti) / (len(recenti) + 5.0)
        base *= 1.0 + 0.5 * (r - 1.0)
    return float(base)


def gialli_attesi(lungo, casa, trasf, anno):
    lega_c = lungo[lungo["campo"] == "casa"]["fatti"].mean()
    lega_t = lungo[lungo["campo"] == "trasf"]["fatti"].mean()
    e_casa = 0.5 * (_attesa(lungo, casa, "casa", "fatti", anno, lega_c)
                    + _attesa(lungo, trasf, "trasf", "subiti", anno, lega_c))
    e_trasf = 0.5 * (_attesa(lungo, trasf, "trasf", "fatti", anno, lega_t)
                     + _attesa(lungo, casa, "casa", "subiti", anno, lega_t))
    return e_casa, e_trasf, float(lega_c), float(lega_t)


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


class ProfiliGiocatori:
    def __init__(self, kick, espn_agg, anno):
        self.anno = anno
        self.espn = espn_agg
        self.cache_link = {}
        self.prior = {}
        for ruolo, g in kick.groupby("ruolo"):
            m = max(g["minuti"].sum(), 1.0)
            self.prior[ruolo] = {"y": g["gialli"].sum() / m * 90, "f": g["falli"].sum() / m * 90,
                                 "t": g["contrasti"].sum() / m * 90}
        self.storia = {pid: g for pid, g in kick.groupby("id")}
        ultimi = kick.sort_values("stagione").groupby("id").tail(1)
        self.candidati = [(r.id, set(r.nome_completo.split()), r.squadra, r.ruolo) for r in ultimi.itertuples()]

    def _collega(self, nome, squadra):
        chiave = (nome, squadra)
        if chiave in self.cache_link:
            return self.cache_link[chiave]
        tok = set(senza_accenti(nome).lower().replace("-", " ").replace("'", " ").split())
        migliore, punteggio = None, 0.0
        for pid, tk, sq, _ in self.candidati:
            comuni = len(tok & tk)
            if not comuni:
                continue
            s = comuni / float(len(tok | tk)) + (0.3 if sq == squadra else 0.0)
            if s > punteggio:
                migliore, punteggio = pid, s
        self.cache_link[chiave] = migliore if punteggio >= 0.55 else None
        return self.cache_link[chiave]

    def profilo(self, espn_id, nome, squadra, ruolo_espn):
        pid = self._collega(nome, squadra)
        storia = self.storia.get(pid) if pid else None
        if storia is not None:
            ruolo = storia.sort_values("stagione").iloc[-1]["ruolo"]
        else:
            ruolo = _RUOLO_ESPN.get(ruolo_espn, "C")
        pr = self.prior.get(ruolo, {"y": 0.2, "f": 1.0, "t": 1.0})
        w_min = w_giallo = w_falli = 0.0
        w_min_k = w_tack = 0.0
        gialli_k = minuti_k = 0.0
        if storia is not None:
            for r in storia.itertuples():
                w = PESO_STAGIONE.get(self.anno - r.stagione, 0.2)
                w_min += w * r.minuti
                w_giallo += w * r.gialli
                w_falli += w * r.falli
                w_min_k += w * r.minuti
                w_tack += w * r.contrasti
                gialli_k += r.gialli
                minuti_k += r.minuti
        cur = self.espn.get(espn_id)
        peso0 = PESO_STAGIONE[0]
        if cur:
            w_min += peso0 * cur["minuti"]
            w_giallo += peso0 * cur["gialli"]
            w_falli += peso0 * cur["falli"]
        K = MINUTI_PRIOR / 90.0
        y90 = (w_giallo + pr["y"] * K) / (w_min / 90.0 + K)
        f90 = (w_falli + pr["f"] * K) / (w_min / 90.0 + K)
        t90 = (w_tack + pr["t"] * K) / (w_min_k / 90.0 + K)
        prior_entra = 0.03 if ruolo == "P" else 0.45
        if cur and cur["panchine"] + cur["presenze"] - cur["entrate"] > 0:
            p_entra = (cur["entrate"] + prior_entra * 4) / (cur["panchine"] + 4.0)
        else:
            p_entra = prior_entra
        return {"id": espn_id, "nome": nome, "ruolo": ruolo, "y90": y90, "f90": f90, "t90": t90,
                "p_entra": p_entra, "collegato": pid is not None,
                "gialli_stag": cur["gialli"] if cur else 0, "presenze_stag": cur["presenze"] if cur else 0,
                "gialli_prec": gialli_k, "minuti_prec": minuti_k}


def prob_giallo(y90, minuti, fattore):
    return 1.0 - math.exp(-y90 * fattore * minuti / 90.0)


# ---------------------------------------------------------------------------------------------
# Una partita completa
# ---------------------------------------------------------------------------------------------
def analizza_partita(ev, forma, e_ufficiale, ctx):
    anno = ctx["anno"]
    casa, trasf = ev["casa"], ev["trasf"]
    df, lungo = ctx["df"], ctx["lungo"]
    arbitro_aia = ctx["designazioni"].get((anno, casa, trasf))
    arbitro = ctx["aia_risolte"].get((anno, casa, trasf))
    f_arb, info_arb = fattore_arbitro(df, arbitro)
    tipo = tipo_partita(casa, trasf, anno, ctx["tabelle"], anno)
    f_tipo = fattore_tipo(df, tipo)
    e_c, e_t, lega_c, lega_t = gialli_attesi(lungo, casa, trasf, anno)
    fattore = f_arb * f_tipo
    totale = (e_c + e_t) * fattore
    soglie = []
    storico_coppia = pd.concat([lungo[(lungo["squadra"] == casa) & (lungo["campo"] == "casa")],
                                lungo[(lungo["squadra"] == trasf) & (lungo["campo"] == "trasf")]])
    for s in SOGLIE:
        soglie.append({
            "soglia": s, "prob": prob_oltre(totale, ctx["rapporto_var"], s),
            "lega": frequenza_oltre(df["g_tot"], s),
            "tipo": frequenza_oltre(df[df["tipo"] == tipo]["g_tot"], s),
            "arbitro": info_arb["over" + str(int(s * 10))] if info_arb else None,
        })
    squadre = []
    for lato, sq, e_sq, lega_sq in (("home", casa, e_c, lega_c), ("away", trasf, e_t, lega_t)):
        f_sq = ((e_sq * fattore) / lega_sq) ** 0.5
        k = max(0.3, min(1.8, f_arb * f_tipo * f_sq))
        f = forma.get(lato) if forma else None
        titolari, panchina = [], []
        for g in (f["giocatori"] if f else []):
            p = ctx["profili"].profilo(g["id"], g["nome"], sq, g["ruolo_espn"])
            if g["titolare"]:
                p["minuti"] = MINUTI_TITOLARE if p["ruolo"] != "P" else 90
                p["p_giallo"] = prob_giallo(p["y90"], p["minuti"], k)
                titolari.append(p)
            else:
                p["minuti"] = MINUTI_SUBENTRO
                p["p_se_entra"] = prob_giallo(p["y90"], MINUTI_SUBENTRO, k)
                p["p_giallo"] = p["p_entra"] * p["p_se_entra"]
                panchina.append(p)
        ordine = {"P": 0, "D": 1, "C": 2, "A": 3}
        titolari.sort(key=lambda p: (ordine.get(p["ruolo"], 9), -p["p_giallo"]))
        panchina.sort(key=lambda p: -p["p_giallo"])
        squadre.append({"nome": nome_squadra(sq), "lato": lato, "formazione": f["formazione"] if f else None,
                        "atteso": e_sq * fattore, "titolari": titolari, "panchina": panchina})
    return {"ev": ev, "ufficiale": e_ufficiale, "arbitro": arbitro, "arbitro_aia": arbitro_aia,
            "info_arbitro": info_arb, "f_arb": f_arb, "tipo": tipo, "f_tipo": f_tipo,
            "atteso": totale, "atteso_base": e_c + e_t, "soglie": soglie, "squadre": squadre}
