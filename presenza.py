"""Quanto e quando gioca ciascun giocatore, e quanto "pesano" quei minuti per i cartellini.

I gialli non arrivano a ritmo costante: nei dati ESPN solo il 5% cade nei primi 15 minuti e il 35% negli
ultimi 15 (recupero compreso). Per questo un subentrato che entra al 69' si prende circa il 44% del rischio
di una partita intera (non il 28% che darebbero 25 minuti su 90) e un attaccante sostituito al 69' ne prende
circa il 60% (non il 94% di 85 minuti su 90).

Tutto è stimato dalle partite finite già salvate (dati/cache/espn_dettaglio.json) usando solo quelle
precedenti alla partita che si sta calcolando:
- curva cumulata del rischio di giallo nel tempo (H);
- probabilità di essere sostituito e minuto dell'uscita, per ruolo e per giocatore;
- probabilità di entrare e minuto dell'ingresso, con il vincolo che in una partita entrano ~4,7 giocatori per squadra.
"""
import math
from datetime import date

import numpy as np

from config import stagione_di

LUNGHEZZA = 96.0   # minuti di una partita compreso il recupero medio
FASCE = [0, 15, 30, 45, 60, 75, LUNGHEZZA]
PESO_STAGIONE_PRECEDENTE = 0.6   # peso delle partite della stagione prima rispetto a quella in corso
K_USCITA = 6.0      # partite "virtuali" con cui si tira la probabilità di uscita di un giocatore verso quella del ruolo
K_INGRESSO = 3.0    # idem per la probabilità di entrare dalla panchina
PRIOR_ENTRA = 0.43  # probabilità media di entrare per un panchinaro di movimento (4,7 cambi su ~11 giocatori)
PRIOR_ENTRA_PORTIERE = 0.02
EMIVITA_CAMBI_LEGA = 100.0    # osservazioni (squadra-partita) dopo cui il livello di cambi della lega dimentica metà del passato
EMIVITA_CAMBI_SQUADRA = 10.0  # partite della squadra dopo cui la sua media dimentica metà del passato
K_CAMBI = 12.0                # partite "virtuali" con cui la media di una squadra viene tirata verso la lega

_RUOLO = {
    "G": "P",
    "CD": "D", "CD-L": "D", "CD-R": "D", "LB": "D", "RB": "D", "SW": "D", "D": "D", "LWB": "D", "RWB": "D",
    "CM": "C", "CM-L": "C", "CM-R": "C", "DM": "C", "AM": "C", "LM": "C", "RM": "C", "M": "C", "CAM": "C", "CDM": "C",
    "F": "A", "CF": "A", "CF-L": "A", "CF-R": "A", "LF": "A", "RF": "A", "ST": "A", "LW": "A", "RW": "A", "SS": "A",
}


def _stagione(data_iso):
    y, m, d = (int(x) for x in data_iso.split("-"))
    return stagione_di(date(y, m, d))


class ModelloPresenza:
    def __init__(self, dettagli, prima_del=None, stagione_corrente=None):
        """dettagli: {id partita: dettaglio compatto}. prima_del: 'AAAA-MM-GG' (esclusa) per usare solo il passato."""
        pool = [v for v in dettagli.values() if v.get("data") and (prima_del is None or v["data"] < prima_del)]
        self.n_partite = len(pool)
        if stagione_corrente is None:
            stagione_corrente = max((_stagione(v["data"]) for v in pool), default=2026)
        gialli, ingressi = [], []
        uscite = {r: [] for r in "PDCA"}
        titolari = {r: 0 for r in "PDCA"}
        usciti = {r: 0 for r in "PDCA"}
        cambi_squadra = []
        self.osservazioni = []   # (data, squadra, giocatori entrati) per ogni squadra e partita
        self.giocatore = {}     # id ESPN -> contatori pesati
        portieri = set()
        for v in pool:
            w = 1.0 if _stagione(v["data"]) == stagione_corrente else PESO_STAGIONE_PRECEDENTE
            ruolo = {}
            for lato in ("home", "away"):
                f = v["formazioni"].get(lato)
                if not f:
                    continue
                for g in f["giocatori"]:
                    r = _RUOLO.get(g["ruolo_espn"])
                    if g["titolare"] and r:
                        ruolo[g["id"]] = r
                        if r == "P":
                            portieri.add(g["id"])
                        titolari[r] += 1
                        usciti[r] += bool(g["uscito"])
                    c = self.giocatore.setdefault(g["id"], {"start": 0.0, "out": 0.0, "bench": 0.0, "in": 0.0,
                                                           "ruolo": None})
                    if g["titolare"]:
                        c["start"] += w
                        c["out"] += w * bool(g["uscito"])
                        c["ruolo"] = r or c["ruolo"]
                    else:
                        c["bench"] += w
                        c["in"] += w * bool(g["entrato"])
            for lato in ("home", "away"):
                f = v["formazioni"].get(lato)
                if f and f["giocatori"]:
                    self.osservazioni.append((v["data"], f["squadra"],
                                              sum(1 for g in f["giocatori"] if not g["titolare"] and g["entrato"])))
            per_squadra = {}
            for e in v["eventi"]:
                if e["tipo"] == "yellow-card":
                    gialli.append(min(e["minuto"], LUNGHEZZA - 0.1))
                elif e["tipo"] == "substitution" and len(e["persone"]) >= 2:
                    per_squadra[e["squadra"]] = per_squadra.get(e["squadra"], 0) + 1
                    ingressi.append(min(e["minuto"], LUNGHEZZA - 0.1))
                    r = ruolo.get(e["persone"][1])
                    if r:
                        uscite[r].append(min(e["minuto"], LUNGHEZZA - 0.1))
            cambi_squadra += list(per_squadra.values())
        self.portieri = portieri
        # --- curva del rischio: densità costante in ogni fascia, poi cumulata normalizzata a 1 a fine partita
        conteggi, _ = np.histogram(gialli, bins=FASCE) if gialli else (np.ones(len(FASCE) - 1), None)
        dens = (conteggi + 1.0) / np.diff(FASCE)          # +1: nessuna fascia a rischio zero
        cum = np.concatenate([[0.0], np.cumsum(dens * np.diff(FASCE))])
        self._cum = cum / cum[-1]
        # --- uscite dei titolari per ruolo
        self.p_uscita = {r: (usciti[r] + 3 * 0.5) / (titolari[r] + 6) for r in "PDCA"}
        for r in "PDCA":
            if titolari[r] == 0:
                self.p_uscita[r] = {"P": 0.01, "D": 0.24, "C": 0.52, "A": 0.73}[r]
        self.minuti_uscita = {r: np.array(uscite[r] if len(uscite[r]) >= 20 else ingressi or [68.0]) for r in "PDCA"}
        self.minuti_ingresso = np.array(ingressi if ingressi else [68.0])
        self.cambi_medi = float(np.mean(cambi_squadra)) if cambi_squadra else 4.7
        self._prepara_cambi()

    def _prepara_cambi(self):
        """Numero atteso di cambi: livello recente della lega, corretto con la tendenza di ogni squadra."""
        obs = sorted(self.osservazioni)
        self._cambi_squadra = {}
        if not obs:
            self._cambi_lega = self.cambi_medi
            return
        n = len(obs)
        w = 0.5 ** ((n - 1 - np.arange(n)) / EMIVITA_CAMBI_LEGA)
        self._cambi_lega = float(np.sum(w * np.array([o[2] for o in obs])) / w.sum())
        per = {}
        for _, sq, k in obs:
            per.setdefault(sq, []).append(k)
        for sq, valori in per.items():
            m = len(valori)
            ws = 0.5 ** ((m - 1 - np.arange(m)) / EMIVITA_CAMBI_SQUADRA)
            self._cambi_squadra[sq] = (float(np.sum(ws * np.array(valori)) / ws.sum()), float(ws.sum()))

    def cambi_attesi(self, nome_squadra=None):
        """Giocatori attesi in ingresso per la squadra: media della squadra "tirata" verso il livello della lega."""
        if nome_squadra not in self._cambi_squadra:
            return self._cambi_lega
        media, peso = self._cambi_squadra[nome_squadra]
        return (peso * media + K_CAMBI * self._cambi_lega) / (peso + K_CAMBI)

    # ---- curva oraria ------------------------------------------------------------------------
    def H(self, minuto):
        """Quota (0-1) del rischio di giallo di una partita intera accumulata fino a `minuto`."""
        return float(np.interp(minuto, FASCE, self._cum))

    def _H_array(self, minuti):
        return np.interp(minuti, FASCE, self._cum)

    # ---- titolari ----------------------------------------------------------------------------
    def p_uscita_giocatore(self, id_espn, ruolo):
        c = self.giocatore.get(id_espn)
        prior = self.p_uscita.get(ruolo, 0.5)
        if not c:
            return prior
        return (c["out"] + K_USCITA * prior) / (c["start"] + K_USCITA)

    def esposizione_titolare(self, id_espn, ruolo):
        """(quota di rischio attesa, probabilità di restare in campo fino alla fine, array H alle uscite)."""
        po = self.p_uscita_giocatore(id_espn, ruolo)
        h_uscite = self._H_array(self.minuti_uscita.get(ruolo, self.minuti_ingresso))
        attesa = (1.0 - po) * 1.0 + po * float(h_uscite.mean())
        return attesa, po, h_uscite

    def p_giallo_titolare(self, lam, id_espn, ruolo):
        """lam = gialli attesi in una partita intera (sempre in campo). Ritorna P(almeno un giallo)."""
        _, po, h_uscite = self.esposizione_titolare(id_espn, ruolo)
        pieno = 1.0 - math.exp(-lam)
        uscito = float(np.mean(1.0 - np.exp(-lam * h_uscite)))
        return (1.0 - po) * pieno + po * uscito

    # ---- panchina ----------------------------------------------------------------------------
    def p_entra_grezza(self, id_espn, ruolo_noto=None):
        c = self.giocatore.get(id_espn)
        portiere = id_espn in self.portieri or ruolo_noto == "P"
        prior = PRIOR_ENTRA_PORTIERE if portiere else PRIOR_ENTRA
        if not c:
            return prior
        return (c["in"] + K_INGRESSO * prior) / (c["bench"] + K_INGRESSO)

    def p_entra_squadra(self, ids, ruoli_noti=None, cambi=None):
        """Probabilità di entrare di ciascun panchinaro, riportate al numero atteso di cambi della squadra."""
        ruoli_noti = ruoli_noti or {}
        grezze = np.array([self.p_entra_grezza(i, ruoli_noti.get(i)) for i in ids])
        target = float(cambi if cambi is not None else self._cambi_lega)
        target = min(target, 0.97 * len(ids))
        if not len(ids) or grezze.sum() <= 0:
            return grezze
        logit = np.log(np.clip(grezze, 1e-4, 1 - 1e-4) / (1 - np.clip(grezze, 1e-4, 1 - 1e-4)))
        lo, hi = -8.0, 8.0
        for _ in range(60):
            c = 0.5 * (lo + hi)
            somma = (1.0 / (1.0 + np.exp(-(logit + c)))).sum()
            lo, hi = (c, hi) if somma < target else (lo, c)
        return 1.0 / (1.0 + np.exp(-(logit + 0.5 * (lo + hi))))

    def esposizione_subentrato(self):
        """Quota di rischio attesa per chi entra: media su tutti gli ingressi osservati di 1 - H(minuto)."""
        return float(np.mean(1.0 - self._H_array(self.minuti_ingresso)))

    def p_giallo_se_entra(self, lam):
        return float(np.mean(1.0 - np.exp(-lam * (1.0 - self._H_array(self.minuti_ingresso)))))

    def riepilogo(self):
        """Numeri da mostrare nella pagina, così la spiegazione resta sempre quella dei dati."""
        return {
            "partite": self.n_partite,
            "primo_quarto": self.H(15.0),                  # quota dei gialli nei primi 15 minuti
            "ultimo_quarto": 1.0 - self.H(75.0),           # quota dei gialli dal 75' in poi
            "ingresso_medio": float(np.mean(self.minuti_ingresso)),
            "rischio_subentrato": self.esposizione_subentrato(),
            "cambi": self._cambi_lega,
            "p_uscita": dict(self.p_uscita),
            "uscita_media": {r: float(np.mean(self.minuti_uscita[r])) for r in "PDCA"},
        }
