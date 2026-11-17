#!/bin/bash
# setup_provinotest.sh - prepara l'account di quarantena (zona "recinto").
# Scarica Provino e lo script di controllo, verifica le impronte SHA-256 e crea
# le cartelle di lavoro. Si esegue UNA volta, come utente di quarantena:
#   sudo -H -u provinotest bash /tmp/setup_provinotest.sh
set -euo pipefail

VER="1.1.3"
APPIMG="Provino-${VER}-x86_64.AppImage"
APPIMG_URL="https://github.com/cisla66/Provino/releases/download/v${VER}/${APPIMG}"
APPIMG_SHA="98ebb8f37d2647456383e1b79a0b480bb8651933b9cd1e7ae720be001063c23f"
CHECK_URL="https://raw.githubusercontent.com/cisla66/Provino/main/tools/verifica_file.py"
CHECK_SHA="a724e261abf19483955ab0de8e9dcca90f12a354b58db5d820f4d96b35848706"

if [ "$(id -u)" -eq 0 ]; then echo "Non eseguire come root."; exit 1; fi
cd "$HOME"
mkdir -p Quarantena/in-arrivo Quarantena/verificati Applicazioni

scarica() {   # url file sha
  curl -fsSL -o "$2.part" "$1"
  got="$(sha256sum "$2.part" | cut -d' ' -f1)"
  if [ "$got" != "$3" ]; then
    rm -f "$2.part"; echo "ERRORE: impronta diversa per $2 (attesa $3, trovata $got). File non installato."; exit 1
  fi
  mv "$2.part" "$2"
}

scarica "$CHECK_URL"  Quarantena/verifica_file.py "$CHECK_SHA"
scarica "$APPIMG_URL" "Applicazioni/$APPIMG"       "$APPIMG_SHA"
chmod +x "Applicazioni/$APPIMG"

echo
echo "Fatto. In $HOME:"
echo "  Quarantena/in-arrivo     -> scarica qui i file ricevuti"
echo "  Quarantena/verificati    -> i file accettati, per modello"
echo "  Quarantena/verifica_file.py"
echo "  Applicazioni/$APPIMG"
