"""Lettori delle formazioni ufficiali (Sky, SosFanta): testi e rose salvati, nessuna rete.

Ogni caso qui sotto è uno che si è rotto davvero: se Sky o SosFanta cambiano formato il test fallisce
subito invece di far sparire le ufficiali dalla pagina senza accorgersene.
"""
import unittest
from pathlib import Path
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

    def test_soprannome_nella_tabella(self):
        rosa = [g(8, "Pedro Gonçalves", "AM")]
        self.assertEqual(sky._trova("Pote", rosa, set())["id"], "8")

    def test_due_nomi_sconosciuti_scartano_la_formazione(self):
        estratte = sky._estrai(SKY_VENEZIA_NAPOLI)
        estratte[0][1][1] = "Inesistente Uno"
        estratte[0][1][2] = "Inesistente Due"
        self.assertIsNone(self._forma(estratte))


FIXTURE = Path(__file__).parent / "fixtures"
EV_FC = {"casa": "fiorentina", "trasf": "como", "id_casa": "1", "id_trasf": "2"}
# ESPN scrive il nome corto, Sky nell'indirizzo il nome completo
NOMI_ESPN = {"pedro antonio pereira goncalves": "Pedro Gonçalves", "david de gea": "David de Gea", "alex jimenez": "Álex Jiménez"}
DIRETTA_FC = ("FORMAZIONI UFFICIALI FIORENTINA (3-4-2-1): de Gea; Jimenez, Dragusin, Pongracic; Viery, Ndour, Fagioli, "
              "Mastantuono; Pote, Njie; Pellegrino. All. Vanoli COMO (4-2-3-1): Butez; Smolcic, Chalobah, Kempf, Valle; "
              "Milla, da Cunha; Liberali, Paz, Caqueret; Douvikas. All. Fabregas")


def leggi(nome):
    return sky.leggi_formazioni((FIXTURE / nome).read_text(encoding="utf-8"))


def rose_dalla_pagina(dati, senza=()):
    """Le rose ESPN che corrispondono alla pagina (nomi più corti, come in ESPN), salvo i nomi completi in `senza`."""
    rose = {}
    for lato in ("home", "away"):
        rosa = []
        for i, (numero, completo, _) in enumerate(dati["titolari"][lato] + dati["riserve"][lato]):
            if completo not in senza:
                rosa.append({"id": "%s%d" % (lato, numero), "nome": NOMI_ESPN.get(completo, completo.title()),
                             "ruolo_espn": "G" if i == 0 else "CM", "numero": str(numero)})
        rose["1" if lato == "home" else "2"] = rosa
    return rose


class PaginaFormazioniSky(unittest.TestCase):
    def test_pagina_ufficiale_titolari_e_panchina(self):
        d = leggi("sky_formazioni_ufficiali.html")
        self.assertTrue(d["ufficiale"])
        self.assertEqual((len(d["titolari"]["home"]), len(d["titolari"]["away"])), (11, 11))
        self.assertEqual((len(d["riserve"]["home"]), len(d["riserve"]["away"])), (12, 14))
        self.assertEqual(d["titolari"]["home"][0], (43, "david de gea", "de Gea D."))
        self.assertEqual(d["titolari"]["away"][0], (1, "jean butez", "Butez J."))

    def test_il_soprannome_ha_il_nome_completo_nell_indirizzo(self):
        d = leggi("sky_formazioni_ufficiali.html")
        self.assertIn((28, "pedro antonio pereira goncalves", "Pote"), d["titolari"]["home"])
        self.assertEqual(sky.alias(d)["home"]["pote"], "pedro antonio pereira goncalves")
        self.assertEqual(sky.alias(d)["home"]["jimenez"], "alex jimenez")        # le iniziali non contano
        self.assertEqual(sky.alias(d)["away"]["da cunha"], "lucas da cunha")

    def test_pagina_probabile_ha_i_moduli_e_solo_i_titolari(self):
        d = leggi("sky_formazioni_probabili.html")
        self.assertFalse(d["ufficiale"])
        self.assertEqual(d["moduli"], ("3-4-2-1", "4-3-2-1"))
        self.assertEqual((len(d["titolari"]["home"]), len(d["titolari"]["away"])), (11, 11))
        self.assertEqual((d["riserve"]["home"], d["riserve"]["away"]), ([], []))
        self.assertEqual(d["titolari"]["away"][0], (16, "mike maignan", "Maignan M."))

    def test_pagina_senza_tabella(self):
        self.assertIsNone(sky.leggi_formazioni("<html><body>niente</body></html>"))
        self.assertIsNone(sky.leggi_formazioni(None))
        self.assertEqual(sky.alias(None), {"home": {}, "away": {}})


class FormazioneDaSky(unittest.TestCase):
    """sky.ufficiali con le due pagine: la tabella (nomi completi) e la diretta (solo cognomi e soprannomi)."""

    def setUp(self):
        self.ufficiale = leggi("sky_formazioni_ufficiali.html")
        self.rose = rose_dalla_pagina(self.ufficiale)

    def esegui(self, dati, pagine, rose=None):
        """pagine: {"risultato-gol": html}. Restituisce (formazione, pagine richieste)."""
        richieste = []

        def scarica_finta(ev, anno, giornate, pagina):
            richieste.append(pagina)
            return (pagine.get(pagina), 7) if pagine.get(pagina) else (None, None)
        r = rose or self.rose
        with mock.patch.object(sky, "_scarica", side_effect=scarica_finta), \
                mock.patch.object(sky, "_rosa", side_effect=lambda id_sq: r[id_sq]):
            return sky.ufficiali(EV_FC, 2026, {}, 7, dati), richieste

    def diretta(self, testo=DIRETTA_FC):
        return "<html><body><p>%s</p></body></html>" % testo

    def test_pagina_ufficiale_basta_da_sola(self):
        forma, richieste = self.esegui(self.ufficiale, {})
        self.assertEqual(richieste, [])                                        # non serve nemmeno la diretta
        titolari = [x["nome"] for x in forma["home"]["giocatori"] if x["titolare"]]
        self.assertEqual((len(titolari), titolari[0]), (11, "David de Gea"))
        self.assertIn("Pedro Gonçalves", titolari)
        self.assertEqual(sum(1 for x in forma["home"]["giocatori"] if not x["titolare"]), 12)    # la panchina vera
        self.assertEqual(sum(1 for x in forma["away"]["giocatori"] if not x["titolare"]), 14)

    def test_pagina_probabile_e_diretta_ufficiale_traduce_i_soprannomi(self):
        probabile = dict(self.ufficiale, ufficiale=False)                      # stessa tabella, ma ancora "probabile"
        with mock.patch.dict(sky.SOPRANNOMI, clear=True):                      # senza la tabella dei soprannomi
            forma, richieste = self.esegui(probabile, {"risultato-gol": self.diretta()})
        self.assertEqual(richieste, ["risultato-gol"])
        self.assertIn("Pedro Gonçalves", [x["nome"] for x in forma["home"]["giocatori"] if x["titolare"]])
        self.assertEqual(forma["home"]["formazione"], "3-4-2-1")

    def test_senza_la_pagina_formazioni_vale_la_tabella_dei_soprannomi(self):
        forma, _ = self.esegui(None, {"risultato-gol": self.diretta()})
        self.assertIn("Pedro Gonçalves", [x["nome"] for x in forma["home"]["giocatori"] if x["titolare"]])

    def test_soprannome_che_nessuno_traduce_scarta_la_fonte(self):
        with mock.patch.dict(sky.SOPRANNOMI, clear=True):
            forma, _ = self.esegui(None, {"risultato-gol": self.diretta()})     # niente pagina, niente tabella
        self.assertIsNone(forma)

    def test_pagina_ufficiale_con_un_nome_irriconoscibile_ripiega_sulla_diretta(self):
        rose = rose_dalla_pagina(self.ufficiale, senza={"pedro antonio pereira goncalves"})   # ESPN non lo ha
        forma, richieste = self.esegui(self.ufficiale, {"risultato-gol": self.diretta()}, rose=rose)
        self.assertEqual(richieste, ["risultato-gol"])
        self.assertIsNone(forma)                                                # nemmeno la diretta può risolvere Pote

    def test_nessuna_pagina(self):
        forma, _ = self.esegui(None, {})
        self.assertIsNone(forma)

    def test_pagina_con_meno_di_undici_titolari_non_si_usa(self):
        troncata = dict(self.ufficiale, titolari=dict(self.ufficiale["titolari"], home=self.ufficiale["titolari"]["home"][:10]))
        forma, richieste = self.esegui(troncata, {})
        self.assertIsNone(forma)
        self.assertEqual(richieste, ["risultato-gol"])                          # ripiega sulla diretta (che qui non c'è)


class SosFantaConNomiCompleti(unittest.TestCase):
    """SosFanta scrive gli stessi soprannomi: li traduce con i nomi completi letti da Sky."""

    ARTICOLO = ("LE FORMAZIONI UFFICIALI FIORENTINA - de Gea; Jimenez, Dragusin, Pongracic; Viery, Ndour, Fagioli, Mastantuono; "
                "Pote, Njie; Pellegrino. COMO - Butez; Smolcic, Chalobah, Kempf, Valle; Milla, da Cunha; Liberali, Paz, Caqueret; "
                "Douvikas. 🆘 CLICCA QUI PER TUTTE LE PROBABILI FORMAZIONI")

    def esegui(self, tradotti):
        dati = leggi("sky_formazioni_ufficiali.html")
        rose = rose_dalla_pagina(dati)
        with mock.patch.dict(sky.SOPRANNOMI, clear=True), \
                mock.patch.object(sosfanta, "_link", return_value="https://www.sosfanta.com/news/x/"), \
                mock.patch.object(sosfanta, "scarica", return_value=mock.Mock(text="<p>%s</p>" % self.ARTICOLO)), \
                mock.patch.object(sky, "_rosa", side_effect=lambda id_sq: rose[id_sq]):
            return sosfanta.ufficiali(EV_FC, {}, tradotti)

    def test_con_i_nomi_completi_di_sky(self):
        forma = self.esegui(sky.alias(leggi("sky_formazioni_ufficiali.html")))
        self.assertIn("Pedro Gonçalves", [x["nome"] for x in forma["home"]["giocatori"] if x["titolare"]])

    def test_senza_nomi_completi_il_soprannome_scarta_la_fonte(self):
        self.assertIsNone(self.esegui(None))


class NomeCompleto(unittest.TestCase):
    def test_il_nome_espn_e_piu_corto_di_quello_di_sky(self):
        rosa = [g(1, "Pedro Gonçalves"), g(2, "Marco Altro")]
        self.assertEqual(sky._trova_completo("pedro antonio pereira goncalves", rosa, set())["id"], "1")

    def test_vince_il_nome_piu_specifico(self):
        rosa = [g(1, "Pedro"), g(2, "Pedro Gonçalves")]
        self.assertEqual(sky._trova_completo("pedro antonio pereira goncalves", rosa, set())["id"], "2")

    def test_a_parita_decide_il_numero_di_maglia(self):
        rosa = [dict(g(1, "Jesus"), numero="9"), dict(g(2, "Rodriguez"), numero="17")]
        self.assertEqual(sky._trova_completo("jesus rodriguez", rosa, set(), numero=17)["id"], "2")

    def test_a_parita_senza_numero_nessuno(self):
        rosa = [g(1, "Jesus"), g(2, "Rodriguez")]
        self.assertIsNone(sky._trova_completo("jesus rodriguez", rosa, set()))

    def test_portiere_tra_due_omonimi(self):
        rosa = [g(1, "Lautaro Martínez", "F"), g(2, "Josep Martínez", "G")]
        self.assertEqual(sky._trova_completo("josep martinez", rosa, set(), portiere=True)["id"], "2")
        self.assertEqual(sky._trova_completo("lautaro martinez", rosa, set())["id"], "1")

    def test_senza_corrispondenza_prova_il_cognome(self):
        rosa = [g(1, "Enrique Pérez")]      # per Sky "Kike Perez": il cognome è di un solo giocatore
        self.assertEqual(sky._trova_completo("kike perez", rosa, set())["id"], "1")
        self.assertIsNone(sky._trova_completo("tizio sconosciuto", rosa, set()))


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
