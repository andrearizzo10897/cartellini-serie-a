#!/bin/bash
# Doppio clic: avvia il server e apre la pagina (usa il pulsante Aggiorna).
cd "$(dirname "$0")"
python3 server.py "$@"
