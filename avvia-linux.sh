#!/bin/sh
# Provino su Linux: apri un terminale in questa cartella e scrivi  sh avvia-linux.sh
cd "$(dirname "$0")" && exec python3 provino.py "$@"
