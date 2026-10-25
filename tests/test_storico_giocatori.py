"""Storico dei giocatori: collegamento per nome, fonte primaria (Transfermarkt) e archivio delle stagioni finite.

Nessuna rete: tabelle finte con le stesse colonne di Kickest e Transfermarkt.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import calcoli
import presenza
from fonti import transfermarkt

COL_K = ["stagione", "id", "nome", "nome_completo", "squadra", "ruolo", "presenze", "titolare", "minuti", "gialli", "rossi",
         "falli", "falli_sub", "contrasti", "contrasti_vinti"]
COL_T = ["stagione", "squadra", "id_tm", "nome", "ruolo", "convocato", "presenze", "gialli", "doppi", "rossi", "entrate", "uscite",
         "minuti", "nome_completo", "titolare", "panchina"]


def riga_k(nome, id_, squadra="roma", ruolo="D", gialli=10.0, falli=60.0, stagione=2025):
    return dict(stagione=stagione, id=id_, nome=nome, nome_completo=nome.lower(), squadra=squadra, ruolo=ruolo, presenze=30,
                titolare=28, minuti=2500.0, gialli=gialli, rossi=0.0, falli=falli, falli_sub=20.0, contrasti=70.0,
                contrasti_vinti=40.0)


def riga_t(nome, id_, squadra="roma", ruolo="D", gialli=3.0, stagione=2025):
    return dict(stagione=stagione, squadra=squadra, id_tm=id_, nome=nome, ruolo=ruolo, convocato=32.0, presenze=30.0,
                gialli=gialli, doppi=0.0, rossi=0.0, entrate=2.0, uscite=5.0, minuti=2500.0, nome_completo=nome.lower(),
                titolare=28.0, panchina=4.0)


class CollegamentoPerNome(unittest.TestCase):
    def collega(self, nomi_storico, nome, squadra="milan"):
        tabella = pd.DataFrame([riga_k(n, "id%d" % i, squadra=sq) for i, (n, sq) in enumerate(nomi_storico)], columns=COL_K)
        return calcoli._Collegamento(tabella, "id").trova(nome, squadra)

    def test_stesso_nome_di_battesimo_non_basta(self):
        # Christian Comotto (Milan) non è Christian Pulisic: prima ereditava lo storico del compagno
        self.assertIsNone(self.collega([("christian mate pulisic", "milan")], "Christian Comotto"))
        self.assertIsNone(self.collega([("matteo darmian", "inter")], "Matteo Lavelli", "inter"))
        self.assertIsNone(self.collega([("alessandro deiola", "cagliari")], "Alessandro Romano", "cagliari"))

    def test_nomi_lunghi_e_soprannomi_si_riconoscono_dal_cognome(self):
        self.assertEqual(self.collega([("nicolas paz martinez", "como")], "Nico Paz", "como"), "id0")
        self.assertEqual(self.collega([("torbjorn lysaker heggem", "bologna")], "Torbjørn Heggem", "bologna"), "id0")
        self.assertEqual(self.collega([("giovane santana do nascimento", "napoli")], "Giovane", "napoli"), "id0")
        self.assertEqual(self.collega([("gaspar", "lecce")], "Kialonda Gaspar", "lecce"), "id0")

    def test_giocatore_che_ha_cambiato_squadra(self):
        self.assertEqual(self.collega([("mario gila fuentes", "lazio")], "Mario Gila", "milan"), "id0")

    def test_sceglie_quello_giusto_tra_due_con_lo_stesso_nome(self):
        tabella = pd.DataFrame([riga_k("matteo darmian", "a", "inter"), riga_k("matteo lavelli", "b", "inter")], columns=COL_K)
        self.assertEqual(calcoli._Collegamento(tabella, "id").trova("Matteo Lavelli", "inter"), "b")


class FontePrimaria(unittest.TestCase):
    def setUp(self):
        self.pm = presenza.ModelloPresenza({}, stagione_corrente=2026)
        self.kick = pd.DataFrame([riga_k("Mario Rossi", "k1", gialli=10.0, falli=200.0, ruolo="D"),   # commette molti falli
                                  riga_k("Luca Verdi", "k2", gialli=6.0, falli=20.0, ruolo="D"),
                                  riga_k("Giulio Attacchi", "k3", ruolo="A", gialli=2.0, falli=20.0)], columns=COL_K)
        self.tm = pd.DataFrame([riga_t("Mario Rossi", "t1", gialli=3.0, ruolo="C"),
                                riga_t("Paolo Neri", "t2", gialli=8.0)], columns=COL_T)

    def profilo(self, primaria, nome):
        return calcoli.ProfiliGiocatori(self.kick, self.tm, {}, 2026, self.pm, primaria).profilo("x", nome, "roma", "CD")

    def test_primaria_transfermarkt_usa_i_gialli_di_transfermarkt(self):
        tm_primo = self.profilo("tm", "Mario Rossi")
        k_primo = self.profilo("kickest", "Mario Rossi")
        self.assertLess(tm_primo["y90"], k_primo["y90"])   # 3 gialli di Transfermarkt contro 10 di Kickest
        self.assertLess(tm_primo["lam"], k_primo["lam"])

    def test_se_la_primaria_non_lo_conosce_usa_l_altra(self):
        self.assertTrue(self.profilo("tm", "Luca Verdi")["collegato"])        # solo Kickest
        self.assertTrue(self.profilo("kickest", "Paolo Neri")["collegato"])   # solo Transfermarkt
        self.assertFalse(self.profilo("tm", "Mai Visto")["collegato"])

    def test_i_falli_vengono_sempre_da_kickest(self):
        solo_tm = self.profilo("tm", "Paolo Neri")["f90"]          # Transfermarkt non ha i falli: media del ruolo
        con_kickest = self.profilo("tm", "Mario Rossi")["f90"]     # gialli da Transfermarkt, falli da Kickest (200 in 2500')
        self.assertGreater(con_kickest, solo_tm)
        self.assertAlmostEqual(solo_tm, self.profilo("tm", "Mai Visto")["f90"])   # nessun valore distorto dai minuti di Transfermarkt

    def test_il_ruolo_e_quello_di_kickest(self):
        self.assertEqual(self.profilo("tm", "Mario Rossi")["ruolo"], "D")   # Transfermarkt lo dà centrocampista


def rose_finte(anni, squadre=20):
    return {a: [riga_t("Giocatore %d-%d" % (a, i), "t%d-%d" % (a, i), squadra="squadra %d" % (i % squadre), stagione=a)
                for i in range(squadre * 2)] for a in anni}


class ArchivioTransfermarkt(unittest.TestCase):
    """Le stagioni finite si tengono in transfermarkt_passato.json: GitHub non può leggere il sito."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.archivio = Path(self.tmp.name) / "tm.json"
        self.rose = rose_finte([2024, 2025])
        for p in (mock.patch.object(transfermarkt, "ARCHIVIO", self.archivio),
                  mock.patch.object(transfermarkt, "STAGIONE_CORRENTE", 2026),
                  mock.patch.dict(os.environ, {}, clear=False)):
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("GITHUB_ACTIONS", None)

    def squadre(self, anno):
        return [("s%d" % i, str(i), "Squadra %d" % i) for i in range(20)]

    def giocatori(self, slug, id_squadra, nome, anno):
        return [r for r in self.rose.get(anno, []) if r["squadra"] == "squadra %s" % id_squadra]

    def carica(self, rete=True):
        sq = self.squadre if rete else (lambda anno: [])
        with mock.patch.object(transfermarkt, "squadre_stagione", side_effect=sq), \
                mock.patch.object(transfermarkt, "giocatori_squadra", side_effect=self.giocatori):
            return transfermarkt.carica([2024, 2025])

    def test_sul_pc_scrive_l_archivio_e_non_lo_riscrive_se_non_cambia(self):
        df = self.carica()
        self.assertEqual(len(df), 80)
        self.assertTrue(self.archivio.exists())
        prima = self.archivio.read_bytes()
        self.carica()
        self.assertEqual(self.archivio.read_bytes(), prima)

    def test_se_il_sito_non_risponde_usa_l_archivio(self):
        self.carica()
        df = self.carica(rete=False)
        self.assertEqual(len(df), 80)

    def test_una_stagione_letta_in_parte_non_sostituisce_l_archivio(self):
        self.carica()
        prima = self.archivio.read_bytes()
        self.rose[2025] = [r for r in self.rose[2025] if int(r["squadra"].split()[1]) < 10]   # solo 10 squadre su 20
        df = self.carica()
        self.assertEqual(len(df), 80)                          # per la 2025 si usa l'archivio
        self.assertEqual(self.archivio.read_bytes(), prima)

    def test_una_stagione_letta_in_parte_non_finisce_nell_archivio(self):
        import json
        self.rose[2025] = [r for r in self.rose[2025] if int(r["squadra"].split()[1]) < 10]   # solo 10 squadre su 20
        self.carica()                                          # archivio ancora vuoto: nessuna copia a cui ripiegare
        salvate = {r["stagione"] for r in json.loads(self.archivio.read_text(encoding="utf-8"))}
        self.assertEqual(salvate, {2024})                      # solo la stagione letta per intero

    def test_su_github_si_legge_solo_l_archivio_senza_toccare_il_sito(self):
        self.carica()
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), \
                mock.patch.object(transfermarkt, "squadre_stagione", side_effect=AssertionError("rete usata")):
            df = transfermarkt.carica([2024, 2025])
        self.assertEqual(len(df), 80)

    def test_la_stagione_in_corso_non_entra_nell_archivio(self):
        self.rose[2026] = rose_finte([2026])[2026]
        with mock.patch.object(transfermarkt, "squadre_stagione", side_effect=self.squadre), \
                mock.patch.object(transfermarkt, "giocatori_squadra", side_effect=self.giocatori):
            transfermarkt.carica([2025, 2026])
        import json
        self.assertEqual({r["stagione"] for r in json.loads(self.archivio.read_text(encoding="utf-8"))}, {2025})


if __name__ == "__main__":
    unittest.main()
