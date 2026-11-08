#!/bin/sh
# Costruisce Provino.app (universale: Intel e Apple Silicon) e il .dmg.
# Serve un Mac con gli strumenti di Xcode (swiftc, lipo, codesign, hdiutil). Uso: sh packaging/macos/build-app.sh
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
VER=$(sed -n 's/^APP_VERSION = "\([^"]*\)".*/\1/p' provino.py)
PBS_TAG=${PBS_TAG:-20261026}
PY_VER=${PY_VER:-3.12.16}
B=build/macos
APP=dist/Provino.app
rm -rf "$B" "$APP" && mkdir -p "$B" dist "$APP/Contents/MacOS" "$APP/Contents/Resources/app" "$APP/Contents/Resources/bin"

echo "== finestra (Swift, universale)"
for a in x86_64 arm64; do
  swiftc -O -target $a-apple-macos11.0 -o "$B/Provino-$a" packaging/macos/Provino.swift
done
lipo -create "$B/Provino-x86_64" "$B/Provino-arm64" -output "$APP/Contents/MacOS/Provino"

echo "== aiutante USB (ImageCaptureCore)"
python3 -c "import sys; sys.path.insert(0, '.'); import provino_usb; open('$B/provino-usb.swift', 'w').write(provino_usb.SWIFT_SOURCE)"
for a in x86_64 arm64; do
  swiftc -O -target $a-apple-macos11.0 -o "$B/provino-usb-$a" "$B/provino-usb.swift"
done
lipo -create "$B/provino-usb-x86_64" "$B/provino-usb-arm64" -output "$APP/Contents/Resources/bin/provino-usb"

echo "== motore e pagina"
cp provino.py provino_wifi.py provino_usb.py provino_usb_linux.py provino_scheda.py provino_meta.py provino_pdf.py cameras.json LICENSE "$APP/Contents/Resources/app/"
cp -R web "$APP/Contents/Resources/app/web"
cp assets/icon/provino.icns "$APP/Contents/Resources/Provino.icns"
BUILD=$(date +%Y%m%d%H%M)
sed -e "s/@VERSION@/$VER/" -e "s/@BUILD@/$BUILD/" packaging/macos/Info.plist > "$APP/Contents/Info.plist"
printf 'APPL????' > "$APP/Contents/PkgInfo"

echo "== Python $PY_VER incluso (python-build-standalone $PBS_TAG)"
for pa in x86_64:x86_64 aarch64:arm64; do
  src=${pa%%:*}; dst=${pa##*:}
  tgz="$B/py-$src.tar.gz"
  url="https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_TAG/cpython-$PY_VER%2B$PBS_TAG-$src-apple-darwin-install_only_stripped.tar.gz"
  [ -f "$tgz" ] || curl -fsSL -o "$tgz" "$url"
  # impronta pubblicata da python-build-standalone (SHA256SUMS del rilascio): se il file e' diverso, mi fermo
  case "$PBS_TAG-$PY_VER-$src" in
    20241016-3.12.7-x86_64)  want=848405b92bda20fad1f9bba99234c7d3f11e0b31e46f89835d1cb3d735e932aa ;;
    20241016-3.12.7-aarch64) want=95dd397e3aef4cc1846867cf20be704bdd74edd16ea8032caf01e48f0c53d65d ;;
    20261026-3.12.16-x86_64)  want=37c38fda76fec1fbf310adcbafb7f0d96af13b5511bf8ea954c3aa8eec185734 ;;
    20261026-3.12.16-aarch64) want=353d5f1b4fd2715e7053f12f068435d5bbad16b91e057006b5d01e0925709a7e ;;
    *) echo "Impronta sconosciuta per $PBS_TAG $PY_VER $src: aggiungila allo script" >&2; exit 1 ;;
  esac
  got=$(shasum -a 256 "$tgz" | cut -d' ' -f1)
  [ "$got" = "$want" ] || { echo "Impronta sbagliata per $tgz: $got" >&2; exit 1; }
  mkdir -p "$B/py-$src" && tar -xzf "$tgz" -C "$B/py-$src"
  mv "$B/py-$src/python" "$APP/Contents/Resources/python-$dst"
  P="$APP/Contents/Resources/python-$dst"
  rm -rf "$P/include" "$P/share" "$P/lib/pkgconfig"
  L="$P/lib/python${PY_VER%.*}"
  rm -rf "$L/test" "$L/idlelib" "$L/tkinter" "$L/turtledemo" "$L/ensurepip" "$L/lib2to3" "$L/pydoc_data" \
         "$L/site-packages"/pip* "$L/config-"* "$L/lib-dynload/_tkinter"*
  find "$P" -name "__pycache__" -type d -prune -exec rm -rf {} +
  find "$P" -name "*.a" -delete
done

echo "== prova: il Python incluso carica tutti i moduli di Provino"
HA=$(uname -m); [ "$HA" = arm64 ] || HA=x86_64
(cd "$APP/Contents/Resources/app" && ../python-$HA/bin/python3 -B -c "import provino, provino_wifi, provino_usb, provino_scheda, provino_meta, provino_pdf; print('moduli ok', provino.APP_VERSION)")

echo "== firma (ad hoc)"
codesign --force --sign - "$APP/Contents/Resources/bin/provino-usb"
find "$APP/Contents/Resources" -type f \( -name "*.so" -o -name "*.dylib" -o -perm -u+x \) -exec sh -c 'file "$1" | grep -q Mach-O && codesign --force --sign - "$1"' _ {} \; 2>/dev/null || true
codesign --force --sign - "$APP"
codesign --verify --verbose=1 "$APP" || true

echo "== dmg"
DMG="dist/Provino-$VER-mac.dmg"
rm -f "$DMG"
STAGE="$B/dmg"
rm -rf "$STAGE" && mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
# finestra del disco come nelle app curate: icona di Provino sul disco, sfondo con la freccia verso Applicazioni
if command -v create-dmg >/dev/null 2>&1; then
  tiffutil -cathidpicheck packaging/macos/dmg-background.png packaging/macos/dmg-background@2x.png -out "$B/dmg-bg.tiff" >/dev/null
  create-dmg --volname "Provino" --volicon assets/icon/provino.icns --background "$B/dmg-bg.tiff" \
    --window-pos 200 160 --window-size 600 400 --icon-size 112 --text-size 13 \
    --icon "Provino.app" 150 200 --hide-extension "Provino.app" --app-drop-link 450 200 \
    --no-internet-enable "$DMG" "$STAGE" || rm -f "$DMG"
fi
if [ ! -f "$DMG" ]; then   # ripiego: disco semplice, sempre funzionante
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "Provino" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
fi
du -sh "$APP" "$DMG"
echo "Fatto: $DMG"
