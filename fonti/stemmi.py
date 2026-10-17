"""Stemmi delle squadre (dalle immagini ESPN), incorporati nella pagina come PNG da 96 px.

Si scaricano una volta sola (dati/cache/stemmi) e finiscono nel CSS una sola volta per squadra, anche se lo stemma
compare in più punti. Se ESPN non risponde la pagina si genera lo stesso, senza stemma.
"""
import base64

from config import CACHE
from utils import scarica

URL = "https://a.espncdn.com/combiner/i"
LATO = 96   # pixel: nitido anche sugli schermi ad alta risoluzione, senza appesantire troppo la pagina


def _file(id_squadra):
    return CACHE / "stemmi" / "{}_{}.png".format(id_squadra, LATO)


def carica(id_squadra):
    """Data-URI del PNG dello stemma, o None se non si riesce a scaricarlo."""
    percorso = _file(id_squadra)
    if not percorso.exists():
        try:
            r = scarica(URL, params={"img": "/i/teamlogos/soccer/500/{}.png".format(id_squadra), "w": LATO, "h": LATO},
                        pausa=0.1, tentativi=2)
        except Exception:  # noqa: BLE001 - rete: la pagina funziona anche senza stemmi
            return None
        if not r.content.startswith(b"\x89PNG"):
            return None
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_bytes(r.content)
    return "data:image/png;base64," + base64.b64encode(percorso.read_bytes()).decode()


def css(ids):
    """(regole CSS .stNNN con lo stemma, insieme degli id con stemma disponibile)."""
    regole, ok = [], set()
    for i in sorted({str(x) for x in ids if x}):
        uri = carica(i)
        if uri:
            regole.append(".st{}{{background-image:url({})}}".format(i, uri))
            ok.add(i)
    return "\n".join(regole), ok
