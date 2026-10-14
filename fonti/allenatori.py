"""Allenatori di ogni squadra con le date di inizio e fine incarico (Transfermarkt, pagina pubblica).

Serve a sapere chi allenava una squadra in una certa partita. Una richiesta per squadra, ogni 2 secondi;
si ricarica ogni 24 ore perché a stagione in corso gli allenatori possono cambiare.
"""
import html
import re

import pandas as pd

from config import CACHE, STAGIONE_CORRENTE
from fonti import transfermarkt
from utils import fresca, leggi_json, scarica, scrivi_json, squadra

URL = "{}/{}/mitarbeiterhistorie/verein/{}/personalie_id/1".format(transfermarkt.BASE, "{slug}", "{id}")
DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _data(testo):
    m = DATA.search(testo)
    return "{}-{}-{}".format(m.group(3), m.group(2), m.group(1)) if m else None


def _storia_squadra(slug, id_squadra, nome):
    percorso = CACHE / "tm_allenatori_{}.json".format(id_squadra)
    if fresca(percorso, 24):
        return leggi_json(percorso)
    try:
        t = scarica(URL.format(slug=slug, id=id_squadra), pausa=transfermarkt.PAUSA).text
    except Exception as e:
        print("  ! allenatori {}: {}".format(nome, e))
        return leggi_json(percorso) if percorso.exists() else []
    i = t.find('class="items"')
    tab = t[i:t.find("</table>\n", i)]
    out = []
    for blocco in re.split(r'<tr class="(?:odd|even)">', tab)[1:]:
        m = re.search(r'<a title="([^"]+)" id="(\d+)" href="/[^"]*/profil/trainer/\d+">', blocco)
        if not m:
            continue
        date = DATA.findall(blocco)
        # le date nella riga sono: nascita, dal, (termine se ha lasciato)
        iso = ["{}-{}-{}".format(d[2], d[1], d[0]) for d in date]
        if len(iso) < 2:
            continue
        out.append({"allenatore": html.unescape(m.group(1)), "id_all": m.group(2), "dal": iso[1],
                    "al": iso[2] if len(iso) >= 3 else None})
    if out:
        scrivi_json(percorso, out)
    return out


def carica(stagioni):
    """DataFrame (squadra, allenatore, id_all, dal, al) per le squadre di Serie A delle stagioni indicate."""
    viste, righe = set(), []
    for anno in stagioni:
        for slug, id_squadra, nome in transfermarkt.squadre_stagione(anno):
            if id_squadra in viste:
                continue
            viste.add(id_squadra)
            for r in _storia_squadra(slug, id_squadra, nome):
                righe.append({"squadra": squadra(nome), **r})
    return pd.DataFrame(righe, columns=["squadra", "allenatore", "id_all", "dal", "al"])


def allenatore_a(tab, nome_squadra, data_iso):
    """Nome dell'allenatore della squadra alla data (AAAA-MM-GG), o None."""
    t = tab[tab["squadra"] == nome_squadra]
    for r in t.itertuples():
        if r.dal <= data_iso and (pd.isna(r.al) or data_iso <= r.al):
            return r.allenatore
    return None
