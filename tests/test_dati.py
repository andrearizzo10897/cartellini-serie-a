"""Quote DAZN Bet, cache ESPN e riepilogo delle fonti: nessuna rete (si usano dati finti e cartelle temporanee)."""
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import aggiorna
import calcoli
import pagina
import utils
from fonti import daznbet, espn


class QuoteDaznBet(unittest.TestCase):
    JS = {"avs": [
        {"dsl": {"IT": "Venezia - Napoli"}, "scs": [
            {"d": "GIOCATORE AMMONITO", "dia": "Rrahmani Amir (Napoli)", "eqs": [{"ce": 1, "q": 450}]},
            {"d": "Giocatore ammonito", "dia": "Lucca Lorenzo (Napoli)", "eqs": [{"ce": 0, "q": 300}, {"ce": 1, "q": 575}]},
            {"d": "GIOCATORE ESPULSO", "dia": "Meret Alex (Napoli)", "eqs": [{"ce": 1, "q": 3000}]},   # altro mercato
            {"d": "GIOCATORE AMMONITO", "dia": "Senza Squadra", "eqs": [{"ce": 1, "q": 500}]},          # nessuna squadra
            {"d": "GIOCATORE AMMONITO", "dia": "Quota Zero (Venezia)", "eqs": [{"ce": 1, "q": 0}]}]},   # sospesa
        {"dsl": {"IT": "Roma - Genoa"}, "scs": []},                                                       # nessuna quota
        {"dsl": {}, "scs": []}]}                                                                          # senza titolo

    def test_interpreta_solo_il_mercato_ammonito(self):
        quote = daznbet.interpreta(self.JS)
        self.assertEqual(list(quote), [("venezia", "napoli")])
        righe = quote[("venezia", "napoli")]
        self.assertEqual(len(righe), 2)
        self.assertEqual(righe[0], (["rrahmani", "amir"], "napoli", 4.5))
        self.assertEqual(righe[1][2], 5.75)

    def test_json_vuoto(self):
        self.assertEqual(daznbet.interpreta({}), {})

    def test_associa_per_nome_e_per_cognome(self):
        righe = [(["rrahmani", "amir"], "napoli", 4.5), (["lucca", "lorenzo"], "napoli", 5.75),
                 (["di", "lorenzo", "giovanni"], "napoli", 6.0), (["rrahmani", "x"], "venezia", 9.0)]
        gioc = [{"nome": "Amir Rrahmani"}, {"nome": "Lorenzo Lucca"}, {"nome": "Di Lorenzo"}, {"nome": "Scott McTominay"}]
        daznbet.associa(righe, "napoli", gioc)
        self.assertEqual([x["quota_book"] for x in gioc], [4.5, 5.75, 6.0, None])

    def test_associa_senza_quote(self):
        gioc = [{"nome": "Amir Rrahmani"}]
        daznbet.associa(None, "napoli", gioc)
        self.assertIsNone(gioc[0]["quota_book"])


def riassunto(stato, gialli=0, titolari=True):
    """Dettaglio di una partita nel formato di ESPN (solo i campi che il programma legge)."""
    def squadra(lato, nome, base):
        return {"homeAway": lato, "team": {"displayName": nome}, "roster": [
            {"athlete": {"id": base + i, "fullName": "Giocatore {}".format(base + i)}, "starter": titolari,
             "subbedIn": False, "subbedOut": False,
             "stats": [{"name": "yellowCards", "value": gialli if i == 0 else 0}]} for i in range(11)]}
    return {"header": {"competitions": [{"status": {"type": {"state": stato}}}]},
            "rosters": [squadra("home", "Roma", 100), squadra("away", "Genoa", 200)]}


class Risposta:
    def __init__(self, js):
        self.js = js

    def json(self):
        return self.js


class CacheEspn(unittest.TestCase):
    """Una partita finita resta in cache per sempre, ma solo se il file è stato salvato a partita finita."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        (Path(self.tmp.name) / "espn").mkdir()
        p = mock.patch.object(espn, "CACHE", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)

    def salva(self, js):
        import json
        (Path(self.tmp.name) / "espn" / "partita_1.json").write_text(json.dumps(js), encoding="utf-8")

    def gialli(self, forma):
        return sum(x["gialli"] for lato in forma.values() for x in lato["giocatori"])

    def test_file_salvato_durante_la_partita_si_riscarica(self):
        self.salva(riassunto("in", gialli=1))
        with mock.patch.object(espn, "scarica_json", return_value=riassunto("post", gialli=3)) as rete:
            forma = espn.formazioni("1", "post")
        self.assertEqual(rete.call_count, 1)
        self.assertEqual(self.gialli(forma), 6)   # 3 gialli per squadra: il file nuovo ha sostituito il vecchio
        with mock.patch.object(espn, "scarica_json") as rete:
            espn.formazioni("1", "post")          # ora è finito: non si scarica più
        self.assertEqual(rete.call_count, 0)

    def test_file_salvato_prima_del_fischio_si_riscarica(self):
        self.salva(riassunto("pre"))
        with mock.patch.object(espn, "scarica_json", return_value=riassunto("post", gialli=2)) as rete:
            forma = espn.formazioni("1", "post")
        self.assertEqual(rete.call_count, 1)
        self.assertEqual(self.gialli(forma), 4)

    def test_file_finito_non_usa_la_rete(self):
        self.salva(riassunto("post", gialli=2))
        with mock.patch.object(espn, "scarica_json") as rete:
            forma = espn.formazioni("1", "post")
        self.assertEqual(rete.call_count, 0)
        self.assertEqual(self.gialli(forma), 4)

    def test_rete_assente_con_file_vecchio_usa_il_vecchio(self):
        self.salva(riassunto("in", gialli=1))
        with mock.patch.object(espn, "scarica_json", side_effect=OSError("rete")):
            forma = espn.formazioni("1", "post")
        self.assertEqual(self.gialli(forma), 2)

    def test_rete_assente_senza_file(self):
        with mock.patch.object(espn, "scarica_json", side_effect=OSError("rete")):
            self.assertEqual(espn.formazioni("1", "post"), {})

    def test_partita_non_finita_resta_in_cache_per_poco(self):
        self.salva(riassunto("pre"))
        with mock.patch.object(espn, "scarica_json") as rete:   # file appena salvato: ancora valido
            espn.formazioni("1", "pre")
        self.assertEqual(rete.call_count, 0)

    def test_finita(self):
        self.assertTrue(espn.finita(riassunto("post")))
        self.assertFalse(espn.finita(riassunto("in")))
        self.assertFalse(espn.finita({}))

    def calendario(self, stato="pre"):
        squadra = lambda lato, nome, id_: {"homeAway": lato, "team": {"displayName": nome, "id": id_}, "score": "0"}
        return {"events": [{"id": "9", "date": "2026-10-31T14:00Z", "status": {"type": {"state": stato}},
                            "competitions": [{"competitors": [squadra("home", "Roma", "1"), squadra("away", "Genoa", "2")]}]}]}

    def salva_calendario(self, js, ore_fa):
        import json
        import os
        import time
        percorso = Path(self.tmp.name) / "espn" / "calendario_20261031.json"
        percorso.write_text(json.dumps(js), encoding="utf-8")
        quando = time.time() - ore_fa * 3600
        os.utime(percorso, (quando, quando))

    def test_calendario_senza_risposta_usa_la_copia_salvata(self):
        # 31/10/2026: ESPN ha risposto 200 con la pagina vuota e l'aggiornamento sul PC si è fermato
        self.salva_calendario(self.calendario(), ore_fa=48)
        with mock.patch.object(espn, "scarica_json", side_effect=ValueError("Expecting value: line 1 column 1 (char 0)")):
            partite = espn.partite_del_giorno(date(2026, 10, 31))
        self.assertEqual([(p["casa"], p["trasf"], p["stato"]) for p in partite], [("roma", "genoa", "pre")])

    def test_calendario_senza_risposta_e_senza_copia_si_ferma(self):
        with mock.patch.object(espn, "scarica_json", side_effect=ValueError("pagina vuota")):
            with self.assertRaises(ValueError):
                espn.partite_del_giorno(date(2026, 10, 31))

    def test_calendario_nuovo_sostituisce_la_copia(self):
        self.salva_calendario(self.calendario(), ore_fa=48)
        with mock.patch.object(espn, "scarica_json", return_value=self.calendario("post")) as rete:
            self.assertEqual(espn.partite_del_giorno(date(2026, 10, 31))[0]["stato"], "post")
        self.assertEqual(rete.call_count, 1)
        with mock.patch.object(espn, "scarica_json") as rete:      # ora è tutta finita: resta in cache per sempre
            espn.partite_del_giorno(date(2026, 10, 31))
        self.assertEqual(rete.call_count, 0)


class ScaricaJson(unittest.TestCase):
    """ESPN a volte risponde 200 con la pagina vuota: si riprova come per un errore di rete."""

    def vuota(self):
        r = mock.Mock()
        r.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
        return r

    def test_risposta_vuota_si_riprova(self):
        with mock.patch.object(utils, "scarica", side_effect=[self.vuota(), Risposta({"events": []})]) as rete, \
                mock.patch.object(utils.time, "sleep"):
            self.assertEqual(utils.scarica_json("https://esempio"), {"events": []})
        self.assertEqual(rete.call_count, 2)

    def test_sempre_vuota_alla_fine_solleva(self):
        with mock.patch.object(utils, "scarica", side_effect=lambda *a, **k: self.vuota()) as rete, \
                mock.patch.object(utils.time, "sleep"):
            with self.assertRaises(ValueError):
                utils.scarica_json("https://esempio")
        self.assertEqual(rete.call_count, 3)


class UltimaFormazione(unittest.TestCase):
    def forma(self, nomi_titolari):
        lato = lambda sq, titolari: {"squadra": sq, "formazione": None, "giocatori": [
            {"id": "{}{}".format(sq, i), "nome": "G{}".format(i), "titolare": titolari, "entrato": False, "uscito": False,
             "presenze": 0, "gialli": 0, "falli": 0} for i in range(nomi_titolari)]}
        return lato

    def test_squadra_vuota_di_espn_non_cancella_l_ultima_formazione_buona(self):
        # ESPN a volte manda una squadra senza giocatori (Roma-Genoa del 17/10): non deve far sparire la formazione di prima
        pieno = {"home": {"squadra": "roma", "formazione": None, "giocatori": [
                    {"id": "r1", "nome": "A", "titolare": True, "entrato": False, "uscito": False, "presenze": 0,
                     "gialli": 0, "falli": 0}]}}
        vuoto = {"home": {"squadra": "roma", "formazione": None, "giocatori": []}}
        ev = lambda g: {"inizio": datetime(2026, 10, g, 15, 0)}
        _, ultima = calcoli.aggrega_espn([(ev(10), pieno), (ev(17), vuoto)])
        self.assertEqual([x["id"] for x in ultima["roma"]], ["r1"])


class TestoLivelloSerieA(unittest.TestCase):
    """La frase «Livello della Serie A» di Come funziona usa le medie vere di ogni stagione, non numeri scritti a mano."""

    def test_tutte_le_stagioni_con_quella_in_corso_parziale(self):
        per = {2023: (4.32, 380), 2024: (3.82, 380), 2025: (3.70, 380), 2026: (3.33, 78)}
        self.assertEqual(pagina.anni_gialli({"per_stagione": per}),
                         ("sono calati ogni anno", "4,3 a partita nel 2023/24, 3,8 nel 2024/25, 3,7 nel 2025/26 e 3,3 finora nel 2026/27"))

    def test_se_non_calano_ogni_anno_non_lo_dice(self):
        per = {2023: (4.3, 380), 2024: (3.5, 380), 2025: (3.7, 380)}
        self.assertEqual(pagina.anni_gialli({"per_stagione": per})[0], "sono cambiati da una stagione all'altra")

    def test_senza_dati_ripiega_sul_testo_fisso(self):
        self.assertIn("2023/24", pagina.anni_gialli({})[1])


class RiepilogoFonti(unittest.TestCase):
    def fonti(self, **kw):
        base = dict(anno=2026, ultimo_fd=datetime(2026, 10, 19).date(), oggi=datetime(2026, 10, 25).date(), aggiunte=8,
                    finite=[(None, None)] * 78, prossime=[{"quote": (0.4, 0.3, 0.3)}, {"quote": None}],
                    mancanti=[], kickest_corrente=False, n_tm=2459, quote_giocatori={("a", "b"): []}, nota_quote=None,
                    quote_ora=datetime(2026, 10, 25, 18, 49), n_uff={"ESPN": 1, "Sky": 0, "SosFanta": 0}, cercate=1,
                    partite=[{"arbitro": "X"}, {"arbitro": None}])
        base.update(kw)
        return {nome: (livello, testo) for nome, livello, testo in aggiorna.riepilogo_fonti(**base)}

    def test_testi_e_livelli(self):
        f = self.fonti()
        self.assertNotIn("football-data.co.uk", f)                       # ritardo di 6 giorni: normale, niente avviso
        self.assertIn("78 partite finite lette (8 non ancora in football-data), 2 in programma (1 con le quote 1X2)", f["ESPN"][1])
        self.assertIn("ufficiali per 1 partita su 2", f["Formazioni ufficiali"][1])
        self.assertIn("per 1 partita vicina al calcio d'inizio", f["Formazioni ufficiali"][1])
        self.assertEqual(f["DAZN Bet"][0], "ok")
        self.assertIn("quote «ammonito» per 1 partita, scaricate alle 18:49", f["DAZN Bet"][1])
        self.assertIn("designati per 1 partita su 2", f["Arbitri (AIA)"][1])

    def test_football_data_ferma_da_piu_di_due_settimane(self):
        f = self.fonti(ultimo_fd=datetime(2026, 10, 5).date())           # 20 giorni
        self.assertEqual(f["football-data.co.uk"][0], "att")
        self.assertIn("fermo all'ultimo dato del 05/10", f["football-data.co.uk"][1])

    def test_dazn_non_risponde(self):
        self.assertEqual(self.fonti(quote_giocatori={}, nota_quote=None)["DAZN Bet"][0], "no")
        self.assertEqual(self.fonti(nota_quote="Quote scaricate dal PC alle 10:00.")["DAZN Bet"][0], "att")

    def test_kickest_e_transfermarkt(self):
        f = self.fonti(mancanti=[2025], n_tm=0)
        self.assertEqual((f["Kickest (riserva, falli e contrasti)"][0], f["Transfermarkt (storico principale)"][0]), ("att", "att"))
        self.assertIn("2459 giocatori con storico dal 2022/23", self.fonti()["Transfermarkt (storico principale)"][1])

    def test_riquadro_html_senza_codice_iniettato(self):
        html = pagina.sezione_fonti([("Sito", "ok", "testo <script>alert(1)</script>")])
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertEqual(pagina.sezione_fonti([]), "")


if __name__ == "__main__":
    unittest.main()


class RiprovaSulPC(unittest.TestCase):
    """server.py: dopo un aggiornamento non riuscito non si aspetta mezz'ora."""

    def test_attese(self):
        import server
        self.assertEqual([server.attesa_dopo(n) for n in range(5)], [1800, 180, 600, 1800, 1800])
