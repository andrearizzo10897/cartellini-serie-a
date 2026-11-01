"""AIA (Associazione Italiana Arbitri): designazioni arbitrali della Serie A.

Il sito mostra solo l'ultima giornata, quindi a ogni esecuzione salvo quella che trovo in
dati/designazioni.json: lo storico degli arbitri 2026/27 cresce da solo giornata dopo giornata.
"""
import html
import re
from datetime import date, timedelta

from config import DATI, stagione_di
from utils import leggi_json, scarica, scrivi_json, senza_accenti, squadra

BASE = "https://www.aia-figc.it"
ARCHIVIO = DATI / "designazioni.json"
GIORNI = r"(?:Luned[iì]|Marted[iì]|Mercoled[iì]|Gioved[iì]|Venerd[iì]|Sabato|Domenica)"


def _righe(pagina):
    pagina = re.sub(r"<script.*?</script>|<style.*?</style>", "", pagina, flags=re.S)
    testo = html.unescape(re.sub(r"<[^>]+>", "\n", pagina))
    testo = testo.replace("\xa0", " ").replace("\ufeff", "")
    return [r.strip() for r in testo.splitlines() if r.strip()]


def _pagina(url):
    return scarica(url).content.decode("utf-8", errors="replace")


def _interpreta(pagina):
    """Estrae titolo, data di pubblicazione e partite da una pagina di designazioni."""
    righe = _righe(pagina)
    # la data di pubblicazione (es. "07/10/2026") sta subito dopo il titolo vero della pagina
    pos = next((i for i, r in enumerate(righe) if re.fullmatch(r"\d{2}/\d{2}/\d{4}", r)), None)
    if pos is None:
        return {"titolo": "", "pubblicata": None, "partite": []}
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", righe[pos])
    pub = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    titolo = next((r for r in reversed(righe[:pos]) if "DESIGNAZIONI" in r.upper() and "GIORNATA" in r.upper()), "")
    righe = righe[pos + 1:]
    partite = []
    prima = None   # (data, ora) della partita precedente: serve quando manca il giorno
    i = 0
    while i < len(righe) - 2:
        r = righe[i]
        m = re.match(r"^(.+?)\s+[–-]\s+(.+?)$", r)
        # dopo le squadre c'è giorno e ora («Sabato 31/10 h. 15.00»), ma a volte solo l'ora: nella 10ª giornata 2026/27
        # le cinque partite di domenica erano «h. 12.30», «h. 15.00»... senza giorno, e si perdevano tutte
        if not m or not (re.match(GIORNI, righe[i + 1], re.I) or re.match(r"h\.\s*\d", righe[i + 1])):
            i += 1
            continue
        # riga con giorno e ora, a volte spezzata su due righe
        j = i + 1
        blocco = righe[j]
        if not re.search(r"h\.", blocco) and j + 1 < len(righe):
            j += 1
            blocco += " " + righe[j]
        g = re.search(r"(\d{1,2})/(\d{1,2})", blocco)
        o = re.search(r"h\.\s*(\d{1,2})[.:](\d{2})", blocco)
        ora = "{}:{}".format(o.group(1).zfill(2), o.group(2)) if o else ""
        k = j + 1
        while k < len(righe) and righe[k].lower().startswith("(foto"):
            k += 1
        arbitro = righe[k] if k < len(righe) else ""
        if g:
            giorno, mese = int(g.group(1)), int(g.group(2))
            data = date(pub.year + (1 if mese < pub.month - 3 else 0), mese, giorno)
        elif prima:   # senza giorno: lo stesso della partita prima, o il giorno dopo se l'ora è più presto
            data = prima[0] + timedelta(days=1 if ora and prima[1] and ora < prima[1] else 0)
        else:
            data = pub
        if arbitro:
            partite.append({
                "casa": squadra(m.group(1)), "trasf": squadra(m.group(2)),
                "data": data.isoformat(), "ora": ora,
                "arbitro": re.sub(r"\s*\(.*$", "", arbitro).strip(),   # toglie la sezione tra parentesi: "MASSA (Imperia)" -> "MASSA"
            })
            prima = (data, ora)
        i = k + 1
    return {"titolo": titolo, "pubblicata": pub.isoformat(), "partite": partite}


def aggiorna():
    """Scarica le designazioni di Serie A presenti sul sito e le aggiunge all'archivio."""
    archivio = leggi_json(ARCHIVIO) if ARCHIVIO.exists() else {}
    try:
        elenco = _pagina(BASE + "/designazioni/can/")
        link = re.findall(r'<a [^>]*href="(/?dettaglio\.asp\?ID=(\d+))"[^>]*>(.*?)</a>', elenco, re.S)
        for _, id_, testo in link:
            testo = re.sub(r"<[^>]+>", "", testo).upper()
            if "SERIE A" not in testo or "DESIGNAZIONI" not in testo:
                continue
            pagina = _pagina(BASE + "/dettaglio.asp?ID=" + id_)
            dati = _interpreta(pagina)
            if dati["partite"]:
                archivio[id_] = dati
    except Exception as e:
        print("  ! AIA: {}".format(e))
    scrivi_json(ARCHIVIO, archivio)
    return archivio


def designazioni(archivio):
    """Dizionario {(stagione, casa, trasf): arbitro_aia} con l'ultima designazione nota."""
    out = {}
    for id_ in sorted(archivio, key=int):
        for p in archivio[id_]["partite"]:
            d = date.fromisoformat(p["data"])
            out[(stagione_di(d), p["casa"], p["trasf"])] = p["arbitro"]
    return out
