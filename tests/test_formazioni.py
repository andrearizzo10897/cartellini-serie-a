"""Lettori delle formazioni ufficiali (Sky, SosFanta): testi e rose salvati, nessuna rete.

Ogni caso qui sotto è uno che si è rotto davvero: se Sky o SosFanta cambiano formato il test fallisce
subito invece di far sparire le ufficiali dalla pagina senza accorgersene.
"""
import unittest
from unittest import mock

from fonti import sky, sosfanta

# ---- testi come arrivano dalle pagine (già ripuliti dai tag) ---------------------------------------
SKY_VENEZIA_NAPOLI = (
    "Venezia-Napoli, le formazioni ufficiali e il risultato LIVE Allegri punta su Lucca. GUARDA TUTTI GLI HIGHLIGHTS "
    "FORMAZIONI UFFICIALI VENEZIA (3-5-2): Stankovic; Halhal, Juan Jesus, Moreno; Hainaut, Kike Perez, Basic, Sohm, Haps; "
    "Yeboah, Adams. All. Nicola NAPOLI (3-4-2-1): Meret; Beukema, Rrahmani, Badiashile; Di Lorenzo, Lobotka, Gilmour, "
    "Spinazzola; Giovane, McTominay; Lucca. All. Allegri • NAPOLI (3-4-2-1): Meret; Beukema ...")
# il 17/10 Sky scriveva uno spazio prima dei due punti e questo faceva scartare la partita
SKY_BOLOGNA_INTER = (
    "FORMAZIONI UFFICIALI BOLOGNA (3-4-2-1) : Skorupski; Darmian, Casale, Theate; Zortea, Ferguson, Pobega, Miranda; "
    "Bernardeschi, Cambiaghi; Piccoli. All. Palladino INTER (3-5-2): Martinez; Bisseck, Akanji, Bastoni; Luis Henrique, "
    "Barella, Zielinski, Sucic, Dimarco; Thuram, Pio Esposito. All. Chivu L'Inter ha alternato un pareggio ad una vittoria.")
SKY_PROBABILI = ("Le probabili formazioni di Venezia – Napoli Venezia VS Napoli 3-5-2 3-4-2-1 Titolari 1 Stankovic F. "
                 "3 Schingtienne J. Riserve Montipò, Grandi Allenatore Davide Nicola Massimiliano Allegri")
SOSFANTA_VENEZIA_NAPOLI = (
    "le formazioni ufficiali: la scelta su De Bruyne! Hojlund, Lang, McTominay... - SOS Fanta Accedi Cerca Venezia-Napoli, "
    "le formazioni ufficiali: la scelta su De Bruyne! LE FORMAZIONI UFFICIALI VENEZIA - Stankovic; Moreno, Juan Jesus, "
    "Halhal; Hainaut, Kike Perez, Sohm, Basic, Haps; Yeboah, Adams. NAPOLI - Meret; Beukema, Rrahmani, Badiashile; "
    "Di Lorenzo, Lobotka, Gilmour, Spinazzola; Giovane, McTominay; Lucca. 🆘 CLICCA QUI PER TUTTE LE PROBABILI FORMAZIONI "
    "© RIPRODUZIONE RISERVATA Commenta")


def g(i, nome, ruolo="CM", titolare=False):
    return {"id": str(i), "nome": nome, "ruolo_espn": ruolo, "titolare": titolare, "entrato": False, "uscito": False,
            "presenze": 0, "gialli": 0, "rossi": 0, "falli": 0, "falli_sub": 0}


ROSA_VENEZIA = [g(1, "Filip Stankovic", "G"), g(2, "Redouane Halhal", "CD"), g(3, "Juan Jesus", "CD"),
                g(4, "Matías Moreno", "CD"), g(5, "Antoine Hainaut", "RM"), g(6, "Enrique Pérez", "CM"),
                g(7, "Tomás Basic", "CM"), g(8, "Samuel Sohm", "CM"), g(9, "Rafael Haps", "LM"),
                g(10, "Joshua Yeboah", "F"), g(11, "Adams Adams", "F"), g(12, "Marco Panchina", "G")]
ROSA_NAPOLI = [g(21, "Alex Meret", "G"), g(22, "Sam Beukema", "CD"), g(23, "Amir Rrahmani", "CD"),
               g(24, "Benoît Badiashile", "CD"), g(25, "Giovanni Di Lorenzo", "RB"), g(26, "Stanislav Lobotka", "CM"),
               g(27, "Billy Gilmour", "CM"), g(28, "Leonardo Spinazzola", "LB"), g(29, "Giovane", "AM"),
               g(30, "Scott McTominay", "AM"), g(31, "Lorenzo Lucca", "F"), g(32, "Romelu Panchina", "F")]
EV_VN = {"casa": "venezia", "trasf": "napoli", "id_casa": "17530", "id_trasf": "114"}


class LetturaSky(unittest.TestCase):
    def test_legge_modulo_e_undici_nomi(self):
        (m1, n1), (m2, n2) = sky._estrai(SKY_VENEZIA_NAPOLI)
        self.assertEqual((m1, m2), ("3-5-2", "3-4-2-1"))
        self.assertEqual(len(n1), 11)
        self.assertEqual(len(n2), 11)
        self.assertEqual((n1[0], n2[0]), ("Stankovic", "Meret"))
        self.assertIn("Kike Perez", n1)

    def test_spazio_prima_dei_due_punti(self):
        (m1, n1), (m2, n2) = sky._estrai(SKY_BOLOGNA_INTER)
        self.assertEqual((m1, m2), ("3-4-2-1", "3-5-2"))
        self.assertEqual((n1[0], n2[0]), ("Skorupski", "Martinez"))
        self.assertIn("Luis Henrique", n2)

    def test_probabili_non_sono_ufficiali(self):
        self.assertIsNone(sky._estrai(SKY_PROBABILI))

    def test_formazione_con_meno_di_undici_nomi_si_scarta(self):
        testo = SKY_VENEZIA_NAPOLI.replace("Yeboah, Adams. All. Nicola", "Yeboah. All. Nicola")
        self.assertIsNone(sky._estrai(testo))


class AbbinamentoNomi(unittest.TestCase):
    def test_soprannome_kike_perez(self):
        self.assertEqual(sky._trova("Kike Perez", ROSA_VENEZIA, set())["nome"], "Enrique Pérez")

    def test_due_martinez_portiere_o_attaccante(self):
        rosa = [g(1, "Lautaro Martínez", "F"), g(2, "Josep Martínez", "G")]
        self.assertEqual(sky._trova("Martinez", rosa, set(), portiere=True)["nome"], "Josep Martínez")
        self.assertEqual(sky._trova("Martinez", rosa, set(), portiere=False)["nome"], "Lautaro Martínez")

    def test_non_riusa_un_giocatore_gia_assegnato(self):
        rosa = [g(1, "Lautaro Martínez", "F"), g(2, "Josep Martínez", "G")]
        self.assertEqual(sky._trova("Martinez", rosa, {"2"}, portiere=True)["nome"], "Lautaro Martínez")

    def test_nome_sconosciuto(self):
        self.assertIsNone(sky._trova("Sconosciutissimo", ROSA_VENEZIA, set()))


class DaNomiAFormazione(unittest.TestCase):
    def _forma(self, estratte, ultima=None):
        rose = {"17530": ROSA_VENEZIA, "114": ROSA_NAPOLI}
        with mock.patch.object(sky, "_rosa", side_effect=lambda id_sq: rose[id_sq]):
            return sky.da_nomi(EV_VN, ultima or {}, estratte)

    def test_venezia_napoli_da_sky(self):
        forma = self._forma(sky._estrai(SKY_VENEZIA_NAPOLI))
        self.assertEqual(forma["home"]["formazione"], "3-5-2")
        for lato, rosa in (("home", ROSA_VENEZIA), ("away", ROSA_NAPOLI)):
            giocatori = forma[lato]["giocatori"]
            titolari = [x for x in giocatori if x["titolare"]]
            self.assertEqual(len(titolari), 11)
            self.assertEqual(len(giocatori), len(rosa))          # tutti gli altri in panchina
            self.assertFalse({x["id"] for x in titolari} & {x["id"] for x in giocatori if not x["titolare"]})
        self.assertEqual([x["nome"] for x in forma["home"]["giocatori"] if x["titolare"]][0], "Filip Stankovic")

    def test_venezia_napoli_da_sosfanta_senza_modulo(self):
        forma = self._forma(sosfanta._estrai(SOSFANTA_VENEZIA_NAPOLI, EV_VN))
        self.assertIsNone(forma["home"]["formazione"])
        self.assertEqual(sum(1 for x in forma["away"]["giocatori"] if x["titolare"]), 11)

    def test_un_nome_sconosciuto_si_ricava_per_esclusione(self):
        # "Pote" è il soprannome di Pedro Gonçalves: senza la tabella dei soprannomi lo trovo da chi manca all'appello
        nomi = ["de Gea", "Jimenez", "Dragusin", "Pongracic", "Viery", "Ndour", "Fagioli", "Mastantuono", "Pote", "Njie",
                "Pellegrino"]
        rosa = [g(1, "David de Gea", "G", True), g(2, "Álex Jiménez", "RB", True), g(3, "Radu Dragusin", "CD-R", True),
                g(4, "Marin Pongracic", "CD-L", True), g(5, "Viery", "LB", True), g(6, "Cher Ndour", "RM", True),
                g(7, "Niccolò Fagioli", "LM", True), g(8, "Pedro Gonçalves", "AM", True),
                g(9, "Franco Mastantuono", "AM-R", True), g(10, "Alieu Njie", "AM-L", True),
                g(11, "Mateo Pellegrino", "F", True), g(12, "Panchinaro Uno", "CM")]
        ev = {"casa": "fiorentina", "trasf": "como", "id_casa": "1", "id_trasf": "2"}
        with mock.patch.dict(sky.SOPRANNOMI, clear=True), mock.patch.object(sky, "_rosa", return_value=rosa):
            forma = sky.da_nomi(ev, {"fiorentina": rosa, "como": rosa}, [("3-4-2-1", nomi), ("3-4-2-1", nomi)])
        self.assertIn("Pedro Gonçalves", [x["nome"] for x in forma["home"]["giocatori"] if x["titolare"]])

    def test_soprannome_nella_tabella(self):
        rosa = [g(8, "Pedro Gonçalves", "AM")]
        self.assertEqual(sky._trova("Pote", rosa, set())["id"], "8")

    def test_due_nomi_sconosciuti_scartano_la_formazione(self):
        estratte = sky._estrai(SKY_VENEZIA_NAPOLI)
        estratte[0][1][1] = "Inesistente Uno"
        estratte[0][1][2] = "Inesistente Due"
        self.assertIsNone(self._forma(estratte))


class LetturaSosFanta(unittest.TestCase):
    def test_legge_il_blocco_in_maiuscolo_non_il_titolo(self):
        (m1, n1), (m2, n2) = sosfanta._estrai(SOSFANTA_VENEZIA_NAPOLI, EV_VN)
        self.assertEqual((m1, m2), (None, None))
        self.assertEqual((n1[0], n1[-1], n2[0], n2[-1]), ("Stankovic", "Adams", "Meret", "Lucca"))
        self.assertEqual((len(n1), len(n2)), (11, 11))

    def test_solo_titolo_senza_blocco(self):
        self.assertIsNone(sosfanta._estrai("Venezia-Napoli, le formazioni ufficiali: la scelta su De Bruyne!", EV_VN))

    def test_cerca_l_articolo_giusto(self):
        home = ('<a href="https://www.sosfanta.com/news/formazioni-ufficiali-roma-genoa-mora-soule/">x</a>'
                '<a href="https://www.sosfanta.com/news/formazioni-ufficiali-venezia-napoli-de-bruyne-lucca/">y</a>'
                '<a href="https://www.sosfanta.com/news/formazioni-ufficiali-hellas-verona-lecce-x-y/">z</a>')
        with mock.patch.object(sosfanta, "scarica", return_value=mock.Mock(text=home)):
            self.assertTrue(sosfanta._link(EV_VN).endswith("venezia-napoli-de-bruyne-lucca/"))
            self.assertIn("hellas-verona-lecce", sosfanta._link({"casa": "verona", "trasf": "lecce"}))
            self.assertIsNone(sosfanta._link({"casa": "roma", "trasf": "cagliari"}))


class SenzaRete(unittest.TestCase):
    def test_se_il_sito_non_risponde_restituisce_none(self):
        with mock.patch.object(sky, "scarica", side_effect=OSError("rete")):
            self.assertIsNone(sky.ufficiali(EV_VN, 2026, {}, 7))
        with mock.patch.object(sosfanta, "scarica", side_effect=OSError("rete")):
            self.assertIsNone(sosfanta.ufficiali(EV_VN, {}))


if __name__ == "__main__":
    unittest.main()
