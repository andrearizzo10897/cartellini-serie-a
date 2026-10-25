"""Sky Sport: formazioni ufficiali, di solito prima che ESPN le pubblichi.

Due pagine per partita:
- "formazioni": tabella con titolari e riserve di ogni squadra, numero di maglia e un link per giocatore che contiene
  il NOME COMPLETO (".../atleti/pedro-antonio-pereira-goncalves/123" dietro al testo "Pote"). Prima del fischio è
  "probabili formazioni" (solo i titolari hanno il link), dopo un po' diventa "formazioni ufficiali" (titolari e panchina);
- "risultato-gol": la diretta, che pubblica per prima le ufficiali in testo: "FORMAZIONI UFFICIALI VENEZIA (3-5-2):
  Stankovic; Halhal, ...; Yeboah, Adams. All. Nicola NAPOLI (3-4-2-1): ..." (solo cognomi, a volte soprannomi).

Con la pagina ufficiale si legge tutto da lì, senza ambiguità. Con il solo testo, i soprannomi si traducono con i nomi
completi della stessa pagina "formazioni" (anche quella probabile) o con la tabella SOPRANNOMI. Un nome che non si
riconosce con certezza fa scartare la fonte: non si indovina (una prova su 78 partite ha mostrato che scegliere "per
esclusione" tra i titolari abituali sbaglia una volta su tre quando il giocatore ruota). Se la pagina non c'è, non è ancora
ufficiale o cambia formato, restituisce None e la pagina usa le altre fonti.
"""
import html
import re

from config import CACHE
from fonti import espn
from utils import fresca, leggi_json, scarica, scrivi_json, senza_accenti

BASE = "https://sport.sky.it/calcio/serie-a/partite/{anno}/giornata-{g}/{slug}/{pagina}"
ELENCO = "https://sport.sky.it/calcio/serie-a/probabili-formazioni"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"}
# nomi con cui Sky costruisce gli indirizzi, quando non coincidono con il nostro nome canonico
ALIAS = {"verona": ["hellas-verona", "verona"]}
# soprannomi sicuri, per quando la pagina "formazioni" non c'è: "pote" è Pedro Gonçalves
SOPRANNOMI = {"pote": "Pedro Goncalves"}
ELEMENTI = re.compile(
    r'ftbl__report-tabs-panel__header-td">([^<]*)<'                                                  # 1: titolo della sezione
    r'|data-panel-(left|right)="true"'                                                                # 2: casa (left) o trasferta
    r'|jerseyNum">(\d+)</span><a[^>]*href="https://sport\.sky\.it/calcio/atleti/([a-z0-9\-]+)/\d+"[^>]*>([^<]*)</a>')  # 3-5


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


def _scarica(ev, anno, giornate, pagina):
    """(html, giornata) di una pagina Sky della partita, o (None, None) se non si trova."""
    for g in giornate:
        for c in ALIAS.get(ev["casa"], [_slug(ev["casa"])]):
            for t in ALIAS.get(ev["trasf"], [_slug(ev["trasf"])]):
                try:
                    r = scarica(BASE.format(anno=anno, g=g, slug=c + "-" + t, pagina=pagina), headers=UA, pausa=0.1, tentativi=1)
                except Exception:  # noqa: BLE001 - 404 o rete: provo la combinazione dopo
                    continue
                return r.text, g
    return None, None


def _testo(raw):
    pulito = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", pulito)))


def _tok(s):
    return [t for t in re.split(r"[^a-z]+", senza_accenti(s).lower()) if t]


def _chiave(nome):
    """Nome come lo scrive Sky, senza le iniziali ("Jiménez Á." -> "jimenez", "Pote" -> "pote"): serve a confrontare i due elenchi."""
    return " ".join(t for t in _tok(nome) if len(t) > 1)


def leggi_formazioni(raw):
    """Pagina "formazioni" -> {"ufficiale", "moduli", "titolari": {home, away}, "riserve": {home, away}}.

    Ogni giocatore è (numero, nome completo dall'indirizzo, nome come scritto da Sky). None se la tabella non si legge."""
    if not raw or "ftbl__report-tabs-panel" not in raw:
        return None
    titolo = re.search(r"<title>([^<]*)</title>", raw)
    moduli = tuple((re.search(r'formation-%s">([\d-]+)<' % lato, raw) or [None, None])[1] for lato in ("home", "away"))
    sezione, lato = None, "home"
    titolari, riserve = {"home": [], "away": []}, {"home": [], "away": []}
    for m in ELEMENTI.finditer(raw):
        if m.group(1) is not None:
            sezione = m.group(1).strip()
        elif m.group(2):
            lato = "home" if m.group(2) == "left" else "away"
        elif sezione in ("Titolari", "Riserve"):
            giocatore = (int(m.group(3)), m.group(4).replace("-", " "), html.unescape(m.group(5)).strip())
            (titolari if sezione == "Titolari" else riserve)[lato].append(giocatore)
    return {"ufficiale": bool(titolo and "ufficial" in titolo.group(1).lower()), "moduli": moduli,
            "titolari": titolari, "riserve": riserve}


def carica_pagina(ev, anno, giornata=None):
    """Legge la pagina "formazioni" della partita (probabile o ufficiale). None se non c'è."""
    giornate = [giornata + d for d in (0, 1, -1)] if giornata else list(range(1, 39))
    raw, g = _scarica(ev, anno, giornate, "formazioni")
    dati = leggi_formazioni(raw)
    if dati:
        dati["giornata"] = g
    return dati


def alias(dati):
    """{"home": {nome scritto da Sky: nome completo}, "away": ...} dai giocatori con link della pagina "formazioni"."""
    out = {"home": {}, "away": {}}
    for sezione in ("titolari", "riserve"):
        for lato in out:
            for _, completo, scritto in (dati or {}).get(sezione, {}).get(lato, []):
                if _chiave(scritto):
                    out[lato][_chiave(scritto)] = completo
    return out


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


def _trova(nome_sky, rosa, usati, portiere=False):
    """Giocatore della rosa che corrisponde a un nome di Sky (solo cognome, a volte con l'iniziale o due parole).

    A parità di nome (due Martínez) vince chi ha il ruolo giusto: il primo della lista di Sky è il portiere."""
    t = _tok(SOPRANNOMI.get(" ".join(_tok(nome_sky)), nome_sky))
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


def _trova_completo(completo, rosa, usati, portiere=False, numero=None):
    """Giocatore ESPN per un nome completo preso dall'indirizzo di Sky ("pedro antonio pereira goncalves").

    ESPN ha di solito il nome più corto ("Pedro Gonçalves"): le sue parole devono stare tutte nel nome completo, e vince
    chi ne ha di più. A parità decide il ruolo (portiere) o il numero di maglia; se resta il dubbio, nessuno."""
    parole = set(_tok(completo))
    candidati = []
    for g in rosa:
        if g["id"] in usati:
            continue
        p = set(_tok(g["nome"]))
        if p and p <= parole:
            candidati.append((len(p), g))
    if not candidati:
        return _trova(completo, rosa, usati, portiere)
    massimo = max(n for n, _ in candidati)
    migliori = [g for n, g in candidati if n == massimo]
    if len(migliori) > 1 and numero is not None:
        con_numero = [g for g in migliori if str(g.get("numero")) == str(numero)]
        migliori = con_numero or migliori
    if len(migliori) > 1:
        per_ruolo = [g for g in migliori if (g.get("ruolo_espn") == "G") == portiere]
        migliori = per_ruolo or migliori
    return migliori[0] if len(migliori) == 1 else None


def _rosa(id_squadra):
    """Rosa completa dell'ESPN [{id, nome, ruolo_espn, numero}], per chi non era nell'ultima partita e per i numeri di maglia."""
    percorso = CACHE / "espn" / "rosa_{}.json".format(id_squadra)
    try:
        if fresca(percorso, 1):
            return leggi_json(percorso)
        js = scarica(espn.BASE + "/teams/{}/roster".format(id_squadra)).json()
        rosa = [{"id": str(a["id"]), "nome": a.get("fullName") or a.get("displayName", ""),
                 "ruolo_espn": (a.get("position") or {}).get("abbreviation", ""), "numero": a.get("jersey")}
                for a in js.get("athletes", [])]
        scrivi_json(percorso, rosa)
        return rosa
    except Exception:  # noqa: BLE001 - rete: si lavora con l'ultima formazione
        return []


def _giocatore(g, titolare):
    return {"id": g["id"], "nome": g["nome"], "ruolo_espn": g.get("ruolo_espn", ""), "titolare": titolare,
            "entrato": False, "uscito": False, "presenze": 0, "gialli": 0, "rossi": 0, "falli": 0, "falli_sub": 0}


def _squadra(ev, lato, ultima_formazione):
    """(squadra, rosa completa: prima chi ha giocato l'ultima, poi il resto, ultima formazione)."""
    sq, id_sq = (ev["casa"], ev["id_casa"]) if lato == "home" else (ev["trasf"], ev["id_trasf"])
    ultima = [dict(g) for g in ultima_formazione.get(sq, [])]
    rosa = {g["id"]: g for g in _rosa(id_sq)}
    for g in ultima:
        rosa[g["id"]] = dict(rosa.get(g["id"], {}), **g)
    return sq, list(rosa.values()), ultima


NON_LETTA = object()


def ufficiali(ev, anno, ultima_formazione, giornata=None, dati=NON_LETTA):
    """Formazioni ufficiali di Sky nel formato di espn.formazioni(), o None se non ci sono ancora.

    dati: pagina "formazioni" già letta con carica_pagina (None = letta ma non c'è); se non si passa la leggo qui."""
    if dati is NON_LETTA:
        dati = carica_pagina(ev, anno, giornata)
    if dati and dati["ufficiale"]:
        forma = _da_pagina(ev, ultima_formazione, dati)
        if forma:
            return forma
    g = [dati["giornata"]] if dati and dati.get("giornata") else ([giornata + d for d in (0, 1, -1)] if giornata else list(range(1, 39)))
    raw, _ = _scarica(ev, anno, g, "risultato-gol")
    return da_nomi(ev, ultima_formazione, _estrai(_testo(raw)) if raw else None, alias(dati))


def _da_pagina(ev, ultima_formazione, dati):
    """Formazione dalla pagina "formazioni" ufficiale: undici e panchina con i nomi completi. None se manca qualcuno."""
    forma = {}
    for lato in ("home", "away"):
        xi = dati["titolari"][lato]
        if len(xi) != 11:
            return None
        sq, tutti, ultima = _squadra(ev, lato, ultima_formazione)
        usati, titolari = set(), []
        for k, (numero, completo, _) in enumerate(xi):
            g = _trova_completo(completo, tutti, usati, portiere=(k == 0), numero=numero)
            if not g:
                return None   # un nome che non si riconosce con certezza: meglio un'altra fonte
            usati.add(g["id"])
            titolari.append(_giocatore(g, True))
        panchina = []
        for numero, completo, _ in dati["riserve"][lato]:
            g = _trova_completo(completo, tutti, usati, numero=numero)
            if g:
                usati.add(g["id"])
                panchina.append(_giocatore(g, False))
        if len(panchina) < 5:   # panchina non letta: l'ultima formazione, come per le altre fonti
            panchina = [_giocatore(g, False) for g in (ultima or tutti) if g["id"] not in usati]
        forma[lato] = {"squadra": sq, "formazione": dati["moduli"][0 if lato == "home" else 1], "giocatori": titolari + panchina}
    return forma


def da_nomi(ev, ultima_formazione, estratte, tradotti=None):
    """Dalle liste di cognomi [(modulo o None, [11 nomi]) casa, trasferta] alla formazione nel formato di ESPN.

    Serve anche a SosFanta. tradotti = alias(dati): i soprannomi si traducono con i nomi completi della pagina "formazioni".
    None se mancano le liste o se anche un solo nome non si riconosce con certezza."""
    if not estratte:
        return None
    forma = {}
    for lato, (modulo, nomi) in zip(("home", "away"), estratte):
        sq, tutti, ultima = _squadra(ev, lato, ultima_formazione)
        usati, titolari = set(), []
        for k, n in enumerate(nomi):
            completo = (tradotti or {}).get(lato, {}).get(_chiave(n))
            g = (completo and _trova_completo(completo, tutti, usati, portiere=(k == 0))) or _trova(n, tutti, usati, portiere=(k == 0))
            if not g:
                return None   # soprannome sconosciuto: meglio le altre fonti che una formazione sbagliata
            usati.add(g["id"])
            titolari.append(_giocatore(g, True))
        panchina = [_giocatore(g, False) for g in (ultima or tutti) if g["id"] not in usati]
        forma[lato] = {"squadra": sq, "formazione": modulo, "giocatori": titolari + panchina}
    return forma
