"""SosFanta: formazioni ufficiali, di riserva quando Sky non le ha (o non si riescono a leggere).

L'articolo "formazioni ufficiali <casa> <trasferta> ..." contiene un blocco di testo così:
"LE FORMAZIONI UFFICIALI VENEZIA - Stankovic; Moreno, Juan Jesus, ...; Yeboah, Adams. NAPOLI - Meret; ... Lucca."
Solo cognomi e nessun modulo. Ricerca e lettura sono in fonti/articoli.py: SosFanta cambia spesso indirizzi e titoli.
"""
from fonti import articoli

DOMINIO = "www.sosfanta.com"
ELENCHI = ["https://www.sosfanta.com/", "https://www.sosfanta.com/probabili-formazioni/",
           "https://www.sosfanta.com/news-formazioni/"]
RICERCA = "https://www.sosfanta.com/?s=formazioni+ufficiali+{c}+{t}"


def _articoli(ev):
    return articoli.trova(ev, DOMINIO, ELENCHI, RICERCA, "SosFanta")


def _link(ev):
    """Primo articolo "formazioni ufficiali" della partita, o None."""
    return next(iter(_articoli(ev)), None)


def _estrai(testo, _ev=None):
    """[(None, [11 nomi]), (None, [11 nomi])] nell'ordine casa, trasferta, o None."""
    trovati = articoli.blocchi(testo)
    return [(None, trovati[0]), (None, trovati[1])] if len(trovati) >= 2 else None


def ufficiali(ev, ultima_formazione, tradotti=None):
    """Formazioni ufficiali di SosFanta nel formato di espn.formazioni(), o None.

    tradotti: nomi completi dei soprannomi, presi dalla pagina "formazioni" di Sky (sky.alias)."""
    return articoli.leggi(ev, ultima_formazione, tradotti, _articoli(ev), "SosFanta")
