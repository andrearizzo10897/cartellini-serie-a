"""Transfermarkt: statistiche per giocatore e stagione, solo Serie A (convocazioni, presenze, gialli, entrate, uscite, minuti).

Pagina pubblica "prestazioni" di ogni squadra. Le stagioni passate restano in cache per sempre, quella in corso
si ricarica ogni 12 ore. Si fa una richiesta ogni 2 secondi (come chiede il robots.txt del sito): la prima
esecuzione per 5 stagioni richiede circa 4 minuti, poi quasi niente.

Colonne utili ricavate:
- convocato: volte in distinta (titolare o panchina)  -> panchina = convocato - (presenze - entrate)
- presenze, entrate (subentrato), uscite (sostituito)   -> titolare = presenze - entrate
- gialli, doppi gialli, rossi, minuti
"""
import html
import re

import pandas as pd

from config import CACHE, STAGIONE_CORRENTE
from utils import fresca, leggi_json, scarica, scrivi_json, senza_accenti, squadra

BASE = "https://www.transfermarkt.it"
PAUSA = 2.0
RUOLI = (("portiere", "P"), ("difensor", "D"), ("terzin", "D"), ("libero", "D"), ("centrocampist", "C"),
         ("mediano", "C"), ("trequartist", "C"), ("ala ", "A"), ("attaccant", "A"), ("punta", "A"), ("ala", "A"))
RIGA = re.compile(r'<tr class="(?:odd|even)">(.*?)</tr>\s*(?=<tr class="(?:odd|even)">|</tbody>)', re.S)
GIOCATORE = re.compile(r'<a title="([^"]+)" href="/[^"]*/profil/spieler/(\d+)">')
POSIZIONE = re.compile(r"</td></tr><tr><td>([^<]+)</td></tr></table>")
CELLE = re.compile(r'<td[^>]*class="zentriert\s*"[^>]*>(.*?)</td>', re.S)
MINUTI = re.compile(r'<td[^>]*class="rechts\s*"[^>]*>(.*?)</td>', re.S)


def _numero(testo):
    pulito = re.sub(r"<[^>]+>", "", testo).replace(".", "").replace("'", "").strip()
    try:
        return float(pulito)
    except ValueError:
        return 0.0


def _ruolo(testo):
    t = senza_accenti(testo or "").lower() + " "
    for chiave, r in RUOLI:
        if chiave in t:
            return r
    return "C"


def squadre_stagione(anno):
    """[(slug, id, nome)] delle squadre di Serie A in quella stagione."""
    percorso = CACHE / "tm_squadre_{}.json".format(anno)
    ttl = 12 if anno == STAGIONE_CORRENTE else None
    if fresca(percorso, ttl):
        return [tuple(x) for x in leggi_json(percorso)]
    try:
        t = scarica("{}/serie-a/startseite/wettbewerb/IT1/plus/?saison_id={}".format(BASE, anno), pausa=PAUSA).text
    except Exception as e:
        print("  ! Transfermarkt squadre {}: {}".format(anno, e))
        return [tuple(x) for x in leggi_json(percorso)] if percorso.exists() else []
    i = t.find('class="items"')
    tab = t[i:t.find("</table>", i)]
    viste, out = set(), []
    for m in re.finditer(r'<a title="([^"]+)" href="/([a-z0-9\-]+)/startseite/verein/(\d+)(?:/saison_id/\d+)?"', tab):
        if m.group(3) not in viste:
            viste.add(m.group(3))
            out.append((m.group(2), m.group(3), html.unescape(m.group(1))))
    if len(out) >= 18:   # una pagina strana non deve finire in cache
        scrivi_json(percorso, out)
    else:
        print("  ! Transfermarkt {}: elenco squadre non leggibile ({} trovate): pagina vuota o bloccata".format(anno, len(out)))
    return out


def giocatori_squadra(slug, id_squadra, nome_squadra, anno):
    percorso = CACHE / "tm_squadra_{}_{}.json".format(anno, id_squadra)
    ttl = 12 if anno == STAGIONE_CORRENTE else None
    if fresca(percorso, ttl):
        return leggi_json(percorso)
    url = "{}/{}/leistungsdaten/verein/{}/reldata/IT1%26{}/plus/1".format(BASE, slug, id_squadra, anno)
    try:
        t = scarica(url, pausa=PAUSA).text
    except Exception as e:
        print("  ! Transfermarkt {} {}: {}".format(nome_squadra, anno, e))
        return leggi_json(percorso) if percorso.exists() else []
    i = t.find('class="items"')
    corpo = t[i:t.find("</table>\n", i) if t.find("</table>\n", i) > 0 else len(t)]
    righe = []
    for blocco in RIGA.findall(corpo):
        g = GIOCATORE.search(blocco)
        if not g:
            continue
        pos = POSIZIONE.search(blocco)
        celle = [_numero(c) for c in CELLE.findall(blocco)]
        # celle: età, nazionalità (immagine -> 0), convocato, presenze, gol, assist, gialli, doppi, rossi, entrate, uscite
        if len(celle) < 11:
            continue
        minuti = MINUTI.findall(blocco)
        righe.append({
            "stagione": anno, "squadra": squadra(nome_squadra), "id_tm": g.group(2),
            "nome": html.unescape(g.group(1)), "ruolo": _ruolo(pos.group(1) if pos else ""),
            "convocato": celle[2], "presenze": celle[3], "gialli": celle[6], "doppi": celle[7], "rossi": celle[8],
            "entrate": celle[9], "uscite": celle[10], "minuti": _numero(minuti[-1]) if minuti else 0.0,
        })
    if len(righe) >= 10:   # una pagina vuota o bloccata non deve finire in cache
        scrivi_json(percorso, righe)
    else:
        print("  ! Transfermarkt {} {}: giocatori non leggibili ({} trovati)".format(nome_squadra, anno, len(righe)))
    return righe


def carica(stagioni):
    """DataFrame con una riga per giocatore, squadra e stagione."""
    righe = []
    for anno in stagioni:
        for slug, id_squadra, nome in squadre_stagione(anno):
            righe += giocatori_squadra(slug, id_squadra, nome, anno)
    colonne = ["stagione", "squadra", "id_tm", "nome", "ruolo", "convocato", "presenze", "gialli", "doppi", "rossi",
               "entrate", "uscite", "minuti"]
    df = pd.DataFrame(righe, columns=colonne)
    df["nome_completo"] = [senza_accenti(n).lower() for n in df["nome"]]
    df["titolare"] = (df["presenze"] - df["entrate"]).clip(lower=0)
    df["panchina"] = (df["convocato"] - df["titolare"]).clip(lower=0)
    return df
