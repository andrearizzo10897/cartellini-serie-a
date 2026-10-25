"""SosFanta: formazioni ufficiali, di riserva quando Sky non le ha (o non si riescono a leggere).

L'articolo "formazioni ufficiali <casa> <trasferta> ..." contiene un blocco di testo così:
"LE FORMAZIONI UFFICIALI VENEZIA - Stankovic; Moreno, Juan Jesus, ...; Yeboah, Adams. NAPOLI - Meret; ... Lucca."
Solo cognomi e nessun modulo. Gli articoli si trovano dai link della home e della pagina delle probabili formazioni.
Se non c'è l'articolo o il formato cambia, restituisce None e la pagina usa le altre fonti.
"""
import html
import re

from fonti import sky
from utils import scarica

ELENCHI = ["https://www.sosfanta.com/", "https://www.sosfanta.com/probabili-formazioni/",
           "https://www.sosfanta.com/news-formazioni/"]
UA = sky.UA
ALIAS = {"verona": ["hellas-verona", "verona"]}


def _slug(nome):
    return ALIAS.get(nome, [sky._slug(nome)])


def _link(ev):
    """Indirizzo dell'articolo "formazioni ufficiali" della partita, o None."""
    cercati = {c + "-" + t for c in _slug(ev["casa"]) for t in _slug(ev["trasf"])}
    for url in ELENCHI:
        try:
            testo = scarica(url, headers=UA, pausa=0.1, tentativi=1).text
        except Exception:  # noqa: BLE001 - rete: provo l'elenco dopo
            continue
        for m in re.finditer(r"https://www\.sosfanta\.com/news/formazioni-ufficiali-([a-z0-9-]+)/", testo):
            if any(m.group(1).startswith(c + "-") or m.group(1) == c for c in cercati):
                return m.group(0)
    return None


def _estrai(testo, ev):
    """[(None, [11 nomi]), (None, [11 nomi])] nell'ordine casa, trasferta, o None."""
    i = testo.find("LE FORMAZIONI UFFICIALI")   # in maiuscolo: il titolo dell'articolo lo ha in minuscolo
    if i < 0:
        return None
    blocco = testo[i + len("LE FORMAZIONI UFFICIALI"):i + 2500]
    fine = min([blocco.find(x) for x in ("🆘", "CLICCA", "©", "Commenta") if x in blocco] or [len(blocco)])
    blocco = blocco[:fine]
    etichette = list(re.finditer(r"([A-ZÀ-Ü][A-ZÀ-Ü' .]{2,}?) - ", blocco))[:2]
    if len(etichette) < 2:
        return None
    parti = [blocco[etichette[0].end():etichette[1].start()], blocco[etichette[1].end():]]
    out = []
    for elenco in parti:
        nomi = [n.strip(" .") for n in re.split(r"[;,]", elenco.strip().rstrip(".")) if n.strip(" .")]
        if len(nomi) != 11:
            return None
        out.append((None, nomi))
    return out


def ufficiali(ev, ultima_formazione, tradotti=None):
    """Formazioni ufficiali di SosFanta nel formato di espn.formazioni(), o None.

    tradotti: nomi completi dei soprannomi, presi dalla pagina "formazioni" di Sky (sky.alias)."""
    url = _link(ev)
    if not url:
        return None
    try:
        r = scarica(url, headers=UA, pausa=0.1, tentativi=1)
    except Exception:  # noqa: BLE001
        return None
    pulito = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", r.text)
    testo = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", pulito)))
    return sky.da_nomi(ev, ultima_formazione, _estrai(testo, ev), tradotti)
