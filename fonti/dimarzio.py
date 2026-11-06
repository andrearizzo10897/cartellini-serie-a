"""Gianluca Di Marzio: fonte delle formazioni ufficiali sulla pagina online, al posto di Fantacalcio.

Articolo "<casa>-<trasferta>-formazioni-ufficiali-...", elencato nel feed e nelle notizie, con un blocco
"VENEZIA (3-5-2): Stankovic; Halhal, ...; Yeboah, Adams. All . Nicola". Ricerca e lettura sono in fonti/articoli.py.
"""
from fonti import articoli

DOMINIO = "www.gianlucadimarzio.com"
ELENCHI = ["https://www.gianlucadimarzio.com/rss", "https://www.gianlucadimarzio.com/news-calcio", "https://www.gianlucadimarzio.com/"]


def ufficiali(ev, ultima_formazione, tradotti=None):
    """Formazioni ufficiali di gianlucadimarzio.com nel formato di espn.formazioni(), o None."""
    return articoli.leggi(ev, ultima_formazione, tradotti, articoli.trova(ev, DOMINIO, ELENCHI, None, "Di Marzio"), "Di Marzio")
