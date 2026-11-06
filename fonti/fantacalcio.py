"""Fantacalcio.it: terza fonte delle formazioni ufficiali, indipendente da Sky e SosFanta.

Articolo "<casa>-<trasferta>-le-formazioni-ufficiali-<numero>", elencato nel feed e nella pagina delle notizie, con un blocco
"VENEZIA (3-5-2) : Stankovic; Halhal, ...; Yeboah, Adams. Allenatore: ...". Ricerca e lettura sono in fonti/articoli.py.
"""
from fonti import articoli

DOMINIO = "www.fantacalcio.it"
ELENCHI = ["https://www.fantacalcio.it/feed", "https://www.fantacalcio.it/news", "https://www.fantacalcio.it/"]


def ufficiali(ev, ultima_formazione, tradotti=None):
    """Formazioni ufficiali di Fantacalcio.it nel formato di espn.formazioni(), o None."""
    return articoli.leggi(ev, ultima_formazione, tradotti, articoli.trova(ev, DOMINIO, ELENCHI, None, "Fantacalcio"), "Fantacalcio")
