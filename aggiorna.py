#!/usr/bin/env python3
"""Aggiorna i dati e rigenera index.html.

Uso:   python3 aggiorna.py            (aggiorna tutto e rigenera la pagina)
       python3 aggiorna.py --apri     (poi apre la pagina nel browser)
Da lanciare quando escono le formazioni (circa 1 ora prima di ogni partita): ogni esecuzione
scarica solo le novità, quindi è veloce.
"""
import sys
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore")

import calcoli  # noqa: E402
import config  # noqa: E402
import pagina  # noqa: E402
from fonti import aia, api_football, espn, football_data, kickest  # noqa: E402

GIORNI_AVANTI = 8  # quanti giorni di calendario mostrare


def main():
    oggi = config.adesso().date()
    anno = config.STAGIONE_CORRENTE
    stato = []

    print("1/5 Risultati e cartellini di squadra (football-data.co.uk)")
    fd = football_data.carica()

    print("2/5 Arbitri (API-Football per il 2023-2024, AIA per le designazioni)")
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
    var = df["g_tot"].var() / df["g_tot"].mean()
    ctx = {
        "anno": anno, "df": df, "lungo": lungo, "tabelle": tabelle, "designazioni": designazioni,
        "aia_risolte": aia_risolte, "rapporto_var": max(1.0, min(2.0, var)),
        "profili": calcoli.ProfiliGiocatori(kick, giocatori_espn, anno),
    }

    partite = []
    for ev in prossime:
        forma = espn.formazioni(ev["id"], ev["stato"])
        e_uff = espn.ufficiale(forma)
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
        "lega": {"gialli": float(df["g_tot"].mean()), "partite": len(df),
                 "rapporto_var": ctx["rapporto_var"],
                 "over": {s: calcoli.frequenza_oltre(df["g_tot"], s) for s in calcoli.SOGLIE},
                 "arbitri_noti": int(df["arbitro"].notna().sum())},
        "stato": stato,
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
