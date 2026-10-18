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
from fonti import (aia, api_football, arbitri_espn, daznbet, espn, espn_dettaglio, football_data,  # noqa: E402
                   kickest, sky, sosfanta, transfermarkt)

GIORNI_AVANTI = 8  # quanti giorni di calendario mostrare


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
    giorni_giocati = set(fd[fd["stagione"] == anno]["data"].dt.date) | {oggi - timedelta(1), oggi}
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
        stato.append("Transfermarkt non ha risposto: per i giocatori senza storico Kickest uso la media del ruolo.")

    print("5/5 Calcoli e pagina")
    ok, diversi = calcoli.controllo_espn(fd, finite, anno)
    print("    controllo gialli ESPN vs football-data: {} uguali, {} diversi".format(ok, diversi))
    fd, aggiunte = calcoli.integra_con_espn(fd, finite, anno)
    if aggiunte:
        stato.append("{} partite recenti non ancora nel file di football-data sono state ricavate da ESPN."
                     .format(aggiunte))
    df, aia_risolte, _ = calcoli.prepara_partite(fd, arbitri_api, designazioni)
    tabelle = calcoli.costruisci_tabelle(df, anno)
    df = calcoli.aggiungi_tipo(df, tabelle, anno)
    lungo = calcoli.formato_lungo(df)
    giocatori_espn, ultima_formazione = calcoli.aggrega_espn(finite)
    poisson, stato_modello = calcoli.prepara_modello(df)
    modello_presenza = presenza.ModelloPresenza(dettagli, stagione_corrente=anno)
    quote_giocatori, nota_quote, quote_ora = daznbet.carica()
    if nota_quote:
        stato.append(nota_quote)
    elif quote_giocatori and not os.environ.get("GITHUB_ACTIONS"):
        # scaricate ora dal PC: le pubblico, così le legge anche la pagina online (GitHub non raggiunge DAZN Bet)
        try:
            print("    " + pubblica_quote.pubblica(quote_giocatori))
        except RuntimeError as e:
            print("    quote DAZN Bet non pubblicate online: {}".format(e))
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
    for ev in prossime:
        forma = espn.formazioni(ev["id"], ev["stato"])
        e_uff = espn.ufficiale(forma)
        if not e_uff and ev["inizio"] - config.adesso() < timedelta(hours=5):
            # ESPN è in ritardo: Sky e SosFanta pubblicano le ufficiali circa un'ora prima del fischio d'inizio
            for fonte, cerca in (("Sky", lambda: sky.ufficiali(ev, anno, ultima_formazione, giornata_sky)),
                                 ("SosFanta", lambda: sosfanta.ufficiali(ev, ultima_formazione))):
                forma_ext = cerca()
                if forma_ext:
                    forma, e_uff = forma_ext, True
                    print("    {} - {}: formazioni ufficiali da {}".format(ev["casa"], ev["trasf"], fonte))
                    break
        if not e_uff:  # formazione non ancora uscita: mostro l'ultima schierata, segnalata come "probabile"
            forma = {}
            for lato, sq in (("home", ev["casa"]), ("away", ev["trasf"])):
                if sq in ultima_formazione:
                    forma[lato] = {"squadra": sq, "formazione": None, "giocatori": ultima_formazione[sq]}
        partite.append(calcoli.analizza_partita(ev, forma, e_uff, ctx))

    squadre_stagione = sorted(set(df[df["stagione"] == anno]["casa"]) | set(df[df["stagione"] == anno]["trasf"]))
    sezioni = {
        "arbitri": calcoli.tabella_arbitri(df, anno),
        "squadre": calcoli.tabella_squadre(lungo, anno, squadre_stagione),
        "tipi": calcoli.tabella_tipi(df),
        "lega": {"gialli": float(df.tail(380)["g_tot"].mean()), "partite": len(df),
                 "rapporto_var": ctx["rapporto_var"],
                 "over": {s: calcoli.frequenza_oltre(df.tail(380)["g_tot"], s) for s in calcoli.SOGLIE},
                 "arbitri_noti": int(df["arbitro"].notna().sum())},
        "stato": stato,
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
