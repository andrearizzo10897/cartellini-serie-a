"""ESPN (API pubblica non ufficiale): calendario, formazioni e statistiche per giocatore.

Una chiamata "scoreboard" per giorno e una "summary" per partita. Tutto ciò che è finito
resta in cache per sempre, quindi dopo la prima esecuzione si scaricano solo le partite nuove.
"""
from datetime import datetime

from dateutil import tz

import modello
from config import CACHE
from utils import fresca, leggi_json, scarica, scrivi_json, squadra

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1"
ROMA = tz.gettz("Europe/Rome")


def _ora_locale(iso):
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%MZ").replace(tzinfo=tz.UTC)
    return dt.astimezone(ROMA).replace(tzinfo=None)


def _quote(odds):
    """Quote 1X2 (moneyline) di chiusura, o di apertura, -> (p1, pX, p2) senza margine. None se non ci sono.

    ESPN le toglie a partita finita: ci sono solo per quelle ancora da giocare.
    """
    for o in odds or []:
        ml = (o or {}).get("moneyline")
        for fase in ("close", "open"):
            try:
                q = [float(ml[x][fase]["odds"]) for x in ("home", "draw", "away")]
                return tuple(float(p) for p in modello.probabilita_da_moneyline(*q))
            except (TypeError, KeyError, ValueError):
                continue
    return None


def partite_del_giorno(giorno):
    """Elenco delle partite di un giorno (oggetto date)."""
    percorso = CACHE / "espn" / "calendario_{}.json".format(giorno.strftime("%Y%m%d"))
    js = None
    if percorso.exists():
        js = leggi_json(percorso)
        tutte_finite = all(e["status"]["type"]["state"] == "post" for e in js.get("events", []))
        if not ((tutte_finite and js.get("events")) or fresca(percorso, 0.1)):
            js = None
    if js is None:
        js = scarica(BASE + "/scoreboard", params={"dates": giorno.strftime("%Y%m%d")}).json()
        scrivi_json(percorso, js)
    out = []
    for e in js.get("events", []):
        comp = e["competitions"][0]["competitors"]
        casa = next(c for c in comp if c["homeAway"] == "home")
        trasf = next(c for c in comp if c["homeAway"] == "away")
        out.append({
            "id": e["id"],
            "inizio": _ora_locale(e["date"]),
            "casa": squadra(casa["team"]["displayName"]),
            "trasf": squadra(trasf["team"]["displayName"]),
            "stato": e["status"]["type"]["state"],  # pre / in / post
            "gol_c": casa.get("score"), "gol_t": trasf.get("score"),
            "quote": _quote(e["competitions"][0].get("odds")),
        })
    return out


def _leggi_formazioni(js):
    out = {}
    for r in js.get("rosters", []):
        giocatori = []
        for p in r.get("roster", []):
            st = {s["name"]: s["value"] for s in p.get("stats", [])}
            a = p["athlete"]
            giocatori.append({
                "id": str(a["id"]),
                "nome": a.get("fullName") or a.get("displayName", ""),
                "ruolo_espn": (p.get("position") or {}).get("abbreviation", ""),
                "titolare": bool(p.get("starter")),
                "entrato": bool(p.get("subbedIn")),
                "uscito": bool(p.get("subbedOut")),
                "presenze": st.get("appearances", 0) or 0,
                "gialli": st.get("yellowCards", 0) or 0,
                "rossi": st.get("redCards", 0) or 0,
                "falli": st.get("foulsCommitted", 0) or 0,
                "falli_sub": st.get("foulsSuffered", 0) or 0,
            })
        out[r["homeAway"]] = {
            "squadra": squadra(r.get("team", {}).get("displayName", "")),
            "formazione": r.get("formation"),
            "giocatori": giocatori,
        }
    return out


def formazioni(id_partita, stato):
    """Formazioni (titolari + panchina) con le statistiche della partita, se disponibili."""
    percorso = CACHE / "espn" / "partita_{}.json".format(id_partita)
    if not fresca(percorso, None if stato == "post" else 0.08):
        try:
            js = scarica(BASE + "/summary", params={"event": id_partita}).json()
        except Exception as e:
            print("  ! ESPN partita {}: {}".format(id_partita, e))
            if not percorso.exists():
                return {}
            js = leggi_json(percorso)
        else:
            scrivi_json(percorso, js)
    else:
        js = leggi_json(percorso)
    return _leggi_formazioni(js)


def ufficiale(forma):
    """Le formazioni sono ufficiali quando entrambe le squadre hanno 11 titolari."""
    return bool(forma) and all(sum(1 for g in f["giocatori"] if g["titolare"]) == 11 for f in forma.values()) \
        and len(forma) == 2
