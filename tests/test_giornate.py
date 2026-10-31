"""Numero della giornata ricavato dal calendario e cartellini giornata per giornata (pagina «Giocatori»): nessuna rete."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import calcoli
import pagina
from fonti import espn_dettaglio

# calendari veri: 2023/24 e 2024/25 con la giornata ufficiale (API-Football), 2025/26 senza (ESPN)
CALENDARI = json.loads((Path(__file__).parent / "fixtures" / "calendari_serie_a.json").read_text(encoding="utf-8"))


def calendario(stagione):
    return [{"id": i, "inizio": datetime.fromisoformat(r[0]), "casa": r[1], "trasf": r[2], "vera": r[3] if len(r) > 3 else None}
            for i, r in enumerate(CALENDARI[stagione])]


def p(id_, giorno, casa, trasf):
    return {"id": id_, "inizio": datetime(2026, 9, 1, 15) + timedelta(days=giorno), "casa": casa, "trasf": trasf}


class NumeroGiornata(unittest.TestCase):
    def test_stagioni_intere_con_rinvii_e_recuperi(self):
        # 2023/24: quattro partite della 21ª rinviate per la Supercoppa, Fiorentina-Atalanta della 29ª giocata a giugno,
        # Udinese-Roma sospesa e finita dieci giorni dopo. 2024/25: Bologna-Milan rinviata a febbraio, Fiorentina-Inter
        # (sospesa) rigiocata il giovedì prima di Inter-Fiorentina, tre partite della 19ª dopo la Supercoppa, la 33ª dopo Pasqua.
        for stagione in ("2023", "2024"):
            ps = calendario(stagione)
            numeri = calcoli.numera_giornate(ps)
            self.assertEqual([(x["casa"], x["trasf"], x["vera"], numeri[x["id"]]) for x in ps if numeri[x["id"]] != x["vera"]],
                             [], stagione)

    def test_giorno_per_giorno_come_in_produzione(self):
        """Ogni giorno conta solo quello che si sa: le partite finite e quelle degli 8 giorni dopo (come in aggiorna.py)."""
        ps = calendario("2024")
        primo, ultimo = ps[0]["inizio"].date(), ps[-1]["inizio"].date()
        for k in range(0, (ultimo - primo).days + 2):
            oggi = primo + timedelta(k)
            note = [x for x in ps if x["inizio"].date() < oggi + timedelta(8)]
            numeri = calcoli.numera_giornate(note)
            sbagliate = [(x["casa"], x["trasf"]) for x in note if x["inizio"].date() < oggi and numeri[x["id"]] != x["vera"]]
            self.assertEqual(sbagliate, [], oggi)

    def test_2025_26_ogni_giornata_ha_dieci_partite_con_venti_squadre(self):
        # senza giornata ufficiale: le quattro partite della 16ª rinviate per la Supercoppa di dicembre e giocate a metà
        # gennaio, Milan-Como spostata al 18 febbraio per le Olimpiadi a San Siro
        ps = calendario("2025")
        numeri = calcoli.numera_giornate(ps)
        self.assertEqual(sorted(set(numeri.values())), list(range(1, 39)))
        for g in range(1, 39):
            squadre = [s for x in ps if numeri[x["id"]] == g for s in (x["casa"], x["trasf"])]
            self.assertEqual((len(squadre), len(set(squadre))), (20, 20), g)

    def test_recupero_che_si_incastra_solo_spostando_un_altra_partita(self):
        # 4 squadre: A-B della 1ª giocata dopo la 3ª. All'inizio A-B occupa il posto di A nella 3ª e A-D resta fuori.
        ps = [p(1, 0, "c", "d"), p(2, 7, "a", "c"), p(3, 7, "b", "d"), p(4, 14, "a", "d"), p(5, 14, "b", "c"), p(6, 17, "a", "b")]
        self.assertEqual(calcoli.numera_giornate(ps), {1: 1, 6: 1, 2: 2, 3: 2, 4: 3, 5: 3})

    def test_calendario_vuoto(self):
        self.assertEqual(calcoli.numera_giornate([]), {})


def giocatore(id_, nome, titolare=True, entrato=False, gialli=0, rossi=0, ruolo="CM"):
    return {"id": id_, "nome": nome, "ruolo_espn": ruolo if titolare else "SUB", "titolare": titolare, "entrato": entrato,
            "uscito": False, "presenze": int(titolare or entrato), "gialli": gialli, "rossi": rossi, "falli": 0, "falli_sub": 0}


def evento(tipo, minuto, chi, testo=None):
    e = {"tipo": tipo, "minuto": minuto, "squadra": "", "persone": [chi]}
    if testo:
        e["testo"] = testo
    return e


class CartelliniGiornata(unittest.TestCase):
    """Due giornate fra quattro squadre: nella 2ª Inter-Roma non è ancora giocata e ESPN manda la Lazio senza giocatori."""

    def setUp(self):
        ev = lambda id_, giorno, casa, trasf: dict(p(id_, giorno, casa, trasf), id_casa="1" + id_, id_trasf="2" + id_)
        roma = [giocatore("r1", "Mario Rossi", gialli=1), giocatore("r2", "Luca Bianchi", rossi=1, ruolo="CD"),
                giocatore("r3", "Paolo Verdi", titolare=False),                                 # in panchina, mai entrato
                giocatore("r4", "Kevin De Bruyne", titolare=False, entrato=True, rossi=1),
                giocatore("r5", "Gino Sardi", gialli=1, rossi=1)]                            # giallo e poi rosso diretto
        genoa = [giocatore("g1", "Ugo Neri"), giocatore("g2", "Pedro", titolare=False, gialli=1)]   # giallo dalla panchina
        genoa2 = [giocatore("g1", "Ugo Neri", titolare=False), giocatore("g2", "Pedro")]
        self.finite = [
            (ev("10", 0, "roma", "genoa"), {"home": {"squadra": "roma", "giocatori": roma},
                                            "away": {"squadra": "genoa", "giocatori": genoa}}),
            (ev("11", 0, "lazio", "inter"), {"home": {"squadra": "lazio", "giocatori": [giocatore("l1", "Ciro Blu")]},
                                             "away": {"squadra": "inter", "giocatori": [giocatore("i1", "Ivo Gialli")]}}),
            (ev("12", 7, "genoa", "lazio"), {"home": {"squadra": "genoa", "giocatori": genoa2},
                                             "away": {"squadra": "lazio", "giocatori": []}}),
        ]
        self.prossime = [ev("13", 8, "inter", "roma")]
        self.dettagli = {"10": {"eventi": [evento("yellow-card", 33.2, "r1"), evento("yellow-card", 20.0, "r2"),
                                           evento("red-card", 70.5, "r2"), evento("red-card", 90.0, "r4", "90'+4'"),
                                           evento("yellow-card", 49.3, "r5", "50'"), evento("red-card", 80.1, "r5", "81'")]}}
        self.dati = calcoli.cartellini_giornate(self.finite, self.prossime, self.dettagli)
        self.per_nome = {x["nome"]: x for x in self.dati["giocatori"]}

    def test_stati_della_giornata(self):
        stati = {n: x["stati"][:3] for n, x in self.per_nome.items()}
        self.assertEqual(stati, {
            "Mario Rossi": "g--", "Luca Bianchi": "d--", "Kevin De Bruyne": "r--",   # la Roma non ha ancora giocato la 2ª
            "Gino Sardi": "r--",
            "Ugo Neri": "o.-", "Pedro": "go-",                                       # in panchina nella 2ª: non ha giocato
            "Ciro Blu": "o--", "Ivo Gialli": "o--"})                                 # Lazio senza giocatori nella 2ª
        self.assertNotIn("Paolo Verdi", self.per_nome)                               # mai in campo, nessun cartellino
        self.assertEqual(len(self.per_nome["Mario Rossi"]["stati"]), 38)
        self.assertEqual(self.dati["ultima"], 2)

    def test_cartellini_con_minuto_e_conteggi(self):
        self.assertEqual(self.per_nome["Mario Rossi"]["cartellini"], [[1, "roma", "genoa", "34'", "g"]])
        self.assertEqual(self.per_nome["Luca Bianchi"]["cartellini"], [[1, "roma", "genoa", "71'", "d"]])
        self.assertEqual(self.per_nome["Kevin De Bruyne"]["cartellini"], [[1, "roma", "genoa", "90'+4'", "r"]])   # recupero
        self.assertEqual(self.per_nome["Gino Sardi"]["cartellini"], [[1, "roma", "genoa", "50'", "g"], [1, "roma", "genoa", "81'", "r"]])
        self.assertEqual(self.per_nome["Pedro"]["cartellini"], [[1, "roma", "genoa", None, "g"]])   # senza evento: niente minuto
        self.assertEqual([(x["gialli"], x["rossi"], x["presenze"]) for x in (self.per_nome["Luca Bianchi"], self.per_nome["Pedro"])],
                         [(0, 1, 1), (1, 0, 1)])
        self.assertEqual((self.per_nome["Luca Bianchi"]["ruolo"], self.per_nome["Kevin De Bruyne"]["ruolo"]), ("D", ""))
        self.assertEqual(self.dati["totali"], {"roma": [2, 3], "genoa": [1, 0], "lazio": [0, 0], "inter": [0, 0]})

    def test_partita_rifatta_con_un_altro_id_tiene_i_cartellini(self):
        ev, forma = self.finite[0]
        rifatta = (dict(ev, id="99", inizio=ev["inizio"] + timedelta(days=3)),
                   {"home": {"squadra": "roma", "giocatori": [giocatore("r9", "Ultimo Arrivato", gialli=1)]},
                    "away": {"squadra": "genoa", "giocatori": [giocatore("g1", "Ugo Neri")]}})
        dati = calcoli.cartellini_giornate(self.finite + [rifatta], self.prossime, self.dettagli)
        self.assertEqual(next(x["stati"][:2] for x in dati["giocatori"] if x["nome"] == "Ultimo Arrivato"), "g-")

    def test_pagina_dati_compatti(self):
        html = pagina.sezione_giocatori(self.dati)
        dati = json.loads(html.split('<script type="application/json" id="gg-dati">')[1].split("</script>")[0])
        squadre = [s[0] for s in dati["s"]]
        self.assertEqual(squadre, ["Genoa", "Inter", "Lazio", "Roma"])
        riga = next(x for x in dati["g"] if x[0] == "Luca Bianchi")
        self.assertEqual(riga[1:4], ["L. Bianchi", "D", squadre.index("Roma")])
        self.assertEqual(riga[8], [[1, squadre.index("Roma"), squadre.index("Genoa"), "71'", "d"]])
        self.assertEqual(dati["s"][squadre.index("Roma")], ["Roma", "", 2, 3])     # gialli e rossi della squadra
        self.assertIn('data-tab', pagina.JS)                                          # la griglia la disegna il JavaScript

    def test_un_nome_non_chiude_lo_script(self):
        self.dati["giocatori"][0]["nome"] = "X</script><b>"
        self.dati["giocatori"][1]["nome"] = "<!--<script>"
        html = pagina.sezione_giocatori(self.dati)
        dati = html.split('id="gg-dati">')[1].split("</script>")[0]
        self.assertNotIn("<", dati)                                                  # né chiusure né commenti HTML
        self.assertEqual(html.count("</script>"), 1)
        self.assertIn("X</script><b>", [x[0] for x in json.loads(dati)["g"]])

    def test_nomi_corti_per_il_telefono(self):
        self.assertEqual([pagina.breve(n) for n in ("Lautaro Martínez", "Pedro", "Kevin De Bruyne", "David de Gea")],
                         ["L. Martínez", "Pedro", "K. De Bruyne", "D. de Gea"])

    def test_nessuna_partita_giocata(self):
        self.assertIn("Nessuna partita giocata", pagina.sezione_giocatori(calcoli.cartellini_giornate([], [], {})))



class MinutoDelRecupero(unittest.TestCase):
    """ESPN ferma il tempo di gioco a 90:00 nel recupero: il minuto scritto («90'+4'») si salva a parte."""

    PARTITA = {"header": {"competitions": [{"date": "2026-10-25T19:45Z", "status": {"type": {"state": "post"}}}]},
               "rosters": [], "keyEvents": [{"type": {"type": "red-card"}, "clock": {"value": 5400, "displayValue": "90'+4'"},
                                             "team": {"displayName": "Lecce"}, "participants": [{"athlete": {"id": 7}}]}]}

    def test_la_voce_vecchia_si_rifa_dal_file_completo_senza_rete(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cartella = Path(tmp.name)
        (cartella / "espn").mkdir()
        (cartella / "espn" / "partita_1.json").write_text(json.dumps(self.PARTITA), encoding="utf-8")
        vecchia = {"data": "2026-10-25", "formazioni": {}, "arbitro": None, "finita": True,
                   "eventi": [{"tipo": "red-card", "minuto": 90.0, "squadra": "lecce", "persone": ["7"]}]}
        with mock.patch.object(espn_dettaglio, "CACHE", cartella), \
                mock.patch.object(espn_dettaglio, "ARCHIVIO", cartella / "espn_dettaglio.json"), \
                mock.patch.object(espn_dettaglio, "_archivio", {"_versione": espn_dettaglio.VERSIONE, "1": vecchia}), \
                mock.patch.object(espn_dettaglio, "scarica_json", side_effect=AssertionError("niente rete")):
            voce = espn_dettaglio.carica(["1"])["1"]
            self.assertEqual(voce["eventi"][0]["testo"], "90'+4'")
            self.assertIs(espn_dettaglio.carica(["1"])["1"], voce)                 # ora è completa: non si rifà più
        self.assertEqual(calcoli._minuto(voce["eventi"][0]), "90'+4'")
        self.assertEqual(calcoli._minuto({"minuto": 66.1}), "67'")                   # voce vecchia: dal tempo di gioco


if __name__ == "__main__":
    unittest.main()
