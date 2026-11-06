#!/bin/bash
# Doppio clic: apre Provino nel browser. / Double-click: opens Provino in your browser.
cd "$(dirname "$0")"
echo "Provino è aperto nel browser. Per chiuderlo chiudi questa finestra."
echo "Provino is open in your browser. Close this window to quit."
python3 provino.py
