"""Formazioni ufficiali dagli articoli dei siti di calcio: si cercano e si leggono senza dipendere da come il sito è fatto.

Gli indirizzi e i titoli cambiano spesso (SosFanta, novembre 2026), quindi:
- l'articolo è qualunque link del sito il cui ultimo pezzo contiene "ufficial" e le due squadre nell'ordine casa, trasferta;
- la formazione è qualunque blocco del testo con 11 nomi separati da virgole e punti e virgola ("Stankovic; Halhal, Moreno; ...");
- vale solo se tutti gli 11 nomi corrispondono alla rosa della squadra (sky.da_nomi) e l'articolo è del giorno della partita.
Se qualcosa non torna restituisce None e la pagina usa le altre fonti.
"""
import html
import re

import config
from fonti import sky
from utils import leggi_json_o, scarica, scrivi_json

UA = sky.UA
ALIAS = {"verona": ["hellas-verona", "verona"]}
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
_NOME = r"(?:[^\W\d_]\.\s?)?[^\W\d_]+(?:['’ -][^\W\d_]+){0,3}"
_BLOCCO = re.compile(r"{n}(?:\s*[;,]\s*{n}){{10}}(?!\s*[;,]\s*[^\W\d_])".format(n=_NOME))


SALVATE = config.BASE / "formazioni_ufficiali.json"   # fuori da dati/: il workflow ripristina quella cartella dalla cache


def salvate():
    """{id partita: formazione} trovate dal PC: su GitHub alcuni siti non rispondono, così online si vedono le stesse."""
    return leggi_json_o(SALVATE, {})


def salva(trovate, prossime):
    """Aggiunge le formazioni trovate e toglie le partite non più in programma. True se il file è cambiato."""
    prima = salvate()
    ids = {ev["id"] for ev in prossime}
    dopo = {k: v for k, v in {**prima, **trovate}.items() if k in ids}
    if dopo == prima:
        return False
    scrivi_json(SALVATE, dopo)
    return True


def slug(nome):
    return ALIAS.get(nome, [sky._slug(nome)])


def trova(ev, dominio, elenchi, ricerca, sito):
    """Indirizzi degli articoli "formazioni ufficiali" della partita. ricerca: indirizzo di ricerca del sito con {c} e {t}, o None."""
    coppie = [(c, t) for c in slug(ev["casa"]) for t in slug(ev["trasf"])]
    cerca = re.compile(r"(?:https://{})?(/[a-z0-9/_-]*ufficial[a-z0-9/_-]*)".format(re.escape(dominio)))
    trovati = []
    for url in list(elenchi) + ([ricerca.format(c=c, t=t) for c, t in coppie] if ricerca else []):
        try:
            testo = scarica(url, headers=UA, pausa=0.1, tentativi=1).text
        except Exception:  # noqa: BLE001 - rete: provo l'elenco dopo
            sky.problemi.add(sito + " non risponde")
            continue
        for percorso in cerca.findall(testo):
            nome = percorso.rstrip("/").rsplit("/", 1)[-1]
            link = "https://{}{}".format(dominio, percorso)
            if link not in trovati and "ufficial" in nome and any(
                    re.search(r"(^|-){}-(.*-)?{}(-|$)".format(c, t), nome) for c, t in coppie):
                trovati.append(link)
        if trovati:
            break
    return trovati


def del_giorno(raw, testo, inizio):
    """L'articolo è di oggi? Con gli indirizzi non fissi potrebbe essere quello di una stagione passata, con la stessa partita."""
    return "{} {}".format(inizio.day, MESI[inizio.month - 1]) in testo.lower() or inizio.strftime("%Y-%m-%d") in raw \
        or inizio.strftime("%d_%m_%Y") in raw


def testo_pagina(raw):
    pulito = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", pulito)))


def blocchi(testo):
    """Tutti i blocchi di 11 nomi del testo, con almeno un punto e virgola: un elenco di soli nomi non è una formazione."""
    out = []
    for m in _BLOCCO.finditer(testo):
        if ";" in m.group(0):
            nomi = [n.strip() for n in re.split(r"[;,]", m.group(0))]
            if nomi not in out:
                out.append(nomi)
    return out


def leggi(ev, ultima_formazione, tradotti, urls, sito):
    """Formazioni nel formato di espn.formazioni() dal primo articolo che si legge con certezza, o None."""
    for url in urls:
        try:
            r = scarica(url, headers=UA, pausa=0.1, tentativi=1)
        except Exception:  # noqa: BLE001
            sky.problemi.add(sito + " non risponde")
            continue
        testo = testo_pagina(r.text)
        if ev.get("inizio") and not del_giorno(r.text, testo, ev["inizio"]):
            continue
        trovati = blocchi(testo)
        if len(trovati) < 2:
            sky.problemi.add("articolo di {} senza le due formazioni (formato cambiato?)".format(sito))
            continue
        forma = sky.da_nomi(ev, ultima_formazione, [(None, trovati[0]), (None, trovati[1])], tradotti)
        if forma:
            return forma
    return None
