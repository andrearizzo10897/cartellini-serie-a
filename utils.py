"""Funzioni comuni: download con cache e normalizzazione dei nomi."""
import json
import re
import time
import unicodedata

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124 Safari/537.36"
}


def scarica(url, params=None, headers=None, tentativi=3, pausa=0.3, timeout=40):
    """GET con qualche tentativo; una piccola pausa tiene bassa la pressione sui siti."""
    h = dict(UA)
    if headers:
        h.update(headers)
    errore = None
    for i in range(tentativi):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            r.raise_for_status()
            time.sleep(pausa)
            return r
        except requests.RequestException as e:
            errore = e
            time.sleep(1.5 * (i + 1))
    raise errore


def scarica_json(url, params=None, tentativi=3, **altri):
    """Come scarica, ma restituisce il JSON già letto. Una risposta vuota o troncata con il codice 200 (ESPN a volte
    risponde così: il 31/10/2026 ha fermato l'aggiornamento sul PC) si riprova come un errore di rete."""
    for i in range(tentativi):
        try:
            return scarica(url, params=params, tentativi=1, **altri).json()
        except (requests.RequestException, ValueError):
            if i == tentativi - 1:
                raise
            time.sleep(1.5 * (i + 1))


def fresca(percorso, ttl_ore):
    """True se il file in cache esiste ed è ancora valido (ttl None = per sempre)."""
    if not percorso.exists():
        return False
    if ttl_ore is None:
        return True
    return (time.time() - percorso.stat().st_mtime) < ttl_ore * 3600


def leggi_json(percorso):
    return json.loads(percorso.read_text(encoding="utf-8"))


def scrivi_json(percorso, oggetto):
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(oggetto, ensure_ascii=False), encoding="utf-8")


def senza_accenti(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# ---- Squadre -------------------------------------------------------------------------------
# Ogni fonte scrive i nomi in modo diverso ("AC Milan", "Milan", "MILAN"): li riduco a un nome unico.
_PAROLE_VUOTE = {"ac", "as", "fc", "calcio", "hellas", "ssc", "us", "ss", "acf", "bc", "cfc", "sc", "afc", "spa", "ssd"}
_ALIAS = {
    "inter milan": "inter", "internazionale": "inter", "fc internazionale": "inter",
    "internazionale milano": "inter", "milan": "milan",
}
_NOMI_BELLI = {
    "inter": "Inter", "milan": "Milan", "verona": "Verona", "roma": "Roma", "lazio": "Lazio",
    "juventus": "Juventus", "napoli": "Napoli", "atalanta": "Atalanta", "fiorentina": "Fiorentina",
}


def squadra(nome):
    s = senza_accenti(str(nome)).lower().replace("&", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    parole = [p for p in s.split() if p not in _PAROLE_VUOTE and not p.isdigit()]
    s = " ".join(parole)
    return _ALIAS.get(s, s)


def nome_squadra(canonico):
    return _NOMI_BELLI.get(canonico, canonico.title())


DERBY = [
    {"inter", "milan"}, {"roma", "lazio"}, {"juventus", "torino"}, {"genoa", "sampdoria"},
    {"bologna", "fiorentina"}, {"napoli", "roma"}, {"verona", "chievo"},
]


def e_derby(casa, trasf):
    return {casa, trasf} in DERBY
