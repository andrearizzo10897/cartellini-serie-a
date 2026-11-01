"""Designazioni AIA: lettura della pagina della giornata (nessuna rete, pagina vera salvata in fixtures)."""
import unittest
from pathlib import Path

from fonti import aia

PAGINA_10A = (Path(__file__).parent / "fixtures" / "aia_designazioni_10a_giornata.html").read_text(encoding="utf-8")


def pagina(*partite):
    """Pagina minima come quella dell'AIA: titolo, data di pubblicazione, poi squadre / giorno e ora / arbitro."""
    righe = ["SERIE A ENILIVE - DESIGNAZIONI 10a GIORNATA", "30/10/2026"]
    for squadre, quando, arbitro in partite:
        righe += [squadre, quando, arbitro, "ASSISTENTE UNO – ASSISTENTE DUE", "IV: QUARTO", "VAR: VIDEO"]
    return "<html><body>" + "".join("<p>%s</p>" % r for r in righe) + "</body></html>"


class DesignazioniAia(unittest.TestCase):
    def test_10a_giornata_con_la_domenica_senza_giorno(self):
        # 1/11/2026: per le cinque partite di domenica l'AIA ha scritto solo l'ora («h. 12.30») e si perdevano
        d = aia._interpreta(PAGINA_10A)
        self.assertEqual(len(d["partite"]), 10)
        domenica = [(p["casa"], p["trasf"], p["ora"], p["arbitro"]) for p in d["partite"] if p["data"] == "2026-11-01"]
        self.assertEqual(domenica, [("como", "venezia", "12:30", "FERRIERI CAPUTI"), ("frosinone", "torino", "15:00", "MUCERA"),
                                    ("lazio", "cagliari", "15:00", "COLOMBO"), ("lecce", "genoa", "18:00", "MARCHETTI"),
                                    ("juventus", "napoli", "20:45", "SOZZA")])
        self.assertEqual([p["data"] for p in d["partite"]].count("2026-10-31"), 3)
        self.assertEqual([p["data"] for p in d["partite"]].count("2026-11-02"), 2)
        self.assertIn(("milan", "inter", "GUIDA"), [(p["casa"], p["trasf"], p["arbitro"]) for p in d["partite"]])   # «GUIDA (foto)»

    def test_giorno_scritto(self):
        d = aia._interpreta(pagina(("ROMA – GENOA", "Sabato 31/10 h. 15.00", "MASSA (Imperia)")))
        self.assertEqual([(p["casa"], p["trasf"], p["data"], p["ora"], p["arbitro"]) for p in d["partite"]],
                         [("roma", "genoa", "2026-10-31", "15:00", "MASSA")])

    def test_senza_giorno_stessa_ora_stesso_giorno(self):
        d = aia._interpreta(pagina(("ROMA – GENOA", "Sabato 31/10 h. 20.45", "MASSA"),
                                   ("LAZIO – INTER", "h. 15.00", "DOVERI"), ("MILAN – TORINO", "h. 15.00", "SOZZA"),
                                   ("LECCE – COMO", "Lunedì 02/11 h. 20.45", "GUIDA")))
        self.assertEqual([p["data"] for p in d["partite"]], ["2026-10-31", "2026-11-01", "2026-11-01", "2026-11-02"])

    def test_prima_partita_senza_giorno(self):
        d = aia._interpreta(pagina(("ROMA – GENOA", "h. 12.30", "MASSA")))
        self.assertEqual([(p["casa"], p["data"]) for p in d["partite"]], [("roma", "2026-10-30")])   # giorno di pubblicazione

    def test_designazioni_per_partita(self):
        archivio = {"28806": aia._interpreta(PAGINA_10A)}
        self.assertEqual(aia.designazioni(archivio)[(2026, "juventus", "napoli")], "SOZZA")


if __name__ == "__main__":
    unittest.main()
