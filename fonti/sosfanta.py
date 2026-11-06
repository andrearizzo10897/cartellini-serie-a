"""SosFanta: formazioni ufficiali, di riserva quando Sky non le ha (o non si riescono a leggere).

L'articolo "formazioni ufficiali <casa> <trasferta> ..." contiene un blocco di testo così:
"LE FORMAZIONI UFFICIALI VENEZIA - Stankovic; Moreno, Juan Jesus, ...; Yeboah, Adams. NAPOLI - Meret; ... Lucca."
Solo cognomi e nessun modulo. Gli articoli si trovano per nome (vedi _articoli) dalla home, dalle pagine delle formazioni e dalla ricerca del sito.
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


def _articoli(ev):
    """Indirizzi degli articoli "formazioni ufficiali" della partita, cercati per nome e non per percorso: SosFanta cambia spesso gli indirizzi.

    Vale qualunque link del sito il cui ultimo pezzo contiene "ufficial" e le due squadre nell'ordine casa, trasferta."""
    coppie = [(c, t) for c in _slug(ev["casa"]) for t in _slug(ev["trasf"])]
    ricerca = ["https://www.sosfanta.com/?s=formazioni+ufficiali+{}+{}".format(c, t) for c, t in coppie]
    trovati = []
    for url in ELENCHI + ricerca:
        try:
            testo = scarica(url, headers=UA, pausa=0.1, tentativi=1).text
        except Exception:  # noqa: BLE001 - rete: provo l'elenco dopo
            sky.problemi.add("SosFanta non risponde")
            continue
        for link in re.findall(r"https://www\.sosfanta\.com/[a-z0-9/_-]*ufficial[a-z0-9/_-]*", testo):
            nome = link.rstrip("/").rsplit("/", 1)[-1]
            if link not in trovati and "ufficial" in nome and any(
                    re.search(r"(^|-){}-(.*-)?{}(-|$)".format(c, t), nome) for c, t in coppie):
                trovati.append(link)
        if trovati:
            break
    return trovati


def _link(ev):
    """Primo articolo "formazioni ufficiali" della partita, o None."""
    return next(iter(_articoli(ev)), None)


MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _del_giorno(raw, testo, inizio):
    """L'articolo è di oggi? Con gli indirizzi non fissi potrebbe essere quello di una stagione passata, con la stessa partita."""
    return "{} {}".format(inizio.day, MESI[inizio.month - 1]) in testo.lower() or inizio.strftime("%Y-%m-%d") in raw


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
    for url in _articoli(ev):
        try:
            r = scarica(url, headers=UA, pausa=0.1, tentativi=1)
        except Exception:  # noqa: BLE001
            sky.problemi.add("SosFanta non risponde")
            continue
        pulito = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", r.text)
        testo = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", pulito)))
        if ev.get("inizio") and not _del_giorno(r.text, testo, ev["inizio"]):
            continue
        estratte = _estrai(testo, ev)
        if estratte is None:
            sky.problemi.add("articolo di SosFanta illeggibile (formato cambiato?)")
            continue
        forma = sky.da_nomi(ev, ultima_formazione, estratte, tradotti)
        if forma:
            return forma
    return None
