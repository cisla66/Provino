#!/bin/sh
# Costruisce Provino-<versione>-x86_64.AppImage dalla cartella del repository.
# Uso: sh packaging/linux/build-appimage.sh   (serve appimagetool nel PATH o in $APPIMAGETOOL)
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VER="$(sed -n 's/^APP_VERSION = "\([^"]*\)".*/\1/p' "$ROOT/provino.py")"
OUT="${OUT:-$ROOT/dist}"
APPDIR="$OUT/Provino.AppDir"
rm -rf "$APPDIR"; mkdir -p "$APPDIR/usr/share/provino" "$APPDIR/usr/share/applications"
for f in provino.py provino_finestra.py fuji_wifi.py fuji_usb_linux.py fuji_sd.py fuji_meta.py cameras.json; do
  cp "$ROOT/$f" "$APPDIR/usr/share/provino/"
done
cp -r "$ROOT/web" "$APPDIR/usr/share/provino/web"
cp "$ROOT/packaging/linux/AppRun" "$APPDIR/AppRun"; chmod +x "$APPDIR/AppRun"
cp "$ROOT/packaging/linux/io.github.cisla66.Provino.desktop" "$APPDIR/"
cp "$ROOT/packaging/linux/io.github.cisla66.Provino.desktop" "$APPDIR/usr/share/applications/"
mkdir -p "$APPDIR/usr/share/metainfo" && cp "$ROOT/packaging/linux/io.github.cisla66.Provino.metainfo.xml" "$APPDIR/usr/share/metainfo/"
cp "$ROOT/assets/icon/png/linux/256x256/provino.png" "$APPDIR/io.github.cisla66.Provino.png"
cp "$APPDIR/io.github.cisla66.Provino.png" "$APPDIR/.DirIcon"
for s in 16 24 32 48 64 128 256 512; do
  d="$APPDIR/usr/share/icons/hicolor/${s}x${s}/apps"; mkdir -p "$d"
  cp "$ROOT/assets/icon/png/linux/${s}x${s}/provino.png" "$d/io.github.cisla66.Provino.png"
done
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp "$ROOT/assets/icon/provino-linux.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/io.github.cisla66.Provino.svg"
TOOL="${APPIMAGETOOL:-appimagetool}"
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT/Provino-$VER-x86_64.AppImage" 2>/dev/null \
  || ARCH=x86_64 "$TOOL" "$APPDIR" "$OUT/Provino-$VER-x86_64.AppImage"
echo "$OUT/Provino-$VER-x86_64.AppImage"
