#!/usr/bin/env python3
"""Server locale: mostra la pagina e fa funzionare il pulsante "Aggiorna".

Uso:  python3 server.py            (solo da questo computer)
      python3 server.py --rete     (anche da altri dispositivi della stessa rete wifi, es. il telefono)
Il pulsante "Aggiorna" della pagina lancia aggiorna.py e ricarica la pagina.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config

PORTA = int(os.environ.get("PORTA_CARTELLINI", 8766))
_blocco = threading.Lock()


def _aggiorna():
    """Esegue aggiorna.py. Restituisce (ok, messaggio)."""
    if not _blocco.acquire(blocking=False):
        return False, "Un aggiornamento è già in corso"
    try:
        r = subprocess.run([sys.executable, str(config.BASE / "aggiorna.py")], cwd=str(config.BASE),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=900)
        coda = "\n".join(r.stdout.strip().splitlines()[-6:])
        return r.returncode == 0, coda
    except subprocess.TimeoutExpired:
        return False, "L'aggiornamento ha impiegato troppo tempo"
    finally:
        _blocco.release()


class Gestore(BaseHTTPRequestHandler):
    def _invia(self, codice, corpo, tipo):
        if isinstance(corpo, str):
            corpo = corpo.encode("utf-8")
        self.send_response(codice)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            if not config.OUTPUT.exists():
                _aggiorna()
            self._invia(200, config.OUTPUT.read_bytes(), "text/html; charset=utf-8")
        elif self.path.startswith("/stato"):
            self._invia(200, json.dumps({"in_corso": _blocco.locked(),
                                         "ultimo": config.OUTPUT.stat().st_mtime if config.OUTPUT.exists() else None}),
                        "application/json")
        else:
            self._invia(404, "Non trovato", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path.startswith("/aggiorna"):
            ok, msg = _aggiorna()
            self._invia(200 if ok else 500, json.dumps({"ok": ok, "messaggio": msg}, ensure_ascii=False),
                        "application/json")
        else:
            self._invia(404, "Non trovato", "text/plain; charset=utf-8")

    def log_message(self, formato, *args):  # niente rumore nel terminale
        pass


def _ip_locale():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "IP-del-computer"


def attesa_dopo(falliti):
    """Secondi fino al prossimo aggiornamento: 30 minuti, ma dopo un aggiornamento non riuscito si riprova presto
    (3 minuti, poi 10), altrimenti la pagina resta ferma per mezz'ora per un sito che ha risposto male una volta."""
    return {0: 1800, 1: 180, 2: 600}.get(falliti, 1800)


def _quote_in_background(falliti):
    """Finché la finestra è aperta scarica le quote DAZN Bet, le pubblica per la pagina online e rigenera la pagina locale."""
    while True:
        time.sleep(attesa_dopo(falliti))
        try:
            ok, msg = _aggiorna()
        except Exception as e:  # noqa: BLE001 - un errore non deve fermare il ciclo
            ok, msg = False, str(e)
        falliti = 0 if ok else falliti + 1
        if not ok:
            print("{} aggiornamento non riuscito, riprovo fra {} minuti:\n{}".format(
                time.strftime("%H:%M"), attesa_dopo(falliti) // 60, msg))


def main():
    rete = "--rete" in sys.argv
    # a ogni avvio aggiorno subito: così le quote e il loro orario sono quelli di adesso
    print("Aggiorno i dati prima di partire (può servire un minuto)...")
    ok, msg = _aggiorna()
    if not ok:
        print("Attenzione, aggiornamento non riuscito (riprovo fra {} minuti):\n{}".format(attesa_dopo(1) // 60, msg))
    threading.Thread(target=_quote_in_background, args=(0 if ok else 1,), daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0" if rete else "127.0.0.1", PORTA), Gestore)
    print("Pagina pronta su http://localhost:{}".format(PORTA))
    if rete:
        print("Dal telefono (stesso wifi): http://{}:{}".format(_ip_locale(), PORTA))
    print("Lascia aperta questa finestra: chiudila per spegnere il server.")
    webbrowser.open("http://localhost:{}".format(PORTA))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
