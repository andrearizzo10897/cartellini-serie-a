#!/usr/bin/env python3
"""Aggiorna i dati e rigenera index.html.

Uso:   python3 aggiorna.py            (aggiorna tutto e rigenera la pagina)
       python3 aggiorna.py --apri     (poi apre la pagina nel browser)
Da lanciare quando escono le formazioni (circa 1 ora prima di ogni partita): ogni esecuzione
scarica solo le novità, quindi è veloce.
"""
import os
import sys
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

import calcoli  # noqa: E402
import presenza  # noqa: E402
import config  # noqa: E402
import pagina  # noqa: E402
import pubblica_quote  # noqa: E402
from fonti import (aia, api_football, arbitri_espn, articoli, daznbet, dimarzio, espn, espn_dettaglio, fantacalcio, football_data,  # noqa: E402
                   kickest, sky, sosfanta, transfermarkt)

GIORNI_AVANTI = 8  # quanti giorni di calendario mostrare


def _partite(n):
    return "{} partit{}".format(n, "a" if n == 1 else "e")


def riepilogo_fonti(anno, ultimo_fd, oggi, aggiunte, finite, prossime, mancanti, kickest_corrente, n_tm,
                    quote_giocatori, nota_quote, quote_ora, n_uff, cercate, partite, ora=None, copie_calendario=(),
                    problemi_formazioni=(), gialli_diversi=(), senza_arbitro_espn=0, senza_arbitro=0, errore_pubblica=None):
    """[(sito, livello, testo)] per il riquadro "Fonti di questo aggiornamento": livello ok / att (attenzione) / no.

    «ok» vuol dire che il dato serve così com'è: una fonte che risponde ma lascia un buco dove serve non è «ok». I «no» compaiono
    anche in cima alla scheda Partite."""
    ora = ora or config.adesso()
    fonti = []
    # football-data ritarda di qualche giorno e le partite mancanti le ricavo da ESPN: la riga serve solo se è davvero ferma
    ritardo = (oggi - ultimo_fd).days
    if ritardo > 14:
        fonti.append(("football-data.co.uk", "att", "fermo all'ultimo dato del {:%d/%m}: il modello usa soprattutto ESPN, senza "
                                                   "le quote storiche".format(ultimo_fd)))
    con_quote = sum(1 for e in prossime if e.get("quote"))
    non_ancora = " ({} non ancora in football-data)".format(aggiunte) if aggiunte else ""
    testo = "{} finite lette{}, {} in programma ({} con le quote 1X2)".format(_partite(len(finite)), non_ancora, len(prossime), con_quote)
    if copie_calendario:
        testo = "ESPN non ha risposto: il calendario del {} è una copia salvata, partite e orari possono essere vecchi. {}".format(
            ", ".join("{:%d/%m}".format(g) for g in sorted(set(copie_calendario))), testo)
    fonti.append(("ESPN", "ok" if finite and not copie_calendario else "no", testo))
    if gialli_diversi:
        fonti.append(("Controllo gialli ESPN / football-data", "att", "{} con un numero di gialli diverso: {}. Fa fede il tabellino della Lega Serie A.".format(
            _partite(len(gialli_diversi)), ", ".join(gialli_diversi))))
    totale = sum(n_uff.values())
    testo = "ufficiali per {} su {} ({})".format(_partite(totale), len(prossime), ", ".join("{} {}".format(k, v) for k, v in n_uff.items()))
    if problemi_formazioni:
        testo += "; da controllare: " + ", ".join(sorted(problemi_formazioni))
    elif cercate and not any(v for k, v in n_uff.items() if k != "ESPN"):
        testo += "; per {} vicin{} al calcio d'inizio le altre fonti non hanno ancora pubblicato".format(
            _partite(cercate), "a" if cercate == 1 else "e")
    # le ufficiali escono circa un'ora prima: a 45 minuti dal fischio dovrebbero esserci
    in_ritardo = [p for p in partite if "ev" in p and not p.get("ufficiale")
                  and timedelta(0) < p["ev"]["inizio"] - ora < timedelta(minutes=45)]
    fonti.append(("Formazioni ufficiali", "att" if in_ritardo or problemi_formazioni else "ok", testo))
    fresche = quote_ora is not None and (ora - quote_ora).total_seconds() <= config.QUOTE_MAX_ORE * 3600
    if quote_giocatori and fresche and not errore_pubblica:
        fonti.append(("DAZN Bet", "ok", "quote «ammonito» per {}, scaricate alle {:%H:%M}".format(
            _partite(len(quote_giocatori)), quote_ora)))
    elif errore_pubblica:
        fonti.append(("DAZN Bet", "att", "scaricate ma non pubblicate online: {}".format(errore_pubblica)))
    elif quote_giocatori or nota_quote:
        fonti.append(("DAZN Bet", "att" if quote_giocatori else "no", nota_quote or "quote vecchie: il valore atteso non è mostrato"))
    else:
        fonti.append(("DAZN Bet", "no", "nessuna quota ricevuta"))
    fonti.append(("Transfermarkt (storico principale)", "ok" if n_tm else "att",
                  "{} giocatori con storico dal 2022/23".format(n_tm) if n_tm else "non ha risposto: uso Kickest"))
    if mancanti:
        fonti.append(("Kickest (riserva, falli e contrasti)", "att", "non ha risposto per {}".format(", ".join(
            "{}/{}".format(s, str(s + 1)[2:]) for s in mancanti))))
    else:
        fonti.append(("Kickest (riserva, falli e contrasti)", "ok", "stagioni passate caricate" + ("" if kickest_corrente else
                      "; il {}/{} non è ancora pubblicato, per quella in corso uso ESPN".format(anno, str(anno + 1)[2:]))))
    con_arbitro = sum(1 for p in partite if p["arbitro"])
    testo = "designati per {} su {}".format(_partite(con_arbitro), len(partite))
    # l'AIA pubblica il giorno prima della giornata: a meno di 24 ore l'arbitro deve esserci (il 1/11 ne erano spariti 5 su 10 in silenzio)
    senza = [p["ev"] for p in partite if "ev" in p and not p["arbitro"] and p["ev"]["inizio"] - ora < timedelta(hours=24)]
    if senza:
        testo = "manca l'arbitro di {}, che si gioca entro 24 ore: la stima non ne tiene conto. {}".format(
            ", ".join("{}-{}".format(e["casa"], e["trasf"]) for e in senza), testo)
    fonti.append(("Arbitri (AIA)", "no" if senza else "ok", testo))
    if senza_arbitro_espn or senza_arbitro:
        fonti.append(("Arbitri delle partite giocate", "att" if senza_arbitro else "ok",
                      "ESPN non indica l'arbitro per {}: lo storico di quest'anno dipende dall'archivio AIA{}".format(
                          _partite(senza_arbitro_espn), "; {} senza arbitro".format(_partite(senza_arbitro)) if senza_arbitro else "")))
    return fonti


def main():
    oggi = config.adesso().date()
    anno = config.STAGIONE_CORRENTE
    stato = []

    print("1/5 Risultati e cartellini di squadra (football-data.co.uk)")
    fd = football_data.carica()

    print("2/5 Arbitri (API-Football per il 2023-2024, ESPN dal 2025-2026, AIA per le designazioni)")
    arbitri_api = api_football.carica(config.STAGIONI_STORICO)
    archivio = aia.aggiorna()
    designazioni = aia.designazioni(archivio)

    print("3/5 Giocatori (Kickest, stagioni passate)")
    kick = kickest.carica()
    mancanti = [s for s in range(max(2023, anno - 3), anno) if not len(kick[kick["stagione"] == s])]
    if mancanti:
        stato.append("Kickest non ha risposto per le stagioni: {}. Riproverò al prossimo aggiornamento."
                     .format(", ".join("{}/{}".format(s, str(s + 1)[2:]) for s in mancanti)))
    if not len(kick[kick["stagione"] == anno]):
        stato.append("Kickest non ha ancora pubblicato la stagione {}/{}: per quella in corso uso ESPN."
                     .format(anno, str(anno + 1)[2:]))

    print("4/5 Partite e formazioni (ESPN)")
    # football-data arriva con qualche giorno di ritardo: da ESPN leggo anche tutti i giorni dopo il suo ultimo dato
    date_fd = set(fd[fd["stagione"] == anno]["data"].dt.date)
    ultimo_fd = max(date_fd, default=oggi - timedelta(2))
    giorni_giocati = date_fd | {ultimo_fd + timedelta(k) for k in range(1, max((oggi - ultimo_fd).days, 1) + 1)} \
        | {oggi - timedelta(1), oggi}
    finite, viste = [], set()
    for g in sorted(giorni_giocati):
        for ev in espn.partite_del_giorno(g):
            if ev["stato"] == "post" and ev["id"] not in viste:
                viste.add(ev["id"])
                finite.append((ev, espn.formazioni(ev["id"], "post")))
    prossime = []
    for k in range(GIORNI_AVANTI):
        for ev in espn.partite_del_giorno(oggi + timedelta(k)):
            if ev["stato"] != "post" and ev["id"] not in {p["id"] for p in prossime}:
                prossime.append(ev)
    prossime.sort(key=lambda e: e["inizio"])

    # arbitri delle stagioni che API-Football non copre: dal dettaglio delle partite ESPN
    arbitri_api = pd.concat([arbitri_api, arbitri_espn.carica(fd, finite, anno, set(arbitri_api["arbitro"]))], ignore_index=True)
    arbitri_api = arbitri_api.drop_duplicates(["stagione", "casa", "trasf"], keep="first")

    print("    dettaglio partite ESPN (minuto dei cambi e dei gialli) e Transfermarkt")
    ids = set(arbitri_espn.id_partite(anno - 1)) | {ev["id"] for ev, _ in finite}
    dettagli = espn_dettaglio.carica(sorted(ids))
    tm = transfermarkt.carica(range(max(2022, anno - 4), anno))
    if not len(tm):
        stato.append("Transfermarkt non ha risposto (e non c'è la copia salvata): per lo storico dei giocatori uso solo Kickest.")

    print("5/5 Calcoli e pagina")
    ok, diversi = calcoli.controllo_espn(fd, finite, anno, dettagli)
    print("    controllo gialli ESPN vs football-data: {} uguali, {} diversi".format(ok, len(diversi)))
    fd, aggiunte = calcoli.integra_con_espn(fd, finite, anno)
    if aggiunte:
        stato.append("{} partite recenti non ancora nel file di football-data sono state ricavate da ESPN."
                     .format(aggiunte))
    df, aia_risolte, _ = calcoli.prepara_partite(fd, arbitri_api, designazioni)
    tabelle = calcoli.costruisci_tabelle(df, anno)
    df = calcoli.aggiungi_tipo(df, tabelle, anno)
    lungo = calcoli.formato_lungo(df)
    giocatori_espn, ultima_formazione = calcoli.aggrega_espn(finite)
    squalificati = calcoli.squalificati(finite)
    poisson, stato_modello = calcoli.prepara_modello(df)
    modello_presenza = presenza.ModelloPresenza(dettagli, stagione_corrente=anno)
    quote_giocatori, nota_quote, quote_ora = daznbet.carica()
    errore_pubblica = None
    ctx = {
        "quote_giocatori": quote_giocatori, "quote_ora": quote_ora,
        "anno": anno, "df": df, "lungo": lungo, "tabelle": tabelle, "designazioni": designazioni,
        "aia_risolte": aia_risolte, "poisson": poisson, "stato_modello": stato_modello,
        "rapporto_var": 1.0,  # i gialli totali seguono una Poisson (backtest: la dispersione extra non migliora)
        "presenza": modello_presenza,
        "profili": calcoli.ProfiliGiocatori(kick, tm, giocatori_espn, anno, modello_presenza),
    }

    partite = []
    giornata_sky = sky.giornata_corrente() if prossime else None
    # terza fonte: Fantacalcio dal PC, Di Marzio su GitHub
    terza, leggi_terza = ("Di Marzio", dimarzio.ufficiali) if os.environ.get("GITHUB_ACTIONS") else ("Fantacalcio", fantacalcio.ufficiali)
    n_uff, cercate = {"ESPN": 0, "Sky": 0, "SosFanta": 0, terza: 0, "dal PC": 0}, 0
    trovate, dal_pc = {}, articoli.salvate()
    gia_viste = set()
    for ev in prossime:
        ultima_ev, ctx["squalificati"] = calcoli.formazioni_per_partita(ev, ultima_formazione, squalificati, gia_viste)
        gia_viste |= {ev["casa"], ev["trasf"]}
        forma = espn_ev = espn.formazioni(ev["id"], ev["stato"])
        e_uff = espn.ufficiale(forma)
        n_uff["ESPN"] += bool(e_uff)
        if not e_uff and ev["inizio"] - config.adesso() < timedelta(hours=5):
            # ESPN è in ritardo: Sky e SosFanta pubblicano le ufficiali circa un'ora prima del fischio d'inizio
            cercate += 1
            dati_sky = sky.carica_pagina(ev, anno, giornata_sky)   # pagina "formazioni": nomi completi, anche dei soprannomi
            for fonte, cerca in (("Sky", lambda: sky.ufficiali(ev, anno, ultima_ev, giornata_sky, dati_sky)),
                                 ("SosFanta", lambda: sosfanta.ufficiali(ev, ultima_ev, sky.alias(dati_sky))),
                                 (terza, lambda: leggi_terza(ev, ultima_ev, sky.alias(dati_sky)))):
                forma_ext = cerca()
                if forma_ext:
                    forma, e_uff = forma_ext, True
                    n_uff[fonte] += 1
                    trovate[ev["id"]] = forma_ext
                    print("    {} - {}: formazioni ufficiali da {}".format(ev["casa"], ev["trasf"], fonte))
                    break
        if not e_uff and ev["id"] in dal_pc:   # le ha trovate il PC e pubblicate con le quote
            forma, e_uff = dal_pc[ev["id"]], True
            n_uff["dal PC"] += 1
        if not e_uff:  # formazione non ancora uscita: mostro l'ultima schierata, segnalata come "probabile"
            forma = {}
            for lato, sq in (("home", ev["casa"]), ("away", ev["trasf"])):
                vera = (espn_ev.get(lato) or {})
                if sum(1 for g in vera.get("giocatori", []) if g["titolare"]) == 11:
                    forma[lato] = vera   # ESPN a volte ha gli undici di una squadra sola: quelli sono già veri (il valore atteso resta nascosto)
                elif sq in ultima_ev:
                    forma[lato] = {"squadra": sq, "formazione": None, "giocatori": ultima_ev[sq]}
        partite.append(calcoli.analizza_partita(ev, forma, e_uff, ctx))

    articoli.salva(trovate, prossime)   # prima di pubblicare: partono insieme alle quote
    if nota_quote:
        stato.append(nota_quote)
    elif quote_giocatori and not os.environ.get("GITHUB_ACTIONS"):
        # scaricate ora dal PC: le pubblico, così le legge anche la pagina online (GitHub non raggiunge DAZN Bet)
        try:
            print("    " + pubblica_quote.pubblica(quote_giocatori))
        except (RuntimeError, OSError) as e:   # git che rifiuta, file bloccato: la pagina si genera lo stesso
            print("    quote DAZN Bet non pubblicate online: {}".format(e))
            errore_pubblica = str(e).splitlines()[0][:200]
            stato.append("Quote DAZN Bet scaricate ma non pubblicate online: la pagina online resta con quelle vecchie ({}).".format(errore_pubblica))

    fonti = riepilogo_fonti(
        anno=anno, ultimo_fd=ultimo_fd, oggi=oggi, aggiunte=aggiunte, finite=finite, prossime=prossime,
        mancanti=mancanti, kickest_corrente=bool(len(kick[kick["stagione"] == anno])), n_tm=len(tm),
        quote_giocatori=quote_giocatori, nota_quote=nota_quote, quote_ora=quote_ora,
        n_uff=n_uff, cercate=cercate, partite=partite, copie_calendario=espn.copie_usate, problemi_formazioni=sky.problemi,
        gialli_diversi=diversi, senza_arbitro_espn=arbitri_espn.senza_arbitro(anno),
        senza_arbitro=int(df[df["stagione"] == anno]["arbitro"].isna().sum()), errore_pubblica=errore_pubblica)
    squadre_stagione = sorted(set(df[df["stagione"] == anno]["casa"]) | set(df[df["stagione"] == anno]["trasf"]))
    sezioni = {
        "arbitri": calcoli.tabella_arbitri(df, anno),
        "squadre": calcoli.tabella_squadre(lungo, anno, squadre_stagione),
        "tipi": calcoli.tabella_tipi(df),
        "lega": {"gialli": float(df.tail(380)["g_tot"].mean()), "partite": len(df),
                 "rapporto_var": ctx["rapporto_var"],
                 "over": {s: calcoli.frequenza_oltre(df.tail(380)["g_tot"], s) for s in calcoli.SOGLIE},
                 "arbitri_noti": int(df["arbitro"].notna().sum()),
                 # media di gialli e numero di partite di ogni stagione: serve al testo «Livello della Serie A»
                 "per_stagione": {int(s): (float(g["g_tot"].mean()), len(g)) for s, g in df.groupby("stagione")}},
        "stato": stato,
        "fonti": fonti,
        "giornate": calcoli.cartellini_giornate(finite, prossime, dettagli),   # pagina «Giocatori»
        "tempo": modello_presenza.riepilogo(),
        "aggiornato": config.adesso(),
        "partite_giocate": len(finite),
    }
    pagina.genera(partite, sezioni, config.OUTPUT)
    print("Fatto: {}  ({} partite in programma)".format(config.OUTPUT, len(partite)))
    return 0


if __name__ == "__main__":
    codice = main()
    if "--apri" in sys.argv:
        import webbrowser
        webbrowser.open(config.OUTPUT.as_uri())  # funziona su Windows, Mac e Linux
    sys.exit(codice)
