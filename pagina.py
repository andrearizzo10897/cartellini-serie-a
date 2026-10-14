"""Genera index.html: una pagina sola, senza librerie esterne (funziona anche offline)."""
from html import escape

from utils import nome_squadra

GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
RUOLI = {"P": "Portiere", "D": "Difensore", "C": "Centrocampista", "A": "Attaccante"}

CSS = """
:root{color-scheme:dark;--bg:#121211;--surf:#1a1a19;--surf2:#232321;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#97968c;
--line:#33332f;--bar:#3987e5;--bar-bg:#24334a;--accent:#3987e5;--alto:#f2994a;--medio:#e2c044}
:root[data-theme="light"]{color-scheme:light;--bg:#f6f6f4;--surf:#fcfcfb;--surf2:#f0efec;--ink:#0b0b0b;--ink2:#52514e;
--ink3:#7c7b76;--line:#e2e1dc;--bar:#2a78d6;--bar-bg:#e3ebf7;--accent:#2a78d6;--alto:#c25e00;--medio:#9a7400}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
padding:0 16px}
.wrap{max-width:1180px;margin:0 auto;padding:20px 0 48px}
header{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline;justify-content:space-between;margin-bottom:14px}
h1{font-size:22px;margin:0}h2{font-size:17px;margin:22px 0 8px}h3{font-size:14px;margin:0}
.muted{color:var(--ink2)}.small{font-size:12px;color:var(--ink3)}
.note{background:var(--surf2);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:6px 0;color:var(--ink2);font-size:13px}
nav.tabs{display:flex;flex-wrap:wrap;gap:4px;border-bottom:1px solid var(--line);margin:14px 0}
nav.tabs button,.chip{font:inherit;color:var(--ink2);background:none;border:1px solid transparent;border-radius:8px 8px 0 0;
padding:8px 14px;cursor:pointer}
nav.tabs button[aria-selected=true]{color:var(--ink);border-color:var(--line);border-bottom-color:var(--bg);background:var(--surf);
font-weight:600;margin-bottom:-1px}
.partite{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 14px}
.chip{border:1px solid var(--line);border-radius:8px;background:var(--surf);padding:6px 10px;text-align:left;line-height:1.3}
.chip small{display:block;color:var(--ink3)}
.chip[aria-selected=true]{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.card{background:var(--surf);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:10px 0}
.kpi{background:var(--surf);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.kpi b{display:block;font-size:22px;line-height:1.2}.kpi span{color:var(--ink2);font-size:12px}
.badge{display:inline-block;border-radius:99px;padding:2px 9px;font-size:12px;border:1px solid var(--line);color:var(--ink2)}
.badge.ok{border-color:var(--accent);color:var(--accent);font-weight:600}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{font-weight:600;color:var(--ink2);font-size:12px;cursor:pointer;user-select:none;position:sticky;top:0;background:var(--surf)}
th[data-sort=asc]::after{content:" \\25B2";font-size:9px}th[data-sort=desc]::after{content:" \\25BC";font-size:9px}
tr.sep td{background:var(--surf2);color:var(--ink2);font-size:12px;font-weight:600;cursor:default}
.cols{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;align-items:start}
@media (min-width:1240px){.cols{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
.cols .card{margin-bottom:0}
.det{display:none}.det-on .det{display:table-cell}
.opzioni{display:flex;justify-content:flex-end;margin:0 0 8px;font-size:13px;color:var(--ink2)}
.opzioni label{cursor:pointer;display:flex;gap:6px;align-items:center}
.testata h2{margin:0 0 2px;font-size:20px}
.rischio{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:12px 0 4px}
.rischio .r{background:var(--surf2);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
.rischio .r b{display:block;font-size:20px;line-height:1.2}.rischio .r span{font-size:12px;color:var(--ink2)}
h3.titolo{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink3);margin:16px 0 0}
details.panchina{margin-top:10px;border-top:1px solid var(--line)}
details.panchina>summary{padding:10px 0 6px;font-weight:600;color:var(--ink)}
.bar.p-media i{background:var(--medio)}.bar.p-alta i{background:var(--alto)}
.barcell .p-media b{color:var(--medio)}.barcell .p-alta b{color:var(--alto)}
.barcell>span{display:flex;flex-direction:column;align-items:flex-end;line-height:1.2}
.q{font-size:11px;color:var(--ink3);font-weight:400}
details.partita{background:var(--surf);border:1px solid var(--line);border-radius:10px;margin-bottom:10px}
details.partita>summary{list-style:none;cursor:pointer;padding:12px 14px 12px 36px;display:block;position:relative}
details.partita>summary::-webkit-details-marker{display:none}
details.partita>summary::before{content:"\\25B8";color:var(--ink3);position:absolute;left:14px;top:13px;transition:transform .15s}
details.partita[open]>summary::before{transform:rotate(90deg)}
details.partita[open]>summary{border-bottom:1px solid var(--line)}
.s-riga1{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}
.s-squadre{font-size:16px;font-weight:700;color:var(--ink)}.s-quando{color:var(--ink2);font-size:13px}
.s-riga2{display:flex;flex-wrap:wrap;gap:4px 14px;margin:6px 0 0;font-size:13px;color:var(--ink2)}
.s-riga2 b{color:var(--ink)}.s-riga2 b.p-media{color:var(--medio)}.s-riga2 b.p-alta{color:var(--alto)}
.s-top{margin:4px 0 0;font-size:13px;color:var(--ink2)}.s-top b{color:var(--ink)}
details.partita>.corpo{padding:12px 14px 14px}
.riepilogo .riga{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:2px 0}
.riepilogo .riga span{color:var(--ink2)}.riepilogo .riga b{color:var(--ink)}
.riepilogo h3{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink3);margin:0 0 6px}
.barcell{display:flex;align-items:center;gap:8px;justify-content:flex-end;min-width:120px}
.bar{flex:1;max-width:90px;height:8px;border-radius:4px;background:var(--bar-bg);overflow:hidden}
.bar i{display:block;height:100%;background:var(--bar);border-radius:4px}
.alto b{color:var(--ink)}
td.nome{font-weight:500}.ruolo{color:var(--ink3);font-size:12px;margin-left:4px}
.tag{color:var(--ink3);font-size:11px;margin-left:4px}
details{margin:6px 0}summary{cursor:pointer;color:var(--ink2)}
.legenda{font-size:12px;color:var(--ink3);margin:6px 0 0}
.hid{display:none}
.agg{font:inherit;font-weight:600;color:#fff;background:var(--accent);border:0;border-radius:8px;padding:6px 14px;cursor:pointer}
.agg[disabled]{opacity:.6;cursor:wait}#msg{font-size:12px;color:var(--ink2);margin-left:6px}
.az{display:flex;align-items:center;flex-wrap:wrap;gap:6px}
html{-webkit-text-size-adjust:100%}
@media (max-width:640px){
body{padding:0 max(10px,env(safe-area-inset-left)) 0 max(10px,env(safe-area-inset-right));font-size:15px}
.wrap{padding:12px 0 40px}
h1{font-size:19px}h2{font-size:16px}
header{display:flex;flex-direction:column;align-items:stretch;gap:8px}
header .az{order:2}header .info{order:3}
.agg{flex:1;padding:12px 14px;font-size:15px}#msg{flex-basis:100%;margin:0}
.nm{display:none}
nav.tabs{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;margin:10px -10px;padding:0 10px}
nav.tabs::-webkit-scrollbar,.partite::-webkit-scrollbar{display:none}
nav.tabs button{flex:0 0 auto;white-space:nowrap;padding:12px 14px}
.partite{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;margin:6px -10px 12px;padding:0 10px 4px;scroll-snap-type:x proximity}
.chip{flex:0 0 auto;min-width:148px;scroll-snap-align:start;padding:8px 10px}
.kpis{grid-template-columns:1fr 1fr}.kpi:first-child{grid-column:1/-1}.kpi b{font-size:19px}
.card{padding:10px 10px}
th,td{padding:9px 6px}
.barcell{min-width:84px;gap:6px}.bar{max-width:44px}
.soglie td,.soglie th{padding:9px 4px}
.scroll table th:first-child,.scroll table td:first-child{position:sticky;left:0;z-index:1;background:var(--surf)}
.scroll table tr.sep td:first-child{background:var(--surf2)}
td.nome{white-space:normal;min-width:120px;max-width:170px}
.legenda{font-size:12px}
}
button.tema{font:inherit;color:var(--ink2);background:var(--surf);border:1px solid var(--line);border-radius:8px;padding:4px 10px;cursor:pointer}
"""

JS = """
(function(){
function $(s,r){return (r||document).querySelector(s)}function $$(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
function attiva(gruppo,id,attr){$$('['+attr+'-gruppo="'+gruppo+'"]').forEach(function(e){var on=e.getAttribute(attr)===id;
 if(e.getAttribute('role')==='tab'||e.classList.contains('chip'))e.setAttribute('aria-selected',on);else e.classList.toggle('hid',!on)})}
$$('[data-tab]').forEach(function(b){b.addEventListener('click',function(){attiva('tab',b.getAttribute('data-tab'),'data-tab')})});
$$('[data-match]').forEach(function(b){b.addEventListener('click',function(){attiva('match',b.getAttribute('data-match'),'data-match')})});
$$('table.ord').forEach(function(t){$$('th',t).forEach(function(th,i){th.addEventListener('click',function(){
 var dir=th.getAttribute('data-sort')==='desc'?'asc':'desc';$$('th',t).forEach(function(x){x.removeAttribute('data-sort')});th.setAttribute('data-sort',dir);
 var tb=t.tBodies[0],righe=$$('tr:not(.sep)',tb);
 righe.sort(function(a,b){var x=a.cells[i].getAttribute('data-v'),y=b.cells[i].getAttribute('data-v');
  var nx=parseFloat(x),ny=parseFloat(y);if(isNaN(nx)||isNaN(ny)){return dir==='asc'?String(x).localeCompare(String(y)):String(y).localeCompare(String(x))}
  return dir==='asc'?nx-ny:ny-nx});
 $$('tr.sep',tb).forEach(function(s){s.parentNode.removeChild(s)});righe.forEach(function(r){tb.appendChild(r)})})})});
function ricorda(k,v){try{sessionStorage.setItem(k,v)}catch(e){}}function leggi(k){try{return sessionStorage.getItem(k)}catch(e){return null}}
$$('[data-tab]').forEach(function(b){b.addEventListener('click',function(){ricorda('tab',b.getAttribute('data-tab'))})});
$$('[data-match]').forEach(function(b){b.addEventListener('click',function(){ricorda('match',b.getAttribute('data-match'))})});
var t0=leggi('tab'),m0=leggi('match');if(t0&&$('[data-tab="'+t0+'"]'))attiva('tab',t0,'data-tab');if(m0&&$('[data-match="'+m0+'"]'))attiva('match',m0,'data-match');
var ag=$('#agg'),msg=$('#msg');
if(ag){ag.addEventListener('click',function(){
 if(location.protocol==='file:'){msg.textContent='Da questo file non si può aggiornare: sono i dati di quando è stato creato. Per aggiornare, apri la pagina dal computer di casa (programma Avvia) oppure dalla versione online.';return}
 ag.disabled=true;msg.textContent='Aggiorno... può servire fino a un minuto';
 fetch('/aggiorna',{method:'POST'}).then(function(r){if(r.status===404)throw new Error('statica');return r.json()}).then(function(j){
  if(j.ok){msg.textContent='Fatto, ricarico...';location.reload()}else{ag.disabled=false;msg.textContent='Non riuscito: '+j.messaggio}
 }).catch(function(e){ag.disabled=false;
  if(e.message==='statica'){online()}
  else{msg.textContent='Impossibile aggiornare: il server non risponde. Riavvia "Avvia".'}})})}
var GH={t:'__DISPATCH_TOKEN__',r:'andrearizzo10897/cartellini-serie-a',ref:'main'};
function ghf(url,opz){opz=opz||{};opz.headers={'Authorization':'Bearer '+GH.t,'Accept':'application/vnd.github+json'};return fetch('https://api.github.com/repos/'+GH.r+url,opz)}
function online(){
 if(GH.t.indexOf('__')===0){msg.textContent='Versione online: si aggiorna da sola ogni 20 minuti. Ricarico l’ultima.';setTimeout(function(){location.reload()},1200);return}
 var ult=0;try{ult=parseInt(localStorage.getItem('agg_ult')||'0',10)}catch(e){}
 var resto=300000-(Date.now()-ult);
 if(resto>0){msg.textContent='Aggiornamento appena richiesto: riprova fra '+Math.ceil(resto/60000)+' min.';return}
 ag.disabled=true;msg.textContent='Richiesta inviata...';var t1=new Date(Date.now()-60000).toISOString();
 ghf('/actions/workflows/aggiorna.yml/dispatches',{method:'POST',body:JSON.stringify({ref:GH.ref})}).then(function(r){
  if(r.status!==204)throw new Error('http '+r.status);
  try{localStorage.setItem('agg_ult',String(Date.now()))}catch(e){}
  msg.textContent='Aggiorno online... circa 2 minuti, poi ricarico da solo.';
  var n=0,giro=function(){n++;if(n>30){msg.textContent='Ci sta mettendo più del solito: ricarica fra qualche minuto.';ag.disabled=false;return}
   ghf('/actions/runs?event=workflow_dispatch&created=%3E'+t1.slice(0,19)+'Z&per_page=1').then(function(r){return r.json()}).then(function(j){
    var run=(j.workflow_runs||[])[0];
    if(run&&run.status==='completed'){if(run.conclusion==='success'){msg.textContent='Fatto, ricarico...';setTimeout(function(){location.reload()},6000)}else{msg.textContent='Aggiornamento non riuscito: riprova più tardi.';ag.disabled=false}}
    else setTimeout(giro,8000)}).catch(function(){setTimeout(giro,8000)})};
  setTimeout(giro,10000)
 }).catch(function(e){ag.disabled=false;msg.textContent='Non riesco ad avviare l’aggiornamento ('+e.message+'). Si aggiorna comunque da solo ogni 20 minuti.'})}
var dt=$('#det');if(dt){dt.addEventListener('change',function(){document.body.classList.toggle('det-on',dt.checked)})}
var tm=$('#tema');if(tm){tm.addEventListener('click',function(){var d=document.documentElement,c=d.getAttribute('data-theme');
 d.setAttribute('data-theme',c==='light'?'dark':'light')})}
})();
"""


def n(x, d=2):
    return "–" if x is None else ("{:.%df}" % d).format(x).replace(".", ",")


def pct(x, d=0):
    return "–" if x is None else ("{:.%df}%%" % d).format(x * 100).replace(".", ",")


def barra(valore, massimo, testo, livello=""):
    larghezza = 0 if not massimo else max(0, min(100, valore / massimo * 100))
    return ('<div class="barcell"><span class="{l}">{t}</span><div class="bar {l}"><i style="width:{w:.0f}%"></i></div></div>'
            .format(t=testo, w=larghezza, l=livello))


def livello(prob, medio, alto):
    """Fascia di colore di una probabilità: bassa, media o alta."""
    return "p-alta" if prob >= alto else ("p-media" if prob >= medio else "p-bassa")


def quota(prob):
    """Quota minima conveniente: sopra questa quota la giocata ha valore (1 / probabilità stimata)."""
    if prob <= 0.005:
        return "q 200+"
    q = 1.0 / prob
    return "q " + (n(q, 1) if q >= 10 else n(q, 2))


def con_quota(prob, decimali=0):
    return "<b>{}</b><span class=\"q\" title=\"Conviene giocare solo se il bookmaker paga più di questa quota\">{}</span>".format(
        pct(prob, decimali), quota(prob))


def td(v, testo, extra=""):
    return '<td data-v="{}"{}>{}</td>'.format(escape(str(v)), extra, testo)


def quando(dt):
    return "{} {:02d}/{:02d} {:02d}:{:02d}".format(GIORNI[dt.weekday()], dt.day, dt.month, dt.hour, dt.minute)


# ---- Partite ---------------------------------------------------------------------------------
def righe_giocatori(lista, panchina):
    out = []
    for p in sorted(lista, key=lambda x: -x["p_giallo"]) if panchina else lista:
        alto = ' class="alto"' if p["p_giallo"] >= 0.2 else ""
        tag = "" if p["collegato"] else '<span class="tag" title="Giocatore senza storico in Serie A: uso la media del ruolo">nuovo</span>'
        celle = [
            '<td class="nome" data-v="{}">{}<span class="ruolo">{}</span>{}</td>'.format(
                escape(p["nome"]), escape(p["nome"]), p["ruolo"], tag),
            td(p["y90"], n(p["y90"], 2), ' class="nm"'), td(p["f90"], n(p["f90"], 1), ' class="det"'), td(p["t90"], n(p["t90"], 1), ' class="det"'),
            td(p["gialli_stag"], n(p["gialli_stag"], 0) if p["presenze_stag"] else "–", ' class="nm"'),
        ]
        if not panchina:
            celle.append(td(p["p_esce"], pct(p["p_esce"]), ' class="nm"'))
        if panchina:
            celle.append(td(p["p_entra"], pct(p["p_entra"])))
            celle.append(td(p["p_se_entra"], pct(p["p_se_entra"], 1), ' class="nm"'))
        celle.append('<td data-v="{}"{}>{}</td>'.format(p["p_giallo"], alto,
                                                         barra(p["p_giallo"], 0.5, con_quota(p["p_giallo"], 1),
                                                               livello(p["p_giallo"], 0.08, 0.15))))
        out.append("<tr>" + "".join(celle) + "</tr>")
    return "".join(out)


def tabella_squadra(sq):
    t = ('<div class="card"><h3>{} <span class="muted">· gialli attesi {}</span>{}</h3><div class="scroll">'
         '<table class="ord"><thead><tr><th>Giocatore</th><th class="nm" title="Gialli ogni 90 minuti (pesati sulle ultime stagioni)">Gialli/90</th>'
         '<th class="det">Falli/90</th><th class="det">Contrasti/90</th><th class="nm" title="Gialli presi in questa stagione">Gialli 26/27</th>'
         '<th class="nm" title="Probabilità di essere sostituito prima della fine: meno minuti in campo, meno rischio">Sostituito</th>'
         '<th title="Probabilità di essere ammonito in questa partita">P(giallo)</th></tr></thead><tbody>'
         ).format(escape(sq["nome"]), n(sq["atteso"], 2),
                  ' <span class="small">· modulo {}</span>'.format(escape(sq["formazione"])) if sq["formazione"] else "")
    t += "<tr class=\"sep\"><td colspan=\"7\">Titolari</td></tr>" + righe_giocatori(sq["titolari"], False)
    t += "</tbody></table></div>"
    if sq["panchina"]:
        t += ('<details class="panchina"><summary>Panchina · {} giocatori (probabilità di entrare e di essere ammoniti)</summary>'
              '<div class="scroll"><table class="ord"><thead><tr><th>Giocatore</th>'
              '<th class="nm">Gialli/90</th><th class="det">Falli/90</th><th class="det">Contrasti/90</th><th class="nm">Gialli 26/27</th>'
              '<th title="Probabilità di entrare, stimata da quante volte è entrato in stagione">P(entra)</th>'
              '<th class="nm" title="Probabilità di giallo se entra (circa 25 minuti)">Se entra</th>'
              '<th title="P(entra) x P(giallo se entra)">P(giallo)</th></tr></thead><tbody>')
        t += righe_giocatori(sq["panchina"], True) + "</tbody></table></div></details>"
        t = t.replace("<summary>Panchina · {} giocatori", "<summary>Panchina · {} giocatori".format(len(sq["panchina"])), 1)
    return t + "</div>"


def giocatori_partita(p):
    """(probabilità, nome, squadra, in panchina) di tutti i giocatori della partita, dal più al meno a rischio."""
    out = []
    for sq in p["squadre"]:
        for g in sq["titolari"]:
            out.append((g["p_giallo"], g["nome"], sq["nome"], False))
        for g in sq["panchina"]:
            out.append((g["p_giallo"], g["nome"], sq["nome"], True))
    return sorted(out, reverse=True)


def scheda_partita(i, p):
    ev = p["ev"]
    info = p["info_arbitro"]
    casa, trasf = escape(nome_squadra(ev["casa"])), escape(nome_squadra(ev["trasf"]))
    if p["arbitro"]:
        if info:
            arb = ('<div class="kpi"><span>Arbitro</span><b>{}</b><span>{} gialli/partita · {} rossi · {} partite · ultime 5: {}'
                   '<br>media Serie A: {}</span></div>').format(
                escape(p["arbitro"]), n(info["gialli"]), n(info["rossi"]), info["partite"], n(info["ultime5"]), n(info["lega"]))
        else:
            arb = ('<div class="kpi"><span>Arbitro</span><b>{}</b><span>Senza storico nei dati: nessun '
                   'aggiustamento sul modello</span></div>').format(escape(p["arbitro"]))
        arb_breve = "Arbitro " + escape(p["arbitro"])
    else:
        arb = '<div class="kpi"><span>Arbitro</span><b>da designare</b><span>L\'AIA pubblica le designazioni a metà settimana</span></div>'
        arb_breve = "arbitro da designare"
    badge = ('<span class="badge ok">Formazioni ufficiali</span>' if p["ufficiale"]
             else '<span class="badge" title="Le ufficiali escono circa un\'ora prima del calcio d\'inizio">Formazione probabile</span>')
    soglie = ""
    over_breve = ""
    for s in p["soglie"]:
        liv = livello(s["prob"], 0.35, 0.55)
        soglie += ("<tr><td>Oltre {}</td>{}<td>{}</td><td>{}</td><td>{}</td></tr>"
                   ).format(n(s["soglia"], 1), td(s["prob"], barra(s["prob"], 1, con_quota(s["prob"]), liv)),
                            pct(s["lega"]), pct(s["tipo"]), pct(s["arbitro"]))
        over_breve += '<span>Over {} <b class="{}">{}</b></span>'.format(n(s["soglia"], 1), liv, pct(s["prob"]))
    candidati = giocatori_partita(p)
    top3 = " · ".join("<b>{}</b> {}".format(escape(nome.split()[-1] if len(nome.split()) > 1 else nome), pct(pg))
                      for pg, nome, sq, panc in candidati[:3])
    rischio = ""
    if candidati:
        rischio = '<h3 class="titolo">Più a rischio di ammonizione</h3><div class="rischio">' + "".join(
            '<div class="r"><b class="{}">{}</b><span>{} · {}{}</span></div>'.format(
                livello(pg, 0.08, 0.15), pct(pg, 0), escape(nome), escape(sq), " · panchina" if panc else "")
            for pg, nome, sq, panc in candidati[:6]) + "</div>"
    riga1 = ('<div class="s-riga1"><span class="s-squadre">{c} – {t}</span><span class="s-quando">{q}</span>{b}</div>'
             ).format(c=casa, t=trasf, q=quando(ev["inizio"]), b=badge)
    riga2 = '<div class="s-riga2"><span><b>{}</b> gialli attesi</span>{}<span>{}</span></div>'.format(
        n(p["atteso"]), over_breve, arb_breve)
    riga3 = '<div class="s-top">Più a rischio: {}</div>'.format(top3) if top3 else ""
    corpo = (
        '<div class="kpis">{arb}'
        '<div class="kpi"><span>Gialli attesi (totale)</span><b>{att}</b><span>{casa}: {ac} · {trasf}: {at}<br>senza arbitro e tipo: {base}</span></div>'
        '<div class="kpi"><span>Tipo di partita</span><b>{tipo}</b><span>effetto sul totale: {ft}</span></div></div>'
        '<div class="scroll"><table class="soglie"><thead><tr><th>Gialli totali</th><th>Stimata</th>'
        '<th>Serie A</th><th>Tipo</th><th>Arbitro</th></tr></thead><tbody>{soglie}</tbody></table></div>'
        '{rischio}'
        '<details><summary class="small">Come leggere le percentuali e le quote</summary><p class="legenda">La probabilità stimata combina le squadre, '
        'le quote dei bookmaker, l\'arbitro e il tipo di partita. Sotto ogni percentuale c\'è la <b>quota minima conveniente</b> (1 diviso la '
        'probabilità): conviene giocare solo se il bookmaker paga di più. I colori vanno dal grigio-blu (probabilità bassa) all\'arancio (alta). '
        'Le colonne \u00abSerie A\u00bb, \u00abTipo\u00bb e \u00abArbitro\u00bb sono frequenze reali nello storico (ultime 380 partite, quelle dello stesso tipo, quelle dello stesso arbitro), utili per confronto.</p></details>'
        '<div class="cols" style="margin-top:12px">{t1}{t2}</div>'
    ).format(arb=arb, att=n(p["atteso"]), casa=casa, trasf=trasf, ac=n(p["squadre"][0]["atteso"]), at=n(p["squadre"][1]["atteso"]),
             base=n(p["atteso_base"]), tipo=escape(p["tipo"]),
             ft="{:+.0f}%".format((p["f_tipo"] - 1) * 100).replace("+0%", "nessuno").replace("-0%", "nessuno"),
             soglie=soglie, rischio=rischio, t1=tabella_squadra(p["squadre"][0]), t2=tabella_squadra(p["squadre"][1]))
    return '<details class="partita"><summary>{}{}{}</summary><div class="corpo">{}</div></details>'.format(riga1, riga2, riga3, corpo)


def riepilogo_giornata(partite):
    """Tre riquadri in cima: dove ci sono più gialli attesi, arbitri più severi, giocatori più a rischio."""
    if not partite:
        return ""
    righe = lambda coppie: "".join('<div class="riga"><span>{}</span><b>{}</b></div>'.format(a, b) for a, b in coppie)
    gialli = [("{} – {}".format(escape(nome_squadra(x["ev"]["casa"])), escape(nome_squadra(x["ev"]["trasf"]))), n(x["atteso"]))
              for x in sorted(partite, key=lambda x: -x["atteso"])[:3]]
    con_arbitro = sorted([x for x in partite if x["info_arbitro"] and x["info_arbitro"]["partite"] >= 10],
                         key=lambda x: -x["info_arbitro"]["gialli"])[:3]
    arbitri = [("{} · {} ({} partite)".format(escape(x["arbitro"]), escape(nome_squadra(x["ev"]["casa"])), x["info_arbitro"]["partite"]),
                n(x["info_arbitro"]["gialli"])) for x in con_arbitro] or [("Designazioni non ancora uscite", "")]
    tutti = sorted([(pg, nome, sq) for x in partite for pg, nome, sq, _ in giocatori_partita(x)], reverse=True)[:5]
    giocatori = [("{} · {}".format(escape(nome), escape(sq)), pct(pg)) for pg, nome, sq in tutti]
    return ('<div class="kpis riepilogo"><div class="kpi"><h3>Più gialli attesi</h3>{}</div>'
            '<div class="kpi"><h3>Arbitri più severi (gialli/partita, almeno 10 partite)</h3>{}</div>'
            '<div class="kpi"><h3>Giocatori più a rischio</h3>{}</div></div>').format(righe(gialli), righe(arbitri), righe(giocatori))


# ---- Sezioni globali -------------------------------------------------------------------------
def sezione_arbitri(righe, lega):
    massimo = max([r["gialli"] for r in righe] + [1])
    t = ('<div class="scroll"><table class="ord"><thead><tr><th>Arbitro</th><th>Partite</th><th>Gialli/partita</th>'
         '<th>Rossi/partita</th><th>Gialli casa</th><th>Gialli trasf.</th><th>Ultime 5</th><th>Stagione in corso</th>'
         '<th>Oltre 3,5</th><th>Oltre 4,5</th><th>Oltre 5,5</th></tr></thead><tbody>')
    for r in righe:
        poco = ' style="opacity:.55" title="Meno di 5 partite: media poco affidabile"' if r["partite"] < 5 else ""
        t += ("<tr" + poco + ">" + td(r["arbitro"], escape(r["arbitro"])) + td(r["partite"], r["partite"]) +
              td(r["gialli"], barra(r["gialli"], massimo, "<b>{}</b>".format(n(r["gialli"])))) +
              td(r["rossi"], n(r["rossi"])) + td(r["gialli_casa"], n(r["gialli_casa"])) +
              td(r["gialli_trasf"], n(r["gialli_trasf"])) + td(r["ultime5"], n(r["ultime5"])) +
              td(r["gialli_stag"] if r["gialli_stag"] is not None else -1,
                 "{} ({})".format(n(r["gialli_stag"]), r["partite_stag"]) if r["partite_stag"] else "–") +
              td(r["over35"], pct(r["over35"])) + td(r["over45"], pct(r["over45"])) + td(r["over55"], pct(r["over55"])) + "</tr>")
    return (t + "</tbody></table></div><p class=\"legenda\">Media Serie A: {} gialli a partita. Pochi dati = poca fiducia: "
            "con meno di 10 partite il modello avvicina l'arbitro alla media.</p>").format(n(lega["gialli"]))


def sezione_squadre(righe):
    if not righe:
        return "<p>Nessun dato.</p>"
    massimo = max([r["stag_fatti"] or 0 for r in righe] + [1])
    t = ('<div class="scroll"><table class="ord"><thead><tr><th>Squadra</th><th>Partite</th>'
         '<th title="Gialli presi dalla squadra, in casa">Casa: fatti</th><th title="Gialli presi dagli avversari, quando gioca in casa">Casa: subiti</th>'
         '<th>Trasf.: fatti</th><th>Trasf.: subiti</th><th>Stagione: fatti</th><th>Ultime 5: fatti</th><th>Ultime 10: fatti</th>'
         '<th>Storico: fatti</th><th>Ultime 5: subiti</th><th>Storico: subiti</th><th>Rossi</th></tr></thead><tbody>')
    for r in sorted(righe, key=lambda x: -(x["stag_fatti"] or 0)):
        def c(k, d=2):
            return td(r[k] if r[k] is not None else -1, n(r[k], d))
        t += ("<tr>" + td(r["squadra"], escape(r["squadra"])) + td(r["g_stag"], r["g_stag"]) + c("casa_fatti") + c("casa_subiti") +
              c("trasf_fatti") + c("trasf_subiti") +
              td(r["stag_fatti"] or 0, barra(r["stag_fatti"] or 0, massimo, "<b>{}</b>".format(n(r["stag_fatti"])))) +
              c("f5_fatti") + c("f10_fatti") + c("stor_fatti") + c("f5_subiti") + c("stor_subiti") + td(r["rossi_stag"], r["rossi_stag"]) + "</tr>")
    return (t + "</tbody></table></div><p class=\"legenda\"><b>Fatti</b> = gialli presi dalla squadra; <b>subiti</b> = gialli presi dagli avversari "
            "contro di lei. Valori medi a partita. \"Storico\" = stagioni precedenti dal 2023/24.</p>")


def sezione_tipi(righe):
    t = ('<div class="scroll"><table><thead><tr><th>Tipo di partita</th><th>Partite</th><th>Gialli/partita</th>'
         '<th>Rispetto alla media</th><th>Oltre 3,5</th><th>Oltre 4,5</th><th>Oltre 5,5</th></tr></thead><tbody>')
    for r in righe:
        t += "<tr><td>{}</td><td>{}</td><td><b>{}</b></td><td>{:+.0f}%</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            escape(r["tipo"]), r["partite"], n(r["gialli"]), (r["rapporto"] - 1) * 100, pct(r["over35"]), pct(r["over45"]), pct(r["over55"]))
    return (t + "</tbody></table></div><p class=\"legenda\"><b>Derby</b>: elenco fisso (Inter-Milan, Roma-Lazio, Juventus-Torino, Bologna-Fiorentina, "
            "Napoli-Roma...). <b>Big match</b>: entrambe nelle prime 6. <b>Scontro salvezza</b>: entrambe nelle ultime 6. "
            "Per il passato uso la classifica finale di quella stagione.</p>")


def sezione_metodo(lega, tempo):
    t = tempo
    return """
<div class="card"><h3>In sintesi</h3>
<p>Per ogni partita il programma risponde a tre domande, nell'ordine: <b>1)</b> quanti gialli prenderà ciascuna squadra;
<b>2)</b> come si dividono tra i giocatori, tenendo conto di chi gioca, di chi viene sostituito e di chi entra dalla panchina;
<b>3)</b> con che probabilità il totale supera 3,5, 4,5 o 5,5. Le percentuali sono stime statistiche, non certezze: un giallo è un
evento raro e molto casuale, e nessun modello sa se un arbitro deciderà di fischiare o no.</p></div>

<div class="card"><h3>1. Quanti gialli prenderà ogni squadra</h3><ul>
<li><b>Livello della Serie A.</b> Si parte dalla media recente di gialli, calcolata in modo che le ultime giornate pesino di più. Conta
perché i gialli sono calati ogni anno (4,3 a partita nel 2023/24, circa 3,5 oggi): usare lo storico intero farebbe sovrastimare.</li>
<li><b>Correzione per squadra.</b> Una regressione di Poisson tiene conto di: quanti gialli prende di solito la squadra, quanti ne induce
l'avversaria, il fattore campo, quanto la partita è equilibrata e chi è favorito secondo le quote dei bookmaker (le partite equilibrate hanno
più gialli) e i falli che le due squadre commettono e subiscono. Le partite vecchie contano meno (la metà ogni 400 giorni) e le squadre con
poche partite sono avvicinate alla media.</li>
<li><b>Arbitro.</b> Si confronta la media di gialli dell'arbitro con quella della Serie A. Con poche partite l'effetto viene ridotto: con n
partite pesa n/(n+15). Se l'arbitro non è ancora designato, il fattore è neutro.</li>
<li><b>Tipo di partita</b> (derby, big match, scontro salvezza): stessa logica, ridotta con n/(n+30).</li>
<li>Il totale atteso è la somma delle due squadre (ad esempio 1,8 + 2,1 = 3,9 gialli).</li></ul></div>

<div class="card"><h3>2. Come si dividono tra i giocatori</h3><ul>
<li><b>Gialli attesi del giocatore in una partita intera.</b> Dallo storico: Kickest (e Transfermarkt per chi Kickest non conosce) più la
stagione in corso, con le stagioni pesate 1 / 0,8 / 0,5 / 0,3 (2026/27, 2025/26, 2024/25, 2023/24). Chi ha giocato poco viene avvicinato
alla media del suo ruolo, equivalente a 10 partite: così non finisce a valori estremi.</li>
<li><b>I minuti non valgono tutti uguale.</b> Nelle {partite} partite ESPN analizzate solo il <b>{primo:.0f}%</b> dei gialli arriva nei primi
15 minuti e il <b>{ultimo:.0f}%</b> dal 75' in poi. Per questo il tempo in campo è misurato come quota di rischio, non in minuti.</li>
<li><b>Titolari.</b> Si stima la probabilità di essere sostituiti, per giocatore e per ruolo: nei dati escono prima della fine circa il
{p_p:.0f}% dei portieri, il {p_d:.0f}% dei difensori, il {p_c:.0f}% dei centrocampisti e il {p_a:.0f}% degli attaccanti, in media intorno
al {uscita:.0f}'. Chi esce presto prende meno rischio: è la colonna <b>Sostituito</b>.</li>
<li><b>Panchina.</b> <b>P(entra)</b> parte da quante volte il giocatore è entrato quando era in panchina, avvicinata alla media, e viene
poi riportata al numero di cambi della squadra: in Serie A entrano in media <b>{cambi:.1f}</b> giocatori a partita (massimo 5), con
differenze reali tra allenatori. Chi entra lo fa in media al <b>{ingresso:.0f}'</b> e si prende circa il <b>{rischio_sub:.0f}%</b> del
rischio di una partita intera: è la colonna <b>Se entra</b>. Quindi P(giallo) del panchinaro = P(entra) × Se entra.</li>
<li><b>Coerenza con la partita.</b> Un unico numero scala tutta la rosa in modo che la somma dei gialli dei giocatori coincida con il
totale atteso per la squadra. L'ordine tra i giocatori non cambia.</li>
<li><b>«nuovo»</b>: giocatore senza storico in Serie A. Si usa la media del ruolo, quindi la sua percentuale è poco informativa.</li></ul></div>

<div class="card"><h3>3. Le soglie over</h3><ul>
<li>Dal totale atteso si ricava con una distribuzione di Poisson la probabilità che i gialli siano più di 3,5, 4,5 o 5,5.</li>
<li>Le colonne «Serie A», «Tipo» e «Arbitro» sono frequenze reali, utili per confronto: ultime 380 partite di Serie A, partite dello stesso
tipo, partite dello stesso arbitro.</li></ul></div>

<div class="card"><h3>Come leggere le colonne dei giocatori</h3><ul>
<li><b>Gialli/90</b>, <b>Falli/90</b>, <b>Contrasti/90</b>: dati storici ogni 90 minuti giocati (falli e contrasti si vedono con
«Mostra falli e contrasti»; i contrasti arrivano solo da Kickest, stagioni passate).</li>
<li><b>Gialli 26/27</b>: gialli presi in questa stagione.</li>
<li><b>Sostituito</b>: probabilità di essere sostituito prima della fine.</li>
<li><b>P(entra)</b> e <b>Se entra</b> (solo panchina): vedi sopra.</li>
<li><b>P(giallo)</b>: probabilità di essere ammonito in questa partita.</li></ul></div>

<div class="card"><h3>Da dove arrivano i dati</h3><ul>
<li><b>football-data.co.uk</b>: gialli, rossi, falli e quote 1X2 di ogni partita, dal 2023/24 (si aggiorna con qualche giorno di ritardo: le partite più recenti le ricavo da ESPN).</li>
<li><b>ESPN</b>: calendario, formazioni ufficiali e panchina, minuto di cambi e ammonizioni (2025/26 e 2026/27), arbitri dal 2025/26 e quote 1X2 delle partite ancora da giocare (se mancano, la partita è trattata come media).</li>
<li><b>Kickest</b>: minuti, presenze, gialli, falli e contrasti per giocatore nel 2023/24, 2024/25 e 2025/26 (il 2026/27 non è ancora pubblicato).</li>
<li><b>Transfermarkt</b>: presenze, convocazioni, entrate, uscite e gialli per giocatore dal 2022/23. È il ripiego quando Kickest non conosce un giocatore.</li>
<li><b>API-Football (piano gratuito)</b>: arbitro di ogni partita del 2023/24 e 2024/25.</li>
<li><b>AIA</b>: designazioni arbitrali della giornata. Il sito mostra solo l'ultima: le salvo a ogni aggiornamento.</li></ul></div>

<div class="card"><h3>Quanto è affidabile</h3><ul>
<li><b>Gialli di squadra.</b> Ho rifatto ogni previsione di 2024/25, 2025/26 e 2026/27 usando solo i dati precedenti a quella partita
(<code>backtest.py</code>). Sull'errore delle soglie over (Brier, più basso è meglio): 0,193 con il metodo di partenza, 0,182 con
questo modello e 0,173 aggiungendo l'arbitro (partite 2025/26 e 2026/27, mai usate per tarare). La sovrastima sistematica dei gialli
(+0,27 a partita) è sparita.</li>
<li><b>Giocatori.</b> Sulle 58 partite 2026/27 giocate, con previsioni fatte solo con i dati precedenti: la probabilità di entrare è
molto più precisa (errore 0,545 contro 0,586) e per i panchinari la stima media è passata dall'1,7% al 2,3%, contro il 2,6% reale.
Il campione è piccolo: sono indicazioni, non prove definitive.</li>
<li><b>Provato e scartato</b> perché non migliorava i risultati: l'effetto dell'allenatore (né quello della squadra né quello di chi è appena
arrivato), distribuzioni più complesse di Poisson e lo storico arbitri di Transfermarkt prima del 2023.</li></ul></div>

<div class="card"><h3>Limiti da tenere presenti</h3><ul>
<li>Il modello non conosce squalifiche, diffide, infortuni, tattiche, meteo o importanza della gara. Prima delle formazioni ufficiali (circa un'ora prima) si usa l'ultima formazione schierata: le percentuali dei giocatori sono provvisorie.</li>
<li>Chi entra dalla panchina dipende da come va la partita: P(entra) è una media, non una previsione.</li>
<li>I minuti della stagione in corso per i singoli giocatori sono stimati (titolare = 90, o 68 se sostituito; subentrato = 25, o 15).</li>
<li>Dati usati: {partite_tot} partite storiche, {arb} con arbitro noto.</li></ul></div>""".format(
        partite=t["partite"], primo=t["primo_quarto"] * 100, ultimo=t["ultimo_quarto"] * 100,
        p_p=t["p_uscita"]["P"] * 100, p_d=t["p_uscita"]["D"] * 100, p_c=t["p_uscita"]["C"] * 100, p_a=t["p_uscita"]["A"] * 100,
        uscita=sum(t["uscita_media"][r] for r in "DCA") / 3.0, cambi=t["cambi"], ingresso=t["ingresso_medio"],
        rischio_sub=t["rischio_subentrato"] * 100, partite_tot=lega["partite"], arb=lega["arbitri_noti"])


def genera(partite, sezioni, percorso):
    lega = sezioni["lega"]
    pannelli = "".join(scheda_partita(i, p) for i, p in enumerate(partite))
    if not partite:
        pannelli = '<div class="card">Nessuna partita in programma nei prossimi giorni.</div>'
    note = "".join('<div class="note">{}</div>'.format(escape(s)) for s in sezioni["stato"])
    tabs = [("partite", "Partite"), ("arbitri", "Arbitri"), ("squadre", "Squadre"), ("tipi", "Tipo di partita"), ("metodo", "Come funziona")]
    nav = "".join('<button role="tab" data-tab="{k}" data-tab-gruppo="tab" aria-selected="{s}">{v}</button>'.format(
        k=k, v=v, s="true" if k == "partite" else "false") for k, v in tabs)
    corpo = {
        "partite": (riepilogo_giornata(partite) + '<div class="opzioni"><label><input type="checkbox" id="det"> '
                    'Mostra falli e contrasti</label></div>' + pannelli),
        "arbitri": "<h2>Arbitri: gialli e rossi a partita</h2>" + sezione_arbitri(sezioni["arbitri"], lega),
        "squadre": "<h2>Squadre: gialli fatti e subiti</h2>" + sezione_squadre(sezioni["squadre"]),
        "tipi": "<h2>Gialli per tipo di partita</h2>" + sezione_tipi(sezioni["tipi"]),
        "metodo": sezione_metodo(lega, sezioni["tempo"]),
    }
    sez = "".join('<div data-tab="{k}" data-tab-gruppo="tab" class="{c}">{h}</div>'.format(
        k=k, h=h, c="" if k == "partite" else "hid") for k, h in corpo.items())
    html = """<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#121211">
<title>Cartellini Serie A</title><style>{css}</style><noscript><style>.hid{{display:block!important}}nav.tabs,.az,#tema{{display:none!important}}</style></noscript></head>
<body><div class="wrap">
<header><div class="tit"><h1>Cartellini Serie A</h1><div class="muted">Stagione {anno}/{anno2} · Media Serie A (ultime 380 partite): {media} gialli a partita ({over35} oltre 3,5 · {over45} oltre 4,5 · {over55} oltre 5,5)</div></div>
<div class="small info">Aggiornato il {agg} · {fin} partite di quest'anno analizzate <button id="tema" class="tema" type="button">Tema chiaro/scuro</button></div><div class="az"><button id="agg" class="agg" type="button">Aggiorna</button><span id="msg"></span></div></header>
<noscript><div class="note"><b>JavaScript disattivato</b> (succede nelle anteprime di Files, Drive o email): mostro tutte le partite e tutte le sezioni una sotto l'altra. Per avere schede e pulsante Aggiorna apri il file con Safari o Chrome.</div></noscript>{note}<nav class="tabs" role="tablist">{nav}</nav>{sez}
</div><script>{js}</script></body></html>""".format(
        css=CSS, js=JS, anno=sezioni["aggiornato"].year if sezioni["aggiornato"].month >= 7 else sezioni["aggiornato"].year - 1,
        anno2=str((sezioni["aggiornato"].year if sezioni["aggiornato"].month >= 7 else sezioni["aggiornato"].year - 1) + 1)[2:],
        media=n(lega["gialli"]), over35=pct(lega["over"][3.5]), over45=pct(lega["over"][4.5]), over55=pct(lega["over"][5.5]),
        agg=sezioni["aggiornato"].strftime("%d/%m/%Y alle %H:%M"), fin=sezioni["partite_giocate"], note=note, nav=nav, sez=sez)
    percorso.write_text(html, encoding="utf-8")
