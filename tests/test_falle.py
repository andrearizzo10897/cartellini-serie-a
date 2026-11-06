"""Le falle trovate dalla revisione critica del 5/11/2026: valore atteso, squalificati, riquadro fonti, omonimi, scritture. Nessuna rete."""
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pandas as pd

import aggiorna
import calcoli
import pagina
import server
import utils
from fonti import aia, articoli, daznbet, dimarzio, espn, fantacalcio, sky, sosfanta

FISCHIO = datetime(2026, 11, 7, 18, 0)


class ValoreAtteso(unittest.TestCase):
    def motivo(self, ufficiale=True, ore_quote=0.5, prima=1.0):
        ora = FISCHIO - timedelta(hours=prima)
        return calcoli.motivo_senza_ev(FISCHIO, ufficiale, ora - timedelta(hours=ore_quote) if ore_quote is not None else None, ora)

    def test_si_mostra_solo_con_ufficiali_e_quote_fresche(self):
        self.assertIsNone(self.motivo())

    def test_formazione_probabile(self):
        self.assertEqual(self.motivo(ufficiale=False), "attesa ufficiali")

    def test_quote_vecchie_o_mancanti(self):
        self.assertEqual(self.motivo(ore_quote=3), "quota vecchia")
        self.assertEqual(self.motivo(ore_quote=None), "quota vecchia")

    def test_quote_scaricate_prima_che_uscissero_le_ufficiali(self):
        self.assertEqual(self.motivo(ore_quote=1, prima=1), "quota vecchia")     # due ore prima del fischio: ancora senza ufficiali

    def test_partita_iniziata(self):
        self.assertEqual(self.motivo(prima=-0.1), "iniziata")

    def test_cella_senza_valore_atteso_dice_il_motivo(self):
        cella = pagina.cella_book({"quota_book": 5.0, "p_giallo": 0.5}, "attesa ufficiali")
        self.assertIn("attesa ufficiali", cella)
        self.assertNotIn("%", cella)
        self.assertNotIn("p-alta", cella)

    def test_cella_formula_e_verde_prudente(self):
        positivo_fragile = pagina.cella_book({"quota_book": 5.0, "p_giallo": 0.22})   # EV +10%, con p x 0,8 negativo
        self.assertIn("+10%", positivo_fragile)
        self.assertNotIn("p-alta", positivo_fragile)
        robusto = pagina.cella_book({"quota_book": 5.0, "p_giallo": 0.30})            # EV +50%, con p x 0,8 ancora +20%
        self.assertIn("+50%", robusto)
        self.assertIn("p-alta", robusto)
        self.assertIn("-50%", pagina.cella_book({"quota_book": 2.0, "p_giallo": 0.25}))

    def test_cella_con_il_fischio_per_il_javascript(self):
        cella = pagina.cella_book({"quota_book": 5.0, "p_giallo": 0.3, "fischio": FISCHIO})
        self.assertIn('class="q ev p-alta"', cella)
        self.assertIn('data-fischio="2026-11-07T18:00+01:00"', cella)

    def test_cella_senza_quota(self):
        self.assertIn("–", pagina.cella_book({"quota_book": None, "p_giallo": 0.2}))


class Presenza:
    """Finto modello di presenza: ogni titolare ha esposizione 1 e P(giallo) = lam."""
    portieri = set()
    n_entrate, n_uscite = {}, {}

    def esposizione_titolare(self, _id, _ruolo):
        return 1.0, 0.2, 70

    def esposizione_subentrato(self):
        return 0.3

    def p_giallo_titolare(self, lam, _id, _ruolo):
        return lam

    def p_giallo_se_entra(self, lam):
        return lam * 0.3


class PartitaIntera(unittest.TestCase):
    def test_i_gialli_dei_giocatori_tornano_al_totale_della_squadra(self):
        titolari = [{"id": str(i), "ruolo": "C", "lam": 0.1} for i in range(10)]
        k = calcoli.riconcilia_squadra(titolari, [], "roma", 2.0, Presenza())
        self.assertAlmostEqual(k, 2.0)
        self.assertAlmostEqual(sum(g["p_giallo"] for g in titolari), 2.0)

    def contesto(self, **altro):
        profili = mock.Mock()
        profili.profilo.side_effect = lambda id_, nome, sq, ruolo: {"id": id_, "nome": nome, "ruolo": "C", "lam": 0.2, "collegato": True, "y90": 0.2,
                                                               "f90": 1.0, "t90": 1.0, "gialli_stag": 0, "presenze_stag": 0}
        base = {"anno": 2026, "df": pd.DataFrame({"g_tot": [9, 9, 3, 3], "tipo": ["Derby", "Derby", "Normale", "Normale"]}), "designazioni": {},
                "aia_risolte": {}, "tabelle": {}, "rapporto_var": 1.0, "presenza": Presenza(), "profili": profili,
                "quote_ora": FISCHIO - timedelta(hours=1), "adesso": FISCHIO - timedelta(minutes=50),
                "squalificati": {"roma": [("9", "Mario Rossi", "espulso")]}}
        base.update(altro)
        return base

    def analizza(self, ufficiale):
        ev = {"casa": "roma", "trasf": "genoa", "inizio": FISCHIO, "id": "1"}
        forma = {"home": {"formazione": None, "giocatori": [{"id": "1", "nome": "A", "ruolo_espn": "CM", "titolare": True}]}}
        with mock.patch.object(calcoli, "fattore_arbitro", return_value=(1.1, None)), \
                mock.patch.object(calcoli, "tipo_partita", return_value="Derby"), \
                mock.patch.object(calcoli, "gialli_attesi", return_value=(2.0, 2.0)):
            return calcoli.analizza_partita(ev, forma, ufficiale, self.contesto())

    def test_il_tipo_di_partita_non_cambia_la_stima(self):
        self.assertAlmostEqual(self.analizza(True)["atteso"], 4.4)                   # 4 x arbitro 1,1, derby o no

    def test_ufficiale_con_quote_fresche(self):
        casa = self.analizza(True)["squadre"][0]
        self.assertIsNone(casa["no_ev"])
        self.assertEqual(casa["squalificati"], [])

    def test_probabile_niente_valore_atteso_e_squalificati_segnalati(self):
        casa = self.analizza(False)["squadre"][0]
        self.assertEqual(casa["no_ev"], "attesa ufficiali")
        self.assertEqual(casa["squalificati"], [("9", "Mario Rossi", "espulso")])
        self.assertIn("Mario Rossi (espulso)", pagina.tabella_squadra(dict(casa, nome="Roma", atteso=2.0)))


def g(id_, gialli=0, rossi=0, titolare=True):
    return {"id": id_, "nome": "G" + id_, "titolare": titolare, "entrato": False, "uscito": False, "presenze": 1,
            "gialli": gialli, "rossi": rossi, "falli": 0}


class Squalificati(unittest.TestCase):
    def partite(self, *liste):
        return [({"inizio": datetime(2026, 9, 1 + i)}, {"home": {"squadra": "roma", "giocatori": l}}) for i, l in enumerate(liste)]

    def test_rosso_e_quinto_giallo_nell_ultima_partita(self):
        finite = self.partite(*[[g("a", gialli=1), g("b")] for _ in range(4)], [g("a", gialli=1), g("b", rossi=1), g("c", gialli=1)])
        self.assertEqual(calcoli.squalificati(finite), {"roma": [("a", "Ga", "5° giallo"), ("b", "Gb", "espulso")]})

    def test_squalifica_gia_scontata(self):
        finite = self.partite([g("b", rossi=1)], [g("c")])
        self.assertEqual(calcoli.squalificati(finite), {})

    def test_quarto_giallo_non_squalifica(self):
        self.assertEqual(calcoli.squalificati(self.partite(*[[g("a", gialli=1)] for _ in range(4)])), {})

    def test_doppio_giallo_si_vede_dall_evento(self):
        evento = {"tipo": "yellow-card", "persone": ["a"]}
        self.assertTrue(calcoli.ammonito({"id": "a", "gialli": 0, "rossi": 1}, [evento]))
        self.assertFalse(calcoli.ammonito({"id": "b", "gialli": 0, "rossi": 1}, [evento]))
        self.assertTrue(calcoli.ammonito({"id": "c", "gialli": 1}, []))


class SqualificaSoloProssimaPartita(unittest.TestCase):
    ULTIMA = {"roma": [g("a"), g("b")], "genoa": [g("c")]}
    SQUAL = {"roma": [("a", "Ga", "espulso")]}
    EV = {"casa": "roma", "trasf": "genoa"}

    def test_prima_partita_escluso(self):
        ultima, squal = calcoli.formazioni_per_partita(self.EV, self.ULTIMA, self.SQUAL, set())
        self.assertEqual([x["id"] for x in ultima["roma"]], ["b"])
        self.assertEqual(squal, self.SQUAL)
        self.assertEqual(len(self.ULTIMA["roma"]), 2)                              # l'originale non si tocca

    def test_seconda_partita_nella_finestra_rientra(self):
        ultima, squal = calcoli.formazioni_per_partita(self.EV, self.ULTIMA, self.SQUAL, {"roma"})
        self.assertEqual([x["id"] for x in ultima["roma"]], ["a", "b"])
        self.assertEqual(squal, {})


class ArchiviDaNonPerdere(unittest.TestCase):
    """Un archivio bloccato o rovinato deve fermare il giro, non diventare vuoto e poi essere salvato sopra a quello vero."""

    def test_aia_non_sovrascrive(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "designazioni.json"
            f.write_text('{"tronc', encoding="utf-8")
            with mock.patch.object(aia, "ARCHIVIO", f), mock.patch.object(aia, "_pagina", side_effect=AssertionError("non deve arrivarci")):
                with self.assertRaises(ValueError):
                    aia.aggiorna()
            self.assertEqual(f.read_text(encoding="utf-8"), '{"tronc')


class ControlloGialli(unittest.TestCase):
    """Numeri veri del 2026/27, confrontati con i tabellini della Lega Serie A il 5/11/2026."""

    def esegui(self, casa, trasf, fatti):
        fd = pd.DataFrame([{"stagione": 2026, "casa": "genoa", "trasf": "frosinone", "g_c": fatti[0], "g_t": fatti[1]}])
        forma = {"home": {"giocatori": [g(str(i), gialli=x, rossi=r) for i, (x, r) in enumerate(casa)]},
                 "away": {"giocatori": [g("t" + str(i), gialli=x, rossi=r) for i, (x, r) in enumerate(trasf)]}}
        dettagli = {"1": {"eventi": [{"tipo": "yellow-card", "persone": ["0"]}]}}
        return calcoli.controllo_espn(fd, [({"id": "1", "casa": "genoa", "trasf": "frosinone"}, forma)], 2026, dettagli)

    def test_il_doppio_giallo_non_e_una_differenza(self):
        # Genoa-Frosinone: Vásquez doppio giallo, Ehizibue un giallo. ESPN 1, football-data 3
        self.assertEqual(self.esegui([(0, 1), (1, 0)], [(1, 0), (1, 0)], (3, 2)), (1, []))

    def test_una_differenza_vera_si_segnala_con_i_numeri(self):
        # Roma-Atalanta: rosso diretto senza eventi di giallo, football-data ha un giallo in più
        self.assertEqual(self.esegui([(0, 0)], [(1, 0), (0, 1)], (1, 1)), (0, ["genoa-frosinone (ESPN 0-1, football-data 1-1)"]))

    def test_rosso_diretto_non_vale_come_doppio_giallo(self):
        self.assertEqual(self.esegui([(1, 0), (0, 1)], [], (3, 0))[0], 0)            # il giocatore "1" non ha l'evento del giallo


class RiquadroFonti(unittest.TestCase):
    ORA = datetime(2026, 11, 1, 12, 0)

    def fonti(self, **kw):
        base = dict(anno=2026, ultimo_fd=self.ORA.date(), oggi=self.ORA.date(), aggiunte=0, finite=[(None, None)], prossime=[],
                    mancanti=[], kickest_corrente=False, n_tm=1, quote_giocatori={("a", "b"): []}, nota_quote=None,
                    quote_ora=self.ORA - timedelta(minutes=30), n_uff={"ESPN": 0, "Sky": 0, "SosFanta": 0}, cercate=0, partite=[], ora=self.ORA)
        base.update(kw)
        return {nome: (livello, testo) for nome, livello, testo in aggiorna.riepilogo_fonti(**base)}

    def partita(self, ore, arbitro=None, ufficiale=False):
        return {"ev": {"casa": "roma", "trasf": "genoa", "inizio": self.ORA + timedelta(hours=ore)}, "arbitro": arbitro, "ufficiale": ufficiale}

    def test_arbitro_mancante_entro_24_ore_non_e_ok(self):
        # il caso del 1/11: cinque arbitri su dieci spariti, e il riquadro era verde
        f = self.fonti(partite=[self.partita(2, "X"), self.partita(3)])
        self.assertEqual(f["Arbitri (AIA)"][0], "no")
        self.assertIn("roma-genoa", f["Arbitri (AIA)"][1])

    def test_arbitro_non_ancora_designato_piu_avanti_e_normale(self):
        self.assertEqual(self.fonti(partite=[self.partita(72)])["Arbitri (AIA)"][0], "ok")

    def test_copia_salvata_del_calendario(self):
        f = self.fonti(copie_calendario=[date(2026, 11, 1)])
        self.assertEqual(f["ESPN"][0], "no")
        self.assertIn("01/11", f["ESPN"][1])

    def test_ufficiali_che_tardano(self):
        self.assertEqual(self.fonti(partite=[self.partita(4)])["Formazioni ufficiali"][0], "ok")
        self.assertEqual(self.fonti(partite=[self.partita(0.5)])["Formazioni ufficiali"][0], "att")
        self.assertEqual(self.fonti(partite=[self.partita(0.5, ufficiale=True)])["Formazioni ufficiali"][0], "ok")

    def test_errore_di_lettura_non_diventa_non_ancora_pubblicato(self):
        f = self.fonti(cercate=2, problemi_formazioni={"Sky non risponde"})["Formazioni ufficiali"]
        self.assertEqual(f[0], "att")
        self.assertIn("Sky non risponde", f[1])
        self.assertNotIn("non hanno ancora pubblicato", f[1])

    def test_quote_dal_file_del_pc(self):
        nota = "Quote DAZN Bet scaricate dal PC il 01/11 alle 11:30."
        self.assertEqual(self.fonti(nota_quote=nota)["DAZN Bet"][0], "ok")           # fresche: online non è un problema
        f = self.fonti(nota_quote=nota, quote_ora=self.ORA - timedelta(hours=5))["DAZN Bet"]
        self.assertEqual(f[0], "att")

    def test_quote_non_pubblicate(self):
        f = self.fonti(errore_pubblica="git push: rifiutato")["DAZN Bet"]
        self.assertEqual(f[0], "att")
        self.assertIn("rifiutato", f[1])

    def test_gialli_diversi_e_arbitri_giocate(self):
        f = self.fonti(gialli_diversi=["lazio-cagliari"], senza_arbitro_espn=50, senza_arbitro=3)
        self.assertIn("lazio-cagliari", f["Controllo gialli ESPN / football-data"][1])
        self.assertEqual(f["Arbitri delle partite giocate"][0], "att")
        self.assertEqual(self.fonti(senza_arbitro_espn=50)["Arbitri delle partite giocate"][0], "ok")


class QuoteDazn(unittest.TestCase):
    def test_una_riga_va_a_un_solo_giocatore(self):
        # Ricardo e Filipe Bordon: stessa riga DAZN, prendeva la stessa quota anche l'altro
        gioc = [{"nome": "Ricardo"}, {"nome": "Filipe Bordon"}]
        daznbet.associa([(["bordon", "filipe", "ricardo"], "x", 4.0)], "x", gioc)
        self.assertEqual([p["quota_book"] for p in gioc], [None, None])

    def test_chi_ha_il_nome_intero_vince_su_chi_ha_solo_il_cognome(self):
        gioc = [{"nome": "Amir Rrahmani"}, {"nome": "Luca Rrahmani"}]
        daznbet.associa([(["rrahmani", "amir"], "x", 4.0)], "x", gioc)
        self.assertEqual([p["quota_book"] for p in gioc], [4.0, None])

    def test_formato_cambiato_non_ferma_tutto(self):
        with mock.patch.object(daznbet, "scarica_quote", side_effect=KeyError("avs")), \
                mock.patch.object(daznbet, "da_file", return_value=({}, None)):
            quote, nota, quando = daznbet.carica()
        self.assertEqual((quote, quando), ({}, None))
        self.assertIn("non ha risposto", nota)


class OmonimiSky(unittest.TestCase):
    ROSA = [{"id": "1", "nome": "Ousmane Diallo", "ruolo_espn": "CM"}, {"id": "2", "nome": "Djibril Diallo", "ruolo_espn": "CM"}]

    def test_due_omonimi_nessuno(self):
        self.assertIsNone(sky._trova("Diallo", self.ROSA, set()))

    def test_con_l_iniziale_si_distinguono(self):
        self.assertEqual(sky._trova("Diallo D.", self.ROSA, set())["id"], "2")

    def test_l_alias_non_decide_fra_omonimi(self):
        altri = ["Rossi", "Bianchi", "Verdi", "Neri", "Gallo", "Conti", "Marino", "Greco", "Bruno", "Costa"]
        rosa = self.ROSA + [{"id": n, "nome": "Tizio " + n, "ruolo_espn": "CM"} for n in altri]
        ev = {"casa": "x", "trasf": "y", "id_casa": "1", "id_trasf": "2"}
        tradotti = {"home": {"diallo": "ousmane diallo"}, "away": {}}
        with mock.patch.object(sky, "_rosa", return_value=rosa):
            self.assertIsNone(sky.da_nomi(ev, {}, [(None, ["Diallo"] + altri), (None, ["Diallo D."] + altri)], tradotti))
            forma = sky.da_nomi(ev, {}, [(None, ["Diallo O."] + altri), (None, ["Diallo D."] + altri)], tradotti)
        self.assertEqual(forma["home"]["giocatori"][0]["id"], "1")
        self.assertEqual(forma["away"]["giocatori"][0]["id"], "2")

    def test_stessa_chiave_nella_pagina_non_si_traduce(self):
        d = {"titolari": {"home": [(1, "djibril diallo", "Diallo D."), (2, "ousmane diallo", "Diallo O.")], "away": []}, "riserve": {"home": [], "away": []}}
        self.assertIsNone(sky.alias(d)["home"]["diallo"])

    def test_il_ruolo_decide_ancora_per_il_portiere(self):
        rosa = [{"id": "1", "nome": "Luigi Terracciano", "ruolo_espn": "G"}, {"id": "2", "nome": "Pietro Terracciano", "ruolo_espn": "CM"}]
        self.assertEqual(sky._trova("Terracciano", rosa, set(), portiere=True)["id"], "1")


class StagioneKickest(unittest.TestCase):
    def test_la_stagione_in_corso_di_kickest_non_si_conta_due_volte(self):
        riga = dict(id="k1", nome_completo="mario rossi", squadra="roma", ruolo="C", minuti=900, presenze=10, titolare=10,
                    gialli=2, falli=20, contrasti=10)
        kick = pd.DataFrame([dict(riga, stagione=2025), dict(riga, stagione=2026)])
        profili = calcoli.ProfiliGiocatori(kick, None, {}, 2026, Presenza())
        self.assertEqual(list(profili.storia["k1"]["stagione"]), [2025])


class CorrezioniEspn(unittest.TestCase):
    """ESPN corregge i cartellini dopo la partita: una copia salvata subito si rilegge una volta, dopo 24 ore."""

    def prova(self, ore_salvato, ore_ora):
        inizio = datetime(2026, 10, 25, 17, 0)
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "p.json"
            f.write_text("{}", encoding="utf-8")
            salvato = (inizio + timedelta(hours=ore_salvato)).replace(tzinfo=timezone.utc).timestamp()
            os.utime(f, (salvato, salvato))
            js = {"header": {"competitions": [{"date": "2026-10-25T17:00Z"}]}}
            return espn._da_rileggere(js, f, inizio + timedelta(hours=ore_ora))

    def test_salvata_subito_dopo_un_giorno_si_rilegge(self):
        self.assertTrue(self.prova(3, 30))

    def test_prima_di_un_giorno_si_aspetta(self):
        self.assertFalse(self.prova(3, 10))

    def test_salvata_tardi_e_definitiva(self):
        self.assertFalse(self.prova(100, 200))

    def test_senza_data_resta_com_e(self):
        self.assertFalse(espn._da_rileggere({}, Path("non_serve.json")))


class SosFantaNuovoFormato(unittest.TestCase):
    """6/11/2026: articolo in /squadra/..., con «Abakwah» per Abankwah; le ufficiali c'erano ma la pagina non le prendeva."""
    EV = {"casa": "venezia", "trasf": "udinese", "id_casa": "1", "id_trasf": "2"}
    ARTICOLO = "https://www.sosfanta.com/squadra/udinese/venezia-udinese-formazioni-ufficiali-fantacalcio/"

    def test_link_dagli_elenchi(self):
        with mock.patch.object(articoli, "scarica", return_value=mock.Mock(text='<a href="%s">x</a>' % self.ARTICOLO)):
            self.assertEqual(sosfanta._link(self.EV), self.ARTICOLO)

    def test_qualunque_percorso_va_bene(self):
        # SosFanta cambia spesso: conta il nome dell'articolo, non dove sta
        for url in ("https://www.sosfanta.com/news/formazioni-ufficiali-venezia-udinese-zaniolo/",
                    "https://www.sosfanta.com/2027/nuova-sezione/venezia-e-udinese-le-formazioni-ufficiali/",
                    "https://www.sosfanta.com/x/venezia-udinese-ufficiali"):
            with mock.patch.object(articoli, "scarica", return_value=mock.Mock(text=url + '"')):
                self.assertEqual(sosfanta._link(self.EV), url, url)

    def test_si_trova_con_la_ricerca_del_sito(self):
        def finta(url, **_):
            return mock.Mock(text=self.ARTICOLO if "?s=formazioni+ufficiali+venezia+udinese" in url else "niente")
        with mock.patch.object(articoli, "scarica", side_effect=finta):
            self.assertEqual(sosfanta._link(self.EV), self.ARTICOLO)

    def test_altre_partite_e_probabili_non_vanno_bene(self):
        for url in ("https://www.sosfanta.com/squadra/udinese/venezia-roma-formazioni-ufficiali-fantacalcio/",
                    "https://www.sosfanta.com/squadra/udinese/udinese-venezia-formazioni-ufficiali-fantacalcio/",     # il ritorno
                    "https://www.sosfanta.com/news/venezia-udinese-probabili-formazioni-ufficiali/x-y/"):
            with mock.patch.object(articoli, "scarica", return_value=mock.Mock(text=url)):
                self.assertIsNone(sosfanta._link(self.EV), url)

    def test_articolo_di_un_altro_giorno_si_scarta(self):
        inizio = datetime(2026, 11, 6, 20, 45)
        self.assertTrue(articoli.del_giorno("", "marco astori 6 novembre - 19:35", inizio))
        self.assertTrue(articoli.del_giorno('"datePublished":"2026-11-06T19:35"', "", inizio))
        self.assertFalse(articoli.del_giorno('"datePublished":"2025-03-02"', "2 marzo", inizio))

    def test_refuso_di_una_lettera_solo_se_il_giocatore_e_uno(self):
        rosa = [{"id": "1", "nome": "James Abankwah", "ruolo_espn": "CD"}, {"id": "2", "nome": "Matteo Palma", "ruolo_espn": "CD"}]
        self.assertEqual(sky._trova("Abakwah", rosa, set())["id"], "1")
        doppio = rosa + [{"id": "3", "nome": "Luca Abakwahh", "ruolo_espn": "CD"}]
        self.assertIsNone(sky._trova("Abakwah", doppio, set()))
        self.assertIsNone(sky._trova("Palmi", [{"id": "2", "nome": "Matteo Palma"}, {"id": "4", "nome": "Ugo Palmo"}], set()))
        self.assertIsNone(sky._trova("Ross", [{"id": "5", "nome": "Mario Rossi"}], set()))   # troppo corto per fidarsi


class LetturaArticoli(unittest.TestCase):
    """Testi veri del 6/11/2026: le formazioni si riconoscono dal contenuto, con qualunque titolo intorno."""
    FANTA = ("Venezia-Udinese, le formazioni ufficiali VENEZIA (3-5-2) : Stankovic; Halhal, Moreno, Juan Jesus; Hainaut, Kike Pérez, Sohm, Basic, "
             "Mazzocchi; Yeboah, Adams. Allenatore: Davide Nicola UDINESE (3-5-2) : Okoye; Abankwah, Palma, Solet; Vojvoda, Piotrowski, Karlström, "
             "Kamara; Zaniolo, Ekkelenkamp; Davis. Allenatore: Paolo Zanetti")
    SOS = ("LE FORMAZIONI UFFICIALI: VENEZIA - Stankovic; Halhal, Moreno, Juan Jesus; Hainaut, Perez, Sohm, Basic, Mazzocchi; Adams, Yeboah. "
           "UDINESE - Okoye; Abakwah, Palma, Solet; Vojvoda, Piotrowski, Karlstrom, Kamara; Zaniolo, Ekkelenkamp; Davis. © RIPRODUZIONE RISERVATA")
    DIMARZIO = ("Di seguito le scelte VENEZIA (3-5-2): Stankovic; Halhal, Moreno,Juan Jesus; Hainaut, Kike Perez, Basic, Sohm, Mazzocchi; Yeboah, Adams. "
                "All . Nicola A disposizione: Montipò, Schingtienne, Haps, Busio, Rrhamani, Fanne, Correia, Bella Kotchap, Sagrado, Helgason, Lauberbach, Dagasso. "
                "UDINESE (3-4-2-1): Okoye; Abankwah, Palma, Solet; Vojvoda, Piotrowski, Karlstrom, Kamara; Zaniolo, Ekkelenkamp; Davis.")

    def test_tre_siti_tre_formati(self):
        for testo in (self.FANTA, self.SOS, self.DIMARZIO):
            trovati = articoli.blocchi(testo)
            self.assertEqual([len(b) for b in trovati], [11, 11], testo[:30])
            self.assertEqual(trovati[0][0], "Stankovic")
            self.assertEqual(trovati[1][0], "Okoye")
            self.assertEqual(trovati[1][-1], "Davis")

    def test_un_titolo_nuovo_non_cambia_niente(self):
        self.assertEqual(articoli.blocchi(self.SOS.replace("LE FORMAZIONI UFFICIALI:", "ECCO GLI UNDICI IN CAMPO:")), articoli.blocchi(self.SOS))

    def test_solo_elenchi_non_sono_formazioni(self):
        self.assertEqual(articoli.blocchi("A disposizione: Montipò, Schingtienne, Haps, Busio, Rrhamani, Fanne, Correia, Sagrado, Helgason, Lauberbach, Dagasso."), [])

    def test_fantacalcio_trova_e_legge_l_articolo(self):
        url = "/news/calcio-italia/06_11_2026/venezia-udinese-le-formazioni-ufficiali-500381"
        rosa = [{"id": n, "nome": n, "ruolo_espn": "G" if n in ("Stankovic", "Okoye") else "CM"} for n in
                ("Stankovic Halhal Moreno Juan_Jesus Hainaut Kike_Perez Sohm Basic Mazzocchi Yeboah Adams Okoye Abankwah Palma Solet Vojvoda "
                 "Piotrowski Karlstrom Kamara Zaniolo Ekkelenkamp Davis").replace("_", " ").replace("Juan Jesus", "Juan_Jesus").replace("Kike Perez", "Kike_Perez").split()]
        for g in rosa:
            g["nome"] = g["nome"].replace("_", " ")
        ev = {"casa": "venezia", "trasf": "udinese", "id_casa": "1", "id_trasf": "2", "inizio": datetime(2026, 11, 6, 20, 45)}

        def finta(u, **_):
            return mock.Mock(text=('<a href="%s">x</a>' % url) if "formazioni-ufficiali" not in u else self.FANTA + " 6 novembre")
        with mock.patch.object(articoli, "scarica", side_effect=finta), mock.patch.object(sky, "_rosa", return_value=rosa):
            forma = fantacalcio.ufficiali(ev, {}, None)
        self.assertEqual(sum(g["titolare"] for g in forma["home"]["giocatori"]), 11)
        self.assertEqual([g["nome"] for g in forma["away"]["giocatori"] if g["titolare"]][0], "Okoye")

    def test_articolo_vecchio_o_senza_formazioni_non_vale(self):
        ev = {"casa": "venezia", "trasf": "udinese", "inizio": datetime(2026, 11, 6, 20, 45)}
        with mock.patch.object(articoli, "scarica", return_value=mock.Mock(text=self.FANTA + " 2 marzo 2025")):
            self.assertIsNone(articoli.leggi(ev, {}, None, ["u"], "X"))
        with mock.patch.object(articoli, "scarica", return_value=mock.Mock(text="niente 6 novembre")):
            self.assertIsNone(articoli.leggi(ev, {}, None, ["u"], "X"))
        self.assertIn("articolo di X senza le due formazioni (formato cambiato?)", sky.problemi)
        sky.problemi.clear()


class TerzaFonteOnline(unittest.TestCase):
    def test_di_marzio_con_il_suo_articolo(self):
        url = "/news-calcio/venezia-udinese-formazioni-ufficiali-11a-giornata-serie-a-news-499228"
        with mock.patch.object(articoli, "scarica", return_value=mock.Mock(text='<a href="%s">x</a>' % url)):
            self.assertEqual(articoli.trova({"casa": "venezia", "trasf": "udinese"}, dimarzio.DOMINIO, dimarzio.ELENCHI, None, "Di Marzio"),
                             ["https://www.gianlucadimarzio.com" + url])

    def test_su_github_non_si_usa_fantacalcio(self):
        codice = Path(aggiorna.__file__).read_text(encoding="utf-8")
        self.assertIn('("Di Marzio", dimarzio.ufficiali) if os.environ.get("GITHUB_ACTIONS")', codice)


class UfficialiDelPc(unittest.TestCase):
    def test_si_salvano_e_si_tolgono_le_partite_finite(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(articoli, "SALVATE", Path(t) / "f.json"):
            self.assertTrue(articoli.salva({"1": {"home": {}}}, [{"id": "1"}, {"id": "2"}]))
            self.assertFalse(articoli.salva({"1": {"home": {}}}, [{"id": "1"}]))        # uguale: niente da pubblicare
            self.assertTrue(articoli.salva({"2": {"away": {}}}, [{"id": "2"}]))         # la 1 è finita
            self.assertEqual(articoli.salvate(), {"2": {"away": {}}})

    def test_file_mancante(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(articoli, "SALVATE", Path(t) / "no.json"):
            self.assertEqual(articoli.salvate(), {})


class AvvisoUfficiali(unittest.TestCase):
    def test_solo_per_le_partite_senza_ufficiali(self):
        ev = {"casa": "roma", "trasf": "genoa", "inizio": FISCHIO}
        html = pagina.avvisi_ufficiali([{"ev": ev, "ufficiale": False}, {"ev": dict(ev, casa="lazio"), "ufficiale": True}])
        self.assertEqual(html.count("no-uff"), 1)
        self.assertIn("Roma", html)
        self.assertIn('data-fischio="2026-11-07T18:00+01:00"', html)


class FileSicuri(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.dir = Path(t.name)

    def test_se_la_scrittura_fallisce_resta_il_file_vecchio(self):
        f = self.dir / "a.json"
        utils.scrivi_json(f, {"v": 1})
        with mock.patch("utils.os.replace", side_effect=PermissionError), mock.patch("utils.time.sleep"):
            with self.assertRaises(PermissionError):
                utils.scrivi_json(f, {"v": 2})
        self.assertEqual(utils.leggi_json(f), {"v": 1})
        self.assertEqual([x.name for x in self.dir.iterdir()], ["a.json"])            # nessun temporaneo lasciato in giro

    def test_file_rovinato_o_mancante(self):
        f = self.dir / "b.json"
        f.write_text('{"tronc', encoding="utf-8")
        self.assertEqual(utils.leggi_json_o(f, {}), {})
        self.assertIsNone(utils.leggi_json_o(self.dir / "non_c_e.json"))

    def test_calendario_rovinato_si_riscarica(self):
        (self.dir / "espn").mkdir()
        (self.dir / "espn" / "calendario_20261107.json").write_text('{"events": [', encoding="utf-8")
        with mock.patch.object(espn, "CACHE", self.dir), mock.patch.object(espn, "scarica_json", return_value={"events": []}) as rete:
            self.assertEqual(espn.partite_del_giorno(date(2026, 11, 7)), [])
        self.assertEqual(rete.call_count, 1)
        self.assertEqual(json.loads((self.dir / "espn" / "calendario_20261107.json").read_text(encoding="utf-8")), {"events": []})

    def test_due_avvia_non_possono_aprire_la_stessa_porta(self):
        primo = server.ServerUnico(("127.0.0.1", 0), server.Gestore)
        self.addCleanup(primo.server_close)
        with self.assertRaises(OSError):
            server.ServerUnico(("127.0.0.1", primo.server_address[1]), server.Gestore)


if __name__ == "__main__":
    unittest.main()
