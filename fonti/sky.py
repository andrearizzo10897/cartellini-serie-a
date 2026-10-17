"""Sky Sport: formazioni ufficiali, che compaiono nella pagina "risultato-gol" della partita circa un'ora prima
del fischio d'inizio, di solito prima che ESPN le pubblichi.

Il testo ha la forma  "FORMAZIONI UFFICIALI  VENEZIA (3-5-2): Stankovic; Halhal, ...; Yeboah, Adams. All. Nicola
NAPOLI (3-4-2-1): Meret; ... Lucca. All. Allegri"  (solo cognomi). Li abbino ai giocatori della rosa ESPN.
Se la pagina non c'è, non è ancora ufficiale o cambia formato, restituisce None e la pagina usa le altre fonti.
"""
import html
import re

from config import CACHE
from fonti import espn
from utils import fresca, leggi_json, scarica, scrivi_json, senza_accenti

BASE = "https://sport.sky.it/calcio/serie-a/partite/{anno}/giornata-{g}/{slug}/risultato-gol"
ELENCO = "https://sport.sky.it/calcio/serie-a/probabili-formazioni"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
# nomi con cui Sky costruisce gli indirizzi, quando non coincidono con il nostro nome canonico
ALIAS = {"verona": ["hellas-verona", "verona"]}
RUOLO = {"G": "P", "D": "D", "M": "C", "F": "A"}


def _slug(nome):
    return re.sub(r"[^a-z0-9]+", "-", senza_accenti(nome).lower()).strip("-")


def giornata_corrente():
    """Numero di giornata che Sky mostra nella pagina delle probabili formazioni (None se non si legge)."""
    try:
        testo = scarica(ELENCO, headers=UA, pausa=0.1, tentativi=2).text
    except Exception:  # noqa: BLE001 - rete: si prova senza
        return None
    n = [int(x) for x in re.findall(r"giornata-(\d+)", testo)]
    return max(n) if n else None


def _pagina(ev, anno, giornate):
    """Testo pulito della pagina Sky della partita, o None se non si trova."""
    for g in giornate:
        for c in ALIAS.get(ev["casa"], [_slug(ev["casa"])]):
            for t in ALIAS.get(ev["trasf"], [_slug(ev["trasf"])]):
                try:
                    r = scarica(BASE.format(anno=anno, g=g, slug=c + "-" + t), headers=UA, pausa=0.1, tentativi=1)
                except Exception:  # noqa: BLE001 - 404 o rete: provo la combinazione dopo
                    continue
                pulito = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", r.text)
                return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", pulito)))
    return None


def _estrai(testo):
    """[(modulo, [nomi in ordine di formazione])] per casa e trasferta, o None se non ci sono le ufficiali."""
    i = testo.find("FORMAZIONI UFFICIALI")
    if i < 0:
        return None
    blocchi = re.findall(r"[A-ZÀ-Ü][A-ZÀ-Ü' .-]+ \s*\((\d(?:-\d){1,4})\)\s*:\s*(.+?)\.\s*All\.", testo[i:i + 3000])
    if len(blocchi) < 2:
        return None
    out = []
    for modulo, elenco in blocchi[:2]:
        nomi = [n.strip() for n in re.split(r"[;,]", elenco) if n.strip()]
        if len(nomi) != 11:
            return None
        out.append((modulo, nomi))
    return out


def _tok(s):
    return [t for t in re.split(r"[^a-z]+", senza_accenti(s).lower()) if t]


def _trova(nome_sky, rosa, usati, portiere=False):
    """Giocatore della rosa che corrisponde a un nome di Sky (solo cognome, a volte con l'iniziale o due parole).

    A parità di nome (due Martínez) vince chi ha il ruolo giusto: il primo della lista di Sky è il portiere."""
    t = _tok(nome_sky)
    if not t:
        return None
    migliori = []
    for g in rosa:
        if g["id"] in usati:
            continue
        pieces = _tok(g["nome"])
        ok = all((len(x) == 1 and any(p[0] == x for p in pieces[:-1])) or x in pieces for x in t)
        if ok:
            sbagliato = (g.get("ruolo_espn") == "G") != portiere if g.get("ruolo_espn") else False
            migliori.append(((sbagliato, -sum(len(x) for x in t if x in pieces)), g))
    if migliori:
        return min(migliori, key=lambda m: m[0])[1]
    # soprannomi ("Kike Perez" per Enrique Pérez): se l'ultima parola è il cognome di un solo giocatore, è lui
    sol = [g for g in rosa if g["id"] not in usati and t[-1] in _tok(g["nome"])[1:]]
    return sol[0] if len(sol) == 1 else None


def _rosa(id_squadra):
    """Rosa completa dell'ESPN [{id, nome, ruolo_espn}], per i titolari che non erano nell'ultima partita."""
    percorso = CACHE / "espn" / "rosa_{}.json".format(id_squadra)
    try:
        if fresca(percorso, 1):
            return leggi_json(percorso)
        js = scarica(espn.BASE + "/teams/{}/roster".format(id_squadra)).json()
        rosa = [{"id": str(a["id"]), "nome": a.get("fullName") or a.get("displayName", ""),
                 "ruolo_espn": (a.get("position") or {}).get("abbreviation", "")} for a in js.get("athletes", [])]
        scrivi_json(percorso, rosa)
        return rosa
    except Exception:  # noqa: BLE001 - rete: si lavora con l'ultima formazione
        return []


def _giocatore(g, titolare):
    return {"id": g["id"], "nome": g["nome"], "ruolo_espn": g.get("ruolo_espn", ""), "titolare": titolare,
            "entrato": False, "uscito": False, "presenze": 0, "gialli": 0, "rossi": 0, "falli": 0, "falli_sub": 0}


def ufficiali(ev, anno, ultima_formazione, giornata=None):
    """Formazioni ufficiali di Sky nel formato di espn.formazioni(), o None se non ci sono ancora."""
    giornate = [giornata + d for d in (0, 1, -1)] if giornata else list(range(1, 39))
    testo = _pagina(ev, anno, giornate)
    estratte = _estrai(testo) if testo else None
    if not estratte:
        return None
    forma = {}
    for lato, sq, id_sq, (modulo, nomi) in (("home", ev["casa"], ev["id_casa"], estratte[0]),
                                            ("away", ev["trasf"], ev["id_trasf"], estratte[1])):
        ultima = [dict(g) for g in ultima_formazione.get(sq, [])]
        rosa = {g["id"]: g for g in _rosa(id_sq)}
        rosa.update({g["id"]: g for g in ultima})   # prima chi ha giocato l'ultima, poi il resto della rosa
        tutti = list(rosa.values())
        usati, titolari = set(), []
        for k, n in enumerate(nomi):
            g = _trova(n, tutti, usati, portiere=(k == 0))
            if not g:
                return None   # un nome non riconosciuto: meglio le altre fonti che una formazione sbagliata
            usati.add(g["id"])
            titolari.append(_giocatore(g, True))
        panchina = [_giocatore(g, False) for g in (ultima or tutti) if g["id"] not in usati]
        forma[lato] = {"squadra": sq, "formazione": modulo, "giocatori": titolari + panchina}
    return forma
