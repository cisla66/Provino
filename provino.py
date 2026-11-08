#!/usr/bin/env python3
"""
Provino - scegli e scarica le foto dalle fotocamere Fujifilm (X-Pro3, X100VI).
Progetto indipendente e open source (MIT), non affiliato a FUJIFILM Corporation.

Avvio:  python3 provino.py   (si apre l'interfaccia nel browser)

Apre una pagina nel browser con le anteprime: scegli le foto e premi "Scarica".
Legge e copia soltanto: i comandi che cancellano o modificano la scheda sono bloccati.
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import webbrowser

try:
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
except ImportError:  # Python < 3.7
    from http.server import HTTPServer as ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _data_dir():
    """Dove scrivere impostazioni, log e aiutanti compilati.
    Dalla cartella dei sorgenti: la cartella stessa (come sempre). Dall'app installata (.dmg, AppImage),
    che e' di sola lettura: PROVINO_DATA oppure la cartella standard del sistema."""
    d = os.environ.get("PROVINO_DATA")
    if d:
        return d
    if os.access(HERE, os.W_OK) and not os.environ.get("APPIMAGE") and ".app/Contents/" not in HERE:
        return HERE
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Provino")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "Provino")


_DEV_CACHE = [0.0, None]


def connected_devices():
    """Cosa c'e' collegato adesso: fotocamere Fujifilm sul cavo USB (nome del modello) e schede nel lettore.
    Lettura veloce e senza toccare i dispositivi: ioreg sul Mac, /sys su Linux. Risultato tenuto 2 secondi."""
    now = time.time()
    if _DEV_CACHE[1] is not None and now - _DEV_CACHE[0] < 2:
        return _DEV_CACHE[1]
    usb = []
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["/usr/sbin/ioreg", "-p", "IOUSB", "-l", "-w0"], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, timeout=4).stdout.decode("utf-8", "replace")
            for block in out.split("+-o ")[1:]:
                if re.search(r'"idVendor" = 1227\b', block):          # 0x04CB = FUJIFILM
                    m = re.search(r'"USB Product Name" = "([^"]+)"', block) or re.match(r"([^@<]+)", block)
                    if m:
                        usb.append(m.group(1).strip())
        elif sys.platform.startswith("linux"):
            for d in glob.glob("/sys/bus/usb/devices/*"):
                try:
                    with open(os.path.join(d, "idVendor")) as fh:
                        if fh.read().strip().lower() != "04cb":
                            continue
                    with open(os.path.join(d, "product")) as fh:
                        usb.append(fh.read().strip())
                except OSError:
                    continue
    except Exception:  # noqa: BLE001
        pass
    try:
        import fuji_sd
        cards = [os.path.basename(v.rstrip("/")) for v in fuji_sd.find_cards()]
    except Exception:  # noqa: BLE001
        cards = []
    res = {"usb": sorted(set(u for u in usb if u)), "cards": cards}
    _DEV_CACHE[0], _DEV_CACHE[1] = now, res
    return res


def safe_filename(name):
    """Nome di file ricevuto dalla fotocamera o dalla scheda: solo il nome, mai un percorso (niente ../)."""
    name = str(name or "").replace("\\", "/").split("/")[-1].replace("\x00", "").strip()
    return "" if name in ("", ".", "..") or name.startswith(".") else name


def default_dest():
    """Cartella di download predefinita: 'scaricate' accanto ai sorgenti, Immagini/Provino per l'app installata."""
    if DATA == HERE:
        return os.path.join(HERE, "scaricate")
    pics = ""
    if sys.platform.startswith("linux"):
        try:
            pics = subprocess.run(["xdg-user-dir", "PICTURES"], stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, timeout=3).stdout.decode().strip()
        except (OSError, subprocess.SubprocessError):
            pics = ""
    if not pics or pics == os.path.expanduser("~"):
        pics = os.path.expanduser("~/Pictures")
    return os.path.join(pics, "Provino")


DATA = _data_dir()
os.makedirs(DATA, exist_ok=True)
import fuji_wifi as fw
import fuji_meta  # noqa: E402

APP_VERSION = "1.0.0-rc18"   # app native: GNOME (GTK4/libadwaita) e Mac (AppKit)


def iso_to_text(d):
    # "20261101T080552" -> "1 nov 2026, 08:05"
    mesi = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
    try:
        dt = datetime.datetime.strptime(d[:15], "%Y%m%dT%H%M%S")
        return "%d %s %d, %02d:%02d" % (dt.day, mesi[dt.month - 1], dt.year, dt.hour, dt.minute)
    except (ValueError, TypeError):
        return d or ""


VIDEO_KINDS = ("MOV", "MP4")   # i video: niente anteprima/ricetta, scaricati nella cartella VIDEO


def _slot_of(folder):
    """Via cavo il Mac chiama le schede "SLOT 1", "SLOT 2" (verificato con la X-Pro3)."""
    m = re.match(r"\s*SLOT\s*(\d)", folder or "", re.I)
    return int(m.group(1)) if m else 0


def _wifi_slot(storage):
    hi = storage >> 16
    return hi if hi in (1, 2) else 0


def _remove_quiet(p):
    try:
        os.remove(p)
    except OSError:
        pass


def _close_dates(a, b, tol=2):
    """Stesso scatto? Via cavo il Mac arrotonda l'ora di scatto al secondo successivo (visto con la
    X-Pro3: EXIF 10:11:47, elenco USB 10:11:48), quindi tollero un paio di secondi."""
    try:
        da = datetime.datetime.strptime(a[:15], "%Y%m%dT%H%M%S")
        db = datetime.datetime.strptime(b[:15], "%Y%m%dT%H%M%S")
        return abs((da - db).total_seconds()) <= tol
    except (ValueError, TypeError):
        return a[:15] == b[:15]


def _exif_datetime(buf):
    """DateTimeOriginal (0x9003) da un JPEG -> 'YYYYMMDDTHHMMSS' o None."""
    i = 2
    if buf[:2] != b"\xff\xd8":
        return None
    while i + 4 <= len(buf):
        if buf[i] != 0xFF:
            return None
        m = buf[i + 1]
        (ln,) = struct.unpack(">H", buf[i + 2:i + 4])
        if m == 0xE1 and buf[i + 4:i + 10] == b"Exif\x00\x00":
            t = buf[i + 10:i + 2 + ln]
            try:
                e = "<" if t[:2] == b"II" else ">"

                def ifd_entries(off):
                    (n,) = struct.unpack(e + "H", t[off:off + 2])
                    for k in range(n):
                        yield struct.unpack(e + "HHII", t[off + 2 + 12 * k:off + 14 + 12 * k])

                (ifd0,) = struct.unpack(e + "I", t[4:8])
                exif_off = None
                dt0 = None
                for tag, typ, cnt, val in ifd_entries(ifd0):
                    if tag == 0x8769:
                        exif_off = val
                    elif tag == 0x0132:
                        dt0 = t[val:val + 19]
                dt = None
                if exif_off:
                    for tag, typ, cnt, val in ifd_entries(exif_off):
                        if tag == 0x9003:
                            dt = t[val:val + 19]
                raw = (dt or dt0 or b"").decode("ascii", "ignore")
                if len(raw) == 19:
                    return raw[0:4] + raw[5:7] + raw[8:10] + "T" + raw[11:13] + raw[14:16] + raw[17:19]
            except (struct.error, IndexError):
                return None
            return None
        if m in (0xDA, 0xD9):
            return None
        i += 2 + ln
    return None


def local_capture_date(path):
    try:
        with open(path, "rb") as fh:
            head = fh.read(0x20000)
            if head[:15] == b"FUJIFILMCCD-RAW":
                off = struct.unpack(">I", head[84:88])[0]
                fh.seek(off)
                head = fh.read(0x20000)
        dt = _exif_datetime(head)
        if not dt and head[4:8] == b"ftyp":        # HEIF: l'EXIF sta dentro il contenitore
            try:
                import fuji_meta
                raw = str((fuji_meta.parse(head) or {}).get("date") or "")
                dt = (raw[:10].replace(":", "") + "T" + raw[11:19].replace(":", "")) if len(raw) >= 19 else None
            except Exception:
                dt = None
        if dt:
            return dt
        # video e file senza EXIF: il Mac li salva con la data di scatto come data di modifica
        return time.strftime("%Y%m%dT%H%M%S", time.localtime(os.path.getmtime(path)))
    except (OSError, struct.error):
        return None


def xacquire_running():
    """Ritorna il nome dell'app X Acquire se e' aperta (solo macOS), altrimenti ''."""
    if sys.platform != "darwin":
        return ""
    try:
        out = subprocess.run(["pgrep", "-ilf", "x acquire"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=3).stdout.decode("utf-8", "replace")
    except Exception:
        return ""
    for line in out.splitlines():
        if ".app/" in line:
            return line.split(".app/")[0].rsplit("/", 1)[-1]
    return "X Acquire" if out.strip() else ""


def xacquire_quit():
    name = xacquire_running()
    if not name:
        return True
    try:
        subprocess.run(["osascript", "-e", 'quit app "%s"' % name.replace('"', "")], timeout=8,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    time.sleep(1)
    return not xacquire_running()


def choose_folder(start, prompt="Provino"):
    """Finestra standard di sistema per scegliere una cartella. Ritorna '' se annullata."""
    try:
        if sys.platform == "darwin":
            script = ('set p to POSIX path of (choose folder with prompt "%s" '
                      'default location (POSIX file "%s"))' % (prompt.replace('"', ''), start.replace('"', '')))
            r = subprocess.run(["osascript", "-e", script, "-e", "return p"], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=600)
            return r.stdout.decode("utf-8", "replace").strip().rstrip("/") if r.returncode == 0 else ""
        if shutil.which("zenity"):
            r = subprocess.run(["zenity", "--file-selection", "--directory", "--filename=%s/" % start],
                               stdout=subprocess.PIPE, timeout=600)
            return r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else ""
    except Exception:
        pass
    return ""


def _usb_module():
    """Modulo del cavo USB: ImageCaptureCore sul Mac, libgphoto2 su Linux (stesse funzioni)."""
    if sys.platform.startswith("linux"):
        import fuji_usb_linux as m
    else:
        import fuji_usb as m
    return m


CAMERAS_PATH = os.path.join(HERE, "cameras.json")


def load_cameras():
    with open(CAMERAS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


class App:
    def __init__(self, dest, wireless, ip, log):
        self.dest = dest
        self.wireless = wireless
        self.abort = False
        self.usb = None
        self.usb_starting = False
        self.thumb_tries = {}
        self.camera_meta = {}
        self.choice = {}
        self.settings_path = os.path.join(DATA, "settings.json")
        old = os.path.join(HERE, "impostazioni.json")   # FujiWiFi <= 2.8
        if not os.path.exists(self.settings_path) and os.path.exists(old):
            try:
                os.replace(old, self.settings_path)
            except OSError:
                pass
        try:
            with open(self.settings_path, "r", encoding="utf-8") as fh:
                self.settings = json.load(fh)
        except (OSError, ValueError):
            self.settings = {}
        d = self.settings.get("dest")
        if d and os.path.isdir(d):
            self.dest = d
        self.ip = ip
        self.log = log
        self.lock = threading.RLock()       # accesso alla fotocamera
        self.state_lock = threading.Lock()  # stato condiviso con il browser
        self.cam = None
        self.status = "setup"  # setup, waiting, connecting, ready, error, cable, registering
        self.message_key = ""
        self.message_params = {}
        self.camera_name = ""
        self.camera_id = ""
        self.previews_ok = True
        self.cam_previews = True
        self.files = []        # dict per file
        self.thumbs = {}       # handle -> bytes | None
        self.queue = []
        self.current = None
        self.done = []
        self.failed = []
        self.cancel = False
        self.last_activity = time.time()
        self.stop = False
        self.connect_thread = None
        # anteprime grandi (per controllare il fuoco): handle del file sorgente -> bytes JPEG
        self.big = {}
        self.big_order = []
        self.big_lock = threading.Lock()
        self.big_want = None
        self.meta = {}         # scatto (base) -> metadati e ricetta (fuji_meta.parse)
        self.prefetching = False
        self.pending_names = []   # download interrotti dal distacco del cavo (per nome)
        self.meta_tries = {}
        self._group_cam = None   # fotocamera con D226/D227 gia' accesi
        self.date_shift = 0      # correzione dell'ora dei file (vedi _align_dates)

    # ------------------------------------------------------------ stato
    def set_status(self, status, key="", **params):
        """key = chiave del testo in web/i18n.js ("msg.<key>"), params = valori da inserire."""
        with self.state_lock:
            self.status = status
            self.message_key = key
            self.message_params = {k: str(v) for k, v in params.items()}
        self.log.info("[%s] %s %s" % (status, key, params if params else ""))

    def snapshot(self):
        with self.state_lock:
            return {
                "status": self.status,
                "message_key": self.message_key,
                "message_params": self.message_params,
                "camera": self.camera_name,
                "camera_id": self.camera_id,
                "camera_meta": self.camera_meta,
                "previews": self.previews_ok and self.cam_previews,
                "mode": "wireless" if self.wireless else "autosave",
                "dest": self.dest,
                "files": self.files,
                "queue": [q["name"] for q in self.queue],
                "current": self.current,
                "done": self.done[-200:],
                "failed": self.failed[-50:],
                "thumbs_ready": [h for h, v in self.thumbs.items() if v],
                "meta_n": len(self.meta),
                "pending": [f["handle"] for f in self.files if f["name"] in self.pending_names],
                "pending_n": len(self.pending_names),
                "version": APP_VERSION,
                "choice": self.choice,
                "settings": self.settings,
                "card": os.path.basename((getattr(self.usb, "vol", None) or "").rstrip("/")) if self.choice.get("method") == "card" else "",
                "card_models": list(getattr(self.usb, "models", []) or []) if self.choice.get("method") == "card" else [],
                "heif_preview": self._heif_ok(),
            }

    # ------------------------------------------------------------ collegamento
    # ------------------------------------------------------------ scelta iniziale
    def choose(self, camera, method):
        self.stop_session()
        self.choice = {"camera": camera, "method": method}
        self.settings.update(self.choice)
        self.save_settings()
        self.log.info("Scelta: %s, %s" % (camera, method))
        with self.state_lock:
            self.camera_name = camera
            self.camera_id = ""
            self.camera_meta = {}
            self.files = []
            self.thumbs = {}
            self.meta, self.meta_tries = {}, {}
        self.big, self.big_order = {}, []
        self.date_shift = 0
        if method == "cable":
            self.abort = False
            self.set_status("waiting", "")
            threading.Thread(target=self._connect_usb, args=(camera,), daemon=True).start()
            return
        if method == "card":
            self.abort = False
            self.set_status("waiting", "")
            threading.Thread(target=self._connect_card, daemon=True).start()
            return
        self.wireless = (method == "direct")
        self.abort = False
        self.set_status("waiting", "")
        self.start_connect()

    # ------------------------------------------------------------ cavo USB (macOS e Linux)
    def _connect_usb(self, camera):
        fuji_usb = _usb_module()
        if self.usb_starting:
            return  # gia' in partenza: niente seconda copia dell'aiutante
        self.usb_starting = True
        if self.usb:
            try:
                self.usb.stop()
            except Exception:
                pass
            self.usb = None
        self._usb_files = []
        self.thumb_tries = {}
        try:
            bindir = os.path.join(DATA, ".provino_bin")
            first = sys.platform == "darwin" and not (os.path.isdir(bindir) and any(n.startswith("fujiusb_") for n in os.listdir(bindir)))
            self.set_status("waiting", "usb_prepare" if first else "")
            hint = (load_cameras()["cameras"].get(camera) or {}).get("usb_hint") or camera.lower().replace("-", "")
            sess = fuji_usb.UsbSession(DATA, hint, self.log, self._usb_event)
            sess.start()
            self.usb = sess
            self.set_status("waiting", "")
        except Exception as e:  # noqa: BLE001
            self.log.info("Cavo USB nell'app non disponibile: %s" % e)
            self.usb = None
            self.set_status("cable", "usb_failed", detail=e)
        finally:
            self.usb_starting = False

    _heif_cache = None

    def _heif_ok(self):
        if App._heif_cache is None:
            try:
                import fuji_sd
                App._heif_cache = fuji_sd.can_heif()
            except Exception:  # noqa: BLE001
                App._heif_cache = False
        return App._heif_cache

    # ------------------------------------------------------------ lettore di schede (macOS e Linux)
    def _connect_card(self):
        """La scheda nel lettore: si legge come un disco, in sola lettura (fuji_sd)."""
        import fuji_sd
        if self.usb:
            try:
                self.usb.stop()
            except Exception:
                pass
            self.usb = None
        self._usb_files = []
        self.thumb_tries = {}
        sess = fuji_sd.CardSession(HERE, "", self.log, self._usb_event, dest_dir=self.dest)
        sess.start()
        self.usb = sess
        self.set_status("waiting", "")

    def _usb_event(self, ev):
        k = ev.get("event")
        if self.abort:
            return
        if k == "device":
            self.log.info("%s: %s" % ("Scheda" if self.choice.get("method") == "card" else "USB: dispositivo", ev.get("name")))
        elif k in ("opening", "session"):
            with self.state_lock:
                self.camera_name = (ev.get("name") or self.camera_name)
            self.set_status("connecting", "reading_card")
        elif k == "file":
            name = safe_filename(ev.get("name") or "")
            if not name:
                return
            base, ext = os.path.splitext(name)
            e = ext.upper()
            kind = "RAF" if e == ".RAF" else ("JPG" if e in (".JPG", ".JPEG") else e.lstrip("."))
            size = ev.get("size")
            if any(x["handle"] == ev["id"] for x in self._usb_files):
                return
            self._usb_files.append({
                "handle": ev["id"], "name": name, "base": base, "kind": kind,
                "size": size, "date": self._shifted(ev.get("date", "")), "date_text": iso_to_text(self._shifted(ev.get("date", ""))),
                "on_mac": False, "folder": ev.get("folder", ""),
                "slot": _slot_of(ev.get("folder", "")),
            })
            self._usb_files[-1]["on_mac"] = self._on_mac(name, size, self._usb_files[-1])
            if self.status == "ready":
                self._publish_usb_files()
        elif k == "ready":
            with self.state_lock:
                self.camera_name = ev.get("name") or self.camera_name
            self._publish_usb_files()
            self.previews_ok = True
            self.cam_previews = True
            already = self.status == "ready"
            self.set_status("ready", "")
            if not already:
                threading.Thread(target=self._prefetch_thumbs, daemon=True).start()
        elif k == "progress":
            with self.state_lock:
                if self.current and self.current.get("handle") == ev.get("id") and self.current.get("total"):
                    tot = self.current["total"]
                    got = int(tot * float(ev.get("fraction") or 0))
                    el = max(time.time() - self.current.get("t0", time.time()), 0.001)
                    self.current.update({"got": got, "speed": got / el})
        elif k in ("removed", "exited"):
            if self.choice.get("method") in ("cable", "card") and self.status in ("ready", "connecting", "waiting"):
                with self.state_lock:
                    # download in sospeso: li ricordo per nome e li riseleziono quando torna il cavo
                    pend = ([self.current["name"]] if self.current else []) + [q["name"] for q in self.queue]
                    for n in pend:
                        if n not in self.pending_names:
                            self.pending_names.append(n)
                    self.queue = []
                    if pend:
                        self.log.info("Cavo scollegato durante il download: %d file in sospeso" % len(pend))
                    self.files = []
                    self.thumbs = {}
                self._usb_files = []
                card = self.choice.get("method") == "card"
                if k == "exited" and card:
                    return
                self.set_status("waiting", "card_removed" if card else "usb_unplugged")
                if k == "exited" and not self.stop and not self.abort:
                    self.usb = None
                    threading.Thread(target=lambda: (time.sleep(2), self._connect_usb(self.choice.get("camera", ""))),
                                     daemon=True).start()
        elif k == "error":
            self.set_status("waiting", "card_error" if self.choice.get("method") == "card" else "usb_error",
                            detail=ev.get("message"))

    def _publish_usb_files(self):
        files = sorted(self._usb_files, key=lambda f: (f["date"], f["base"], f["kind"]), reverse=True)
        with self.state_lock:
            self.files = files

    def _download_usb(self, f):
        name = f.get("_target") or f["name"]
        action = f.get("_action", "new")
        d = self.dir_for(f)
        os.makedirs(d, exist_ok=True)
        with self.state_lock:
            if self.current:
                self.current.update({"total": f.get("size") or 0, "t0": time.time()})
        t0 = time.time()
        # Scarico in "<nome>.part" e rinomino solo a file completo: se il cavo si stacca
        # non resta nessun file a meta' (ne' da 0 byte) e un file esistente non viene toccato.
        tmp_name = name + ".part"
        tmp = os.path.join(d, tmp_name)
        _remove_quiet(tmp)
        fuji_usb = _usb_module()
        import fuji_sd
        try:
            got = self.usb.download(f["handle"], d, tmp_name, True, lambda: self.cancel)
            if got != tmp and os.path.exists(got):
                os.replace(got, tmp)
        except (fuji_usb.UsbError, fuji_sd.CardError) as e:
            _remove_quiet(tmp)
            raise fw.FujiError(str(e))
        size = os.path.getsize(tmp) if os.path.exists(tmp) else -1
        if size <= 0 or (f.get("size") and size != f["size"]):
            _remove_quiet(tmp)
            raise fw.FujiError("file incompleto (%d di %s byte)" % (max(size, 0), f.get("size")))
        path = os.path.join(d, name)
        if os.path.exists(path) and action != "overwrite":
            path = os.path.join(d, self._free_name(name, set(), d))   # mai sovrascrivere senza permesso
        os.replace(tmp, path)
        self.log.info("Scaricato %s %s (%s in %.1f s)" % ("dalla scheda" if self.choice.get("method") == "card" else "via cavo",
                      path, fw.human(f.get("size") or 0), time.time() - t0))
        return path, False

    def tr(self, it, en):
        return it if self.settings.get("ui_lang", "it") == "it" else en

    def save_settings(self):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as fh:
                json.dump(self.settings, fh)
        except OSError:
            pass

    def stop_session(self):
        self.abort = True
        with self.state_lock:
            self.queue = []
        self.cancel = True
        t = self.connect_thread
        if t and t.is_alive():
            t.join(timeout=3)
        self._close_cam()
        if self.usb:
            try:
                self.usb.stop()
            except Exception:
                pass
            self.usb = None
        self.cancel = False
        self.big, self.big_order = {}, []
        self.meta, self.meta_tries = {}, {}
        self.pending_names = []
        self.set_status("setup", "")

    def register(self):
        def run():
            self.abort = False
            self.set_status("registering", "")
            try:
                info = {}
                fw.autosave_handshake(self.log, register=True, wait=300, should_stop=lambda: self.abort or self.stop)
                self.set_status("setup", "registered")
            except (fw.FujiError, OSError) as e:
                self.set_status("setup", "register_failed", detail=e)
        self.stop_session()
        threading.Thread(target=run, daemon=True).start()

    def start_connect(self):
        if self.connect_thread and self.connect_thread.is_alive():
            return
        self.connect_thread = threading.Thread(target=self._connect, daemon=True)
        self.connect_thread.start()

    def _connect(self):
        self._close_cam()
        with self.state_lock:
            self.files = []
            self.thumbs = {}
        cam = fw.FujiCamera(self.ip, self.log)
        try:
            if not self.wireless:
                if self.status == "waiting":
                    self.set_status("waiting", self.message_key, **self.message_params)
                else:
                    self.set_status("waiting", "")
                info = {}
                while True:  # se la fotocamera non completa il saluto, riproviamo da soli
                    try:
                        cam.ip = fw.autosave_handshake(self.log, register=False, wait=600, info=info,
                                                       should_stop=lambda: self.abort or self.stop,
                                                       on_registered=lambda r: self.set_status(
                                                           "waiting", "auto_registered", cam=r.get("model") or "?"))
                        break
                    except (fw.FujiError, OSError) as e:
                        if self.stop or self.abort:
                            return
                        self.log.info("Saluto non completato: %s" % e)
                        self.set_status("waiting", "handshake_retry")
                        time.sleep(1)
                with self.state_lock:
                    self.camera_id = info.get("dscname", "")
                    self.camera_name = info.get("model", "") or self.camera_name
                time.sleep(0.5)
            if self.wireless:
                # rete della fotocamera: aspetto che il Mac ci si colleghi
                while not (self.abort or self.stop):
                    try:
                        s_ = socket.create_connection((cam.ip, fw.CMD_PORT), timeout=2)
                        s_.close()
                        break
                    except OSError:
                        time.sleep(2)
                if self.abort or self.stop:
                    return
            self.set_status("connecting", "opening_card")
            with self.lock:
                cam.connect()
                with self.state_lock:
                    self.camera_name = cam.cam_name or self.camera_name or "Fotocamera"
                cam.setup()
            self.cam = cam
            self.last_activity = time.time()
            # Le anteprime in PC AUTO SAVE funzionano leggendo anche la fine del file
            # (verificato con la X-Pro3, vedi FujiCamera.preview).
            self.cam_previews = True
            self.set_status("connecting", "reading_list")
            self._load_list()
            self.set_status("ready", "")
            threading.Thread(target=self._prefetch_thumbs, daemon=True).start()
        except Exception as e:  # noqa: BLE001
            self.log.debug("Collegamento fallito: %r" % (e,))
            try:
                cam.close()
            except Exception:
                pass
            self.cam = None
            self.set_status("error", "error", detail=e)

    def _close_cam(self):
        if self.cam:
            with self.lock:
                try:
                    self.cam.close()
                except Exception:
                    pass
            self.cam = None

    def _load_list(self):
        files = []
        for h in self.cam.handles():
            with self.lock:
                info = self.cam.object_info(h)
            if not info or info["format"] == 0x3001:
                continue
            name = safe_filename(info["filename"])
            if not name:
                continue
            base, ext = os.path.splitext(name)
            kind = "RAF" if ext.upper() == ".RAF" else ("JPG" if ext.upper() in (".JPG", ".JPEG") else ext.upper().lstrip("."))
            files.append({
                "handle": h,
                "name": name,
                "base": base,
                "kind": kind,
                "size": info["size"] if self.cam.autosave else None,
                "date": self._shifted(info["date"]),
                "date_text": iso_to_text(self._shifted(info["date"])),
                "on_mac": False,
                # Wi-Fi: lo StorageID non dice in modo affidabile lo slot (X-Pro3 in Wi-Fi diretto: 0x1000xxxx),
                # quindi lo uso solo se e' proprio 1 o 2; altrimenti nessuna icona SD.
                "slot": _wifi_slot(info.get("storage") or 0),
            })
            iso = self._exif_iso(self.meta.get(base)) if kind in ("JPG", "RAF") else ""
            if iso:   # ricollegamento: l'ora gia' letta dall'EXIF resta quella giusta
                files[-1]["cam_date"] = files[-1]["date"]
                files[-1]["date"], files[-1]["date_text"] = iso, iso_to_text(iso)
            files[-1]["on_mac"] = self._on_mac(name, files[-1]["size"], files[-1])
        files = self._fix_videos(files)
        with self.state_lock:
            self.files = files

    def dir_for(self, f, dest=None, split_type=None, by_date=None):
        """Cartella di destinazione di un file, secondo le scelte dell'utente:
        <dest>[/AAAA-MM-GG][/RAF|JPG]."""
        d = dest or self.dest
        if by_date is None:
            by_date = self.settings.get("by_date", False)
        if split_type is None:
            split_type = self.settings.get("split_type", False)
        dt = (f.get("date") or "")[:8]
        if by_date and len(dt) == 8 and dt.isdigit():
            d = os.path.join(d, "%s-%s-%s" % (dt[:4], dt[4:6], dt[6:8]))
        if split_type:
            k = f.get("kind") or "ALTRI"
            d = os.path.join(d, "VIDEO" if k in VIDEO_KINDS else ("HEIF" if k == "HIF" else k))
        return d

    def refresh_on_mac(self):
        with self.state_lock:
            for f in self.files:
                f["on_mac"] = self._on_mac(f["name"], f.get("size"), f)
            self.thumbs = {h: v for h, v in self.thumbs.items() if v}

    def _on_mac(self, name, size, f=None):
        p = os.path.join(self.dir_for(f) if f else self.dest, name)
        if not os.path.exists(p):
            return False
        return size is None or os.path.getsize(p) == size

    # ------------------------------------------------------------ anteprime
    def _wait_list_stable(self, quiet=1.2, longest=20):
        """Via cavo la fotocamera puo' dire "pronta" quando l'elenco dei file non e' ancora completo."""
        t0, n, last = time.time(), -1, time.time()
        while time.time() - t0 < longest and not self.stop:
            if len(self.files) != n:
                n, last = len(self.files), time.time()
            elif time.time() - last >= quiet:
                return
            time.sleep(0.2)

    def _prefetch_thumbs(self):
        if self.prefetching:
            return
        self.prefetching = True
        try:
            self._wait_list_stable()
            if not self.camera_meta:
                self._read_camera_meta()
            while not self.stop:
                n = len(self.files)
                self._prefetch_thumbs_loop()
                self._meta_loop()
                if len(self.files) == n:   # nel frattempo sono arrivati altri file? allora un altro giro
                    break
        finally:
            self.prefetching = False

    # ------------------------------------------------------------ metadati e ricetta per scatto
    @staticmethod
    def _exif_iso(m):
        """Data e ora di scatto dall'EXIF ('2026:11:05 15:00:36') -> '20261105T150036', o ''."""
        d = (m or {}).get("date") or ""
        try:
            return datetime.datetime.strptime(d[:19], "%Y:%m:%d %H:%M:%S").strftime("%Y%m%dT%H%M%S")
        except (ValueError, TypeError):
            return ""

    def _date_from_exif(self, base, m):
        """Ogni foto prende l'ora del proprio EXIF (DateTimeOriginal), che e' quella mostrata dalla
        fotocamera: in Wi-Fi la X-Pro3 dichiarava le foto 2 ore indietro (verificato il 6 nov 2026).
        I video non hanno EXIF: prendono la stessa correzione della foto piu' vicina nel tempo."""
        iso = self._exif_iso(m)
        if not iso:
            return
        with self.state_lock:
            for x in self.files:
                if x["base"] == base and x["kind"] in ("JPG", "RAF"):
                    x.setdefault("cam_date", x.get("date") or "")
                    if (x.get("date") or "")[:15] != iso:
                        x["date"], x["date_text"] = iso, iso_to_text(iso)
            self.files = self._fix_videos(self.files)

    @staticmethod
    def _dt(s):
        try:
            return datetime.datetime.strptime((s or "")[:15], "%Y%m%dT%H%M%S")
        except (ValueError, TypeError):
            return None

    def _fix_videos(self, files):
        """Correzione dell'ora dei video: lo scarto (EXIF - ora dichiarata) della foto piu' vicina."""
        pairs = []
        for x in files:
            if x["kind"] in ("JPG", "RAF") and x.get("cam_date"):
                c, e = self._dt(x["cam_date"]), self._dt(x["date"])
                if c and e:
                    pairs.append((c, e - c))
        if pairs:
            for x in files:
                if x["kind"] in VIDEO_KINDS:
                    x.setdefault("cam_date", x.get("date") or "")
                    c = self._dt(x["cam_date"])
                    if c:
                        diff = min(pairs, key=lambda p: abs((p[0] - c).total_seconds()))[1]
                        x["date"] = (c + diff).strftime("%Y%m%dT%H%M%S")
                        x["date_text"] = iso_to_text(x["date"])
        return sorted(files, key=lambda x: (x["date"], x["base"], x["kind"]), reverse=True)

    def _raf_size(self, f):
        """Dimensioni della foto da un RAF (tag 0x111 'RawImageCroppedSize' dell'intestazione CFA): (larghezza, altezza)."""
        local = os.path.join(self.dir_for(f), f["name"])

        def rd(off, n):
            if f.get("on_mac") and os.path.exists(local):
                with open(local, "rb") as fh:
                    fh.seek(off)
                    return fh.read(n)
            if self.usb is not None:
                return self.usb.read(f["handle"], off, n) or b""
            return b""   # Wi-Fi: niente letture in piu'
        try:
            head = rd(0, 0x64)
            if head[:15] != b"FUJIFILMCCD-RAW":
                return None
            co, cl = struct.unpack(">II", head[92:100])
            d = rd(co, min(cl, 512))
            n = struct.unpack(">I", d[:4])[0]
            off = 4
            for _ in range(min(n, 64)):
                tag, ln = struct.unpack(">HH", d[off:off + 4])
                if tag == 0x111 and ln == 4:
                    h, w = struct.unpack(">HH", d[off + 4:off + 8])
                    return (w, h) if w and h else None
                off += 4 + ln
        except (OSError, struct.error):
            return None
        return None

    def _set_meta(self, f, head):
        m = fuji_meta.parse(head or b"")
        if not m:
            return None
        if f.get("kind") == "RAF":
            # l'EXIF dentro il RAF descrive l'anteprima JPEG: la misura vera e' nell'intestazione del RAF
            m.pop("width", None)
            m.pop("height", None)
            size = self._raf_size(f)
            if size:
                m["width"], m["height"] = size
        m["from"] = f["name"]
        with self.state_lock:
            self.meta[f["base"]] = m
        self._date_from_exif(f["base"], m)
        self.log.debug("metadati %s: orientamento %s, %sx%s, %s" % (f["name"], m.get("orientation_raw"),
                       m.get("width"), m.get("height"), m.get("film")))
        return m

    def _head_of(self, f, length=0x10000):
        """Inizio del JPEG (o del JPEG dentro il RAF): li' c'e' tutto l'EXIF."""
        is_raf = f["kind"] == "RAF"
        local = os.path.join(self.dir_for(f), f["name"])
        if f.get("on_mac") and os.path.exists(local):
            with open(local, "rb") as fh:
                head = fh.read(0x60 if is_raf else length)
                if is_raf:
                    loc = fw.jpeg_from_raf_head(head)
                    if not loc:
                        return b""
                    fh.seek(loc[0])
                    return fh.read(min(length, loc[1]))
                return head
        if self.usb is not None:
            if is_raf:
                loc = fw.jpeg_from_raf_head(self.usb.read(f["handle"], 0, 0x60) or b"")
                return (self.usb.read(f["handle"], loc[0], min(length, loc[1])) or b"") if loc else b""
            return self.usb.read(f["handle"], 0, length) or b""
        if self.cam is not None:
            with self.lock:
                data = self.cam.read_head(f["handle"], f["name"], length)
                self.last_activity = time.time()
            return data
        return b""

    def shot_meta(self, f):
        if f["base"] in self.meta:
            return self.meta[f["base"]]
        if not any(x["kind"] in ("JPG", "RAF", "HIF") for x in self.files if x["base"] == f["base"]):
            return None   # video: nessuna ricetta
        if self.meta_tries.get(f["base"], 0) >= 3:
            return None
        self.meta_tries[f["base"]] = self.meta_tries.get(f["base"], 0) + 1
        group = {x["kind"]: x for x in self.files if x["base"] == f["base"]}
        src = next((x for x in (group.get("JPG"), group.get("RAF"), group.get("HIF")) if x and x.get("on_mac")), None) \
            or group.get("JPG") or group.get("RAF") or group.get("HIF") or f
        if self.usb is None and not src.get("on_mac") and \
                (self.current or self.queue or not self.previews_ok or self.cam is None):
            self.meta_tries[f["base"]] -= 1   # via Wi-Fi una cosa alla volta: riprovo piu' tardi
            return None
        try:
            return self._set_meta(src, self._head_of(src))
        except Exception as e:  # noqa: BLE001
            self.log.debug("metadati %s: %r" % (src["name"], e))
            return None

    def _meta_loop(self):
        """Dopo le anteprime: metadati di tutti gli scatti (servono per il filtro per pellicola)."""
        for rnd in range(3):
            todo = {}
            for f in sorted(self.files, key=lambda x: x["date"], reverse=True):
                if f["kind"] in VIDEO_KINDS:
                    continue
                if f["base"] not in self.meta and f["base"] not in todo:
                    todo[f["base"]] = f
            if not todo:
                return
            for f in todo.values():
                if self.stop or (self.cam is None and self.usb is None):
                    return
                while self.queue or self.current:  # i download hanno la precedenza
                    time.sleep(0.5)
                    if self.stop:
                        return
                if self.cam is not None and not self.previews_ok:
                    return   # via Wi-Fi la fotocamera non regge le letture parziali: lascio stare
                self.shot_meta(f)
            time.sleep(2)

    def _prefetch_thumbs_loop(self):
        # una anteprima per scatto: prima dal JPG (piu' leggero), altrimenti dal RAF.
        # Piu' passaggi: la fotocamera puo' rispondere "non ancora pronta" ai primi tentativi
        # e i file possono continuare ad arrivare dopo l'elenco iniziale.
        for rnd in range(6):
            seen = {}
            for f in list(self.files):
                b = f["base"]
                if f["kind"] in VIDEO_KINDS:
                    continue   # la fotocamera non da' anteprime dei video (ImageCaptureCore: errore -21000)
                rank = {"JPG": 0, "RAF": 1, "HIF": 2}   # l'anteprima piu' leggera: JPG, poi RAF, poi HEIF
                if b not in seen or rank.get(f["kind"], 3) < rank.get(seen[b]["kind"], 3):
                    seen[b] = f
            order = sorted(seen.values(), key=lambda f: f["date"], reverse=True)
            missing = 0
            for f in order:
                if self.stop or (self.cam is None and self.usb is None):
                    return
                group_has = any(self.thumbs.get(x["handle"]) for x in self.files if x["base"] == f["base"])
                if group_has:
                    continue
                if not self.cam_previews or not self.previews_ok:
                    self.thumb(f["handle"])  # solo anteprime dei file gia' sul Mac
                    continue
                while self.queue or self.current:  # i download hanno la precedenza
                    time.sleep(0.5)
                    if self.stop:
                        return
                if not self.thumb(f["handle"]):
                    # riprova con l'altro file dello stesso scatto (RAF/JPG)
                    alt = [x for x in self.files if x["base"] == f["base"] and x["handle"] != f["handle"]]
                    if not (alt and self.thumb(alt[0]["handle"])):
                        missing += 1
            if not missing or self.usb is None:
                return
            time.sleep(2 + rnd * 2)

    def _read_camera_meta(self):
        """Firmware, numero di serie e scatti, dalla foto piu' recente sulla scheda."""
        try:
            # i video non hanno EXIF: prendo la foto (JPG o RAF) piu' recente, con un paio di riserve
            files = sorted((x for x in self.files if x["kind"] in ("JPG", "RAF")),
                           key=lambda f: (f["date"], f["kind"] == "JPG"), reverse=True)
            for f in files[:3]:
                if self._camera_meta_from(f):
                    return
        except Exception as e:  # noqa: BLE001
            self.log.info("Dati della fotocamera non disponibili: %r" % (e,))

    def _camera_meta_from(self, f):
        try:
            data = b""
            if self.usb is not None:
                if f["name"].upper().endswith(".RAF"):
                    head = self.usb.read(f["handle"], 0, 0x60) or b""
                    loc = fw.jpeg_from_raf_head(head)
                    if loc:
                        data = self.usb.read(f["handle"], loc[0], min(0x20000, loc[1])) or b""
                else:
                    data = self.usb.read(f["handle"], 0, 0x20000) or b""
            elif self.cam is not None:
                with self.lock:
                    data = self.cam.read_head(f["handle"], f["name"])
                    self.last_activity = time.time()
            self._set_meta(f, data)
            meta = fw.camera_info_from_jpeg(data)
            if meta:
                meta["from"] = f["name"]
                with self.state_lock:
                    self.camera_meta = meta
                self.log.info("Dati fotocamera (da %s): %s" % (f["name"], meta))
                return True
        except Exception as e:  # noqa: BLE001
            self.log.info("Dati della fotocamera da %s non disponibili: %r" % (f["name"], e))
        return False

    def _shifted(self, d):
        """Ora di un file corretta con lo scarto misurato sull'EXIF (vedi _align_dates)."""
        if not self.date_shift or not d:
            return d or ""
        try:
            dt = datetime.datetime.strptime(d[:15], "%Y%m%dT%H%M%S") + datetime.timedelta(seconds=self.date_shift)
        except (ValueError, TypeError):
            return d
        return dt.strftime("%Y%m%dT%H%M%S")

    def _align_dates(self, f, exif_date):
        """L'ora che la fotocamera dichiara per i file puo' non essere quella di scatto (EXIF).
        X-Pro3 in Wi-Fi diretto, 5-6 nov 2026: la 147 risultava alle 13:00, mentre la fotocamera
        e l'EXIF dicono 15:00. Misuro lo scarto su una foto e lo applico a tutti i file,
        arrotondato al quarto d'ora, cosi' l'ora e' la stessa in Wi-Fi, via cavo, su Mac e su Linux."""
        try:
            e = datetime.datetime.strptime((exif_date or "")[:19], "%Y:%m:%d %H:%M:%S")
            d = datetime.datetime.strptime((f.get("date") or "")[:15], "%Y%m%dT%H%M%S")
        except (ValueError, TypeError):
            return
        extra = int(round((e - d).total_seconds() / 900.0)) * 900
        if not extra:
            return
        self.date_shift += extra
        self.log.info("Ora dei file corretta di %+d minuti, come nell'EXIF di %s" % (self.date_shift // 60, f["name"]))
        delta = datetime.timedelta(seconds=extra)
        with self.state_lock:
            seen = set()
            for x in list(self.files) + list(getattr(self, "_usb_files", []) or []):
                if id(x) in seen:
                    continue
                seen.add(id(x))
                try:
                    nd = datetime.datetime.strptime(x["date"][:15], "%Y%m%dT%H%M%S") + delta
                except (ValueError, TypeError, KeyError):
                    continue
                x["date"] = nd.strftime("%Y%m%dT%H%M%S")
                x["date_text"] = iso_to_text(x["date"])
            self.files = sorted(self.files, key=lambda x: (x["date"], x["base"], x["kind"]), reverse=True)

    def local_thumb(self, name, f=None):
        """Anteprima ricavata da un file gia' scaricato sul Mac."""
        p = os.path.join(self.dir_for(f) if f else self.dest, name)
        if not os.path.exists(p):
            return None
        try:
            with open(p, "rb") as fh:
                head = fh.read(0x80000)
                base = 0
                if head[:15] == b"FUJIFILMCCD-RAW":
                    base = struct.unpack(">I", head[84:88])[0]
                    fh.seek(base)
                    head = fh.read(0x80000)
                th, _ = fw.exif_thumbnail(head)
                return th
        except (OSError, struct.error):
            return None

    def group_thumb(self, f):
        # per lo scatto: prima il JPG sul Mac, poi il RAF sul Mac
        for x in self.files:
            if x["base"] == f["base"] and x.get("on_mac"):
                th = self.local_thumb(x["name"], x)
                if th:
                    return th
        return None

    def thumb(self, handle):
        if self.thumbs.get(handle):
            return self.thumbs[handle]
        f = next((x for x in self.files if x["handle"] == handle), None)
        if f is None:
            return None
        local = self.group_thumb(f)
        if local:
            self.thumbs[handle] = local
            return local
        if self.usb is not None:
            if self.thumb_tries.get(handle, 0) >= 5:
                return None
            self.thumb_tries[handle] = self.thumb_tries.get(handle, 0) + 1
            try:
                data = self.usb.thumbnail(handle)
            except Exception as e:  # noqa: BLE001
                self.log.debug("anteprima usb %d: %r" % (handle, e))
                data = None
            if data:
                self.thumbs[handle] = data   # i fallimenti non si memorizzano: si riprova
            return data
        if not self.previews_ok or not self.cam_previews or self.cam is None:
            return None
        try:
            with self.lock:
                data = self.cam.preview(handle, f["name"])
                self.last_activity = time.time()
            if f["base"] not in self.meta and getattr(self.cam, "last_head", b""):
                self._set_meta(f, self.cam.last_head)
        except Exception as e:  # noqa: BLE001
            self.log.info("Anteprima %d non riuscita (%r): disattivo le anteprime per questa sessione" % (handle, e))
            self.previews_ok = False
            self._lost(e)
            data = None
        self.thumbs[handle] = data
        return data

    # ------------------------------------------------------------ anteprima grande
    BIG_KEEP = 24   # quante anteprime grandi tenere in memoria (~5-14 MB l'una)

    def big_source(self, handle):
        """Sceglie il file da cui ricavare l'immagine grande per lo scatto di `handle`.
        Sul Mac o via cavo: il JPG originale (piena risoluzione), altrimenti il JPEG dentro il RAF.
        Via Wi-Fi: prima il JPEG dentro il RAF (4416 px, circa un terzo del JPG), per fare prima."""
        f = next((x for x in self.files if x["handle"] == handle), None)
        if f is None:
            return None
        group = {x["kind"]: x for x in self.files if x["base"] == f["base"]}
        jpg, raf, hif = group.get("JPG"), group.get("RAF"), group.get("HIF")
        if not jpg and not raf and not hif:
            return None   # video: niente foto grande
        for x in (jpg, raf):
            if x and x.get("on_mac") and os.path.exists(os.path.join(self.dir_for(x), x["name"])):
                return x
        if self.usb is not None:
            return jpg or raf or (hif if hasattr(self.usb, "heif_jpeg") else None)
        return raf or jpg

    @staticmethod
    def _jpeg_of_raf(read):
        head = read(0, 0x60)
        if not head or head[:15] != b"FUJIFILMCCD-RAW":
            return None
        off, ln = struct.unpack(">II", head[84:92])
        return read(off, ln)

    def big_image(self, handle):
        """(stato, bytes, info). stato: ok, busy, stale, none."""
        src = self.big_source(handle)
        if src is None:
            return "none", None, {}
        key = src["handle"]
        info = {"name": src["name"], "kind": src["kind"]}
        if key in self.big:
            return "ok", self.big[key], info
        self.big_want = key
        with self.big_lock:
            if key in self.big:
                return "ok", self.big[key], info
            if self.big_want != key:
                return "stale", None, info   # nel frattempo l'utente e' passato a un'altra foto
            t0 = time.time()
            try:
                data = self._big_fetch(src)
            except _Busy:
                return "busy", None, info
            except Exception as e:  # noqa: BLE001
                self.log.info("Anteprima grande di %s non riuscita: %r" % (src["name"], e))
                data = None
            if not data or data[:2] != b"\xff\xd8":
                return "none", None, info
            self.log.debug("Anteprima grande %s: %s in %.1f s" % (src["name"], fw.human(len(data)), time.time() - t0))
            self.big[key] = data
            self.big_order.append(key)
            while len(self.big_order) > self.BIG_KEEP:
                self.big.pop(self.big_order.pop(0), None)
            return "ok", data, info

    def _big_fetch(self, f):
        name = f["name"]
        is_raf = f["kind"] == "RAF"
        local = os.path.join(self.dir_for(f), name)
        if f.get("on_mac") and os.path.exists(local):
            with open(local, "rb") as fh:
                if not is_raf:
                    return fh.read()

                def rd(off, ln):
                    fh.seek(off)
                    return fh.read(ln)
                return self._jpeg_of_raf(rd)
        if self.usb is not None:
            if f["kind"] == "HIF":
                return self.usb.heif_jpeg(f["handle"], 2560)   # HEIF -> JPEG con gli strumenti del sistema
            def rd(off, ln):
                return self.usb.read(f["handle"], off, ln, timeout=60)
            if is_raf:
                return self._jpeg_of_raf(rd)
            return rd(0, f.get("size") or 0) if f.get("size") else None
        cam = self.cam
        if cam is None:
            return None
        if self.current or self.queue:
            raise _Busy()   # via Wi-Fi una cosa alla volta: prima finiscono i download
        h = f["handle"]
        with self.lock:
            cam.get_events()
            cam.set_prop16(fw.P_CompressSmall, 2, check=False)
            cam.correct_size_on()
            info = cam.object_info(h, timeout=30)
            size = (info or {}).get("size") or 0
            end = [0]

            def rd(off, ln):
                out = bytearray()
                while len(out) < ln:
                    d = cam.partial(h, off + len(out), min(fw.MAX_CHUNK, ln - len(out)), timeout=60)
                    if not d:
                        break
                    out += d
                end[0] = max(end[0], off + len(out))
                self.last_activity = time.time()
                return bytes(out)
            try:
                return self._jpeg_of_raf(rd) if is_raf else (rd(0, size) if size else None)
            finally:
                # X-Pro3 in AutoSave: se il file non e' stato letto fino in fondo, leggo la coda
                # per "chiuderlo" (vedi FujiCamera.preview), altrimenti non accetta altri comandi.
                if cam.autosave and size > 0x1000 and end[0] < size:
                    try:
                        cam.partial(h, size - 0x1000, 0x1000, timeout=15)
                    except Exception:  # noqa: BLE001
                        pass
                self._finish_props()

    # ------------------------------------------------------------ download
    def _free_name(self, name, taken, d=None):
        d = d or self.dest
        base, ext = os.path.splitext(name)
        n = 1
        cand = name
        while os.path.exists(os.path.join(d, cand)) or os.path.join(d, cand) in taken:
            cand = "%s_%d%s" % (base, n, ext)
            n += 1
        return cand

    def check(self, handles):
        """Per i file scelti, controlla se nella cartella esiste gia' un file con lo stesso nome."""
        out = []
        taken = set()
        for h in handles:
            f = next((x for x in self.files if x["handle"] == h), None)
            if not f:
                continue
            d = self.dir_for(f)
            p = os.path.join(d, f["name"])
            if not os.path.exists(p):
                taken.add(p)
                continue
            lsize = os.path.getsize(p)
            ldate = local_capture_date(p)
            same_size = f["size"] is not None and lsize == f["size"]
            same_date = ldate is not None and _close_dates(ldate, f["date"] or "")
            if same_size and (same_date or ldate is None):
                kind = "same"
            elif f["size"] is None and same_date:
                kind = "same"
            else:
                kind = "different"
            prop = self._free_name(f["name"], taken, d)
            taken.add(os.path.join(d, prop))
            out.append({"handle": h, "name": f["name"], "kind": kind, "proposed": prop,
                        "local_size": lsize, "cam_size": f["size"], "folder": d,
                        "local_date": (ldate or "")[:15], "cam_date": (f["date"] or "")[:15]})   # ISO: la UI li traduce
        return out

    def enqueue(self, handles, options=None):
        """options: {handle: {"action": "skip"|"overwrite"|"rename", "name": "..."}}"""
        options = options or {}
        added = 0
        with self.state_lock:
            self.pending_names = []
            queued = {q["handle"] for q in self.queue}
            for h in handles:
                f = next((x for x in self.files if x["handle"] == h), None)
                if not f or h in queued or (self.current and self.current["handle"] == h):
                    continue
                opt = options.get(str(h)) or options.get(h) or {}
                act = opt.get("action", "new")
                if act == "skip":
                    self.log.info("Non scaricato (scelta dell'utente: gia' presente): %s" % f["name"])
                    continue
                item = dict(f)
                item["_action"] = act
                if act == "rename":
                    nm = os.path.basename(str(opt.get("name") or "")).strip()
                    if not nm or nm.startswith("."):
                        nm = self._free_name(f["name"], set(), self.dir_for(f))
                    if not os.path.splitext(nm)[1]:
                        nm += os.path.splitext(f["name"])[1]
                    item["_target"] = nm
                self.queue.append(item)
                added += 1
            self.cancel = False
        return added

    def worker(self):
        while not self.stop:
            if not self.queue or (self.cam is None and self.usb is None) or self.status != "ready":
                time.sleep(0.3)
                continue
            with self.state_lock:
                f = self.queue.pop(0)
                self.current = {"handle": f["handle"], "name": f["name"], "got": 0,
                                "total": f["size"] or 0, "speed": 0}
            try:
                path, skipped = self._download_usb(f) if self.usb else self._download(f)
                with self.state_lock:
                    self.done.append({"name": os.path.basename(path), "path": path, "skipped": skipped})
                    orig = next((x for x in self.files if x["handle"] == f["handle"]), f)
                    orig["on_mac"] = True
                    f = orig
                    for x in self.files:
                        if x["base"] == f["base"]:
                            x["on_mac"] = x["on_mac"] or x["handle"] == f["handle"]
                            if not self.thumbs.get(x["handle"]):
                                self.thumbs.pop(x["handle"], None)
                for x in self.files:
                    if x["base"] == f["base"]:
                        self.thumb(x["handle"])
                if self.cancel:
                    with self.state_lock:
                        n = len(self.queue)
                        self.queue = []
                    self.log.info("Download annullato dopo %s: %d file non scaricati" % (f["name"], n))
            except _Cancelled:
                self.log.info("Download annullato")
                with self.state_lock:
                    self.queue = []
            except Exception as e:  # noqa: BLE001
                self.log.info("Download %s interrotto: %s" % (f["name"], e))
                if self.choice.get("method") in ("cable", "card"):
                    for _ in range(15):   # il distacco del cavo arriva come evento poco dopo l'errore
                        if self.status != "ready" or self.usb is None:
                            break
                        time.sleep(0.1)
                    if self.status != "ready" or self.usb is None:
                        with self.state_lock:
                            if f["name"] not in self.pending_names:
                                self.pending_names.insert(0, f["name"])
                        continue
                with self.state_lock:
                    f["tries"] = f.get("tries", 0) + 1
                    lost = isinstance(e, (OSError, socket.timeout)) or "chiuso la connessione" in str(e)
                    if f["tries"] < 3 and lost:   # L4, 6 nov 2026: fotocamera spenta durante il download
                        self.queue.insert(0, f)  # riprovo dopo il ricollegamento
                    else:
                        self.failed.append({"name": f["name"], "error": str(e)})
                self._lost(e)
            finally:
                with self.state_lock:
                    self.current = None
                if not self.queue and self._group_cam is not None:
                    self._finish_props()   # fine della coda: rispengo D227 una volta sola

    def _download(self, f):
        cam = self.cam
        h = f["handle"]
        with self.lock:
            self._prepare_group(cam)
            info = cam.object_info(h, timeout=30)
        if info is None:
            raise fw.FujiError("informazioni non disponibili")
        total = info["size"]
        name = f.get("_target") or info["filename"] or f["name"]
        action = f.get("_action", "new")
        d = self.dir_for(f)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, name)
        if os.path.exists(path) and action != "overwrite":
            # caso non previsto dal controllo iniziale: mai sovrascrivere senza permesso
            path = os.path.join(d, self._free_name(name, set(), d))
        tmp = path + ".part"
        got = 0
        t0 = time.time()
        try:
            with open(tmp, "wb") as out:
                while got < total:
                    if self.cancel:
                        raise _Cancelled()
                    want = min(fw.MAX_CHUNK, total - got)
                    with self.lock:
                        d = cam.partial(h, got, want)
                        self.last_activity = time.time()
                    if not d:
                        raise fw.FujiError("la fotocamera ha inviato 0 byte")
                    out.write(d)
                    got += len(d)
                    el = max(time.time() - t0, 0.001)
                    with self.state_lock:
                        if self.current:
                            self.current.update({"got": got, "total": total, "speed": got / el})
            os.replace(tmp, path)  # sostituisce solo se hai scelto "Sovrascrivi"
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
        finally:
            try:
                with self.lock:
                    cam.get_events()
            except Exception:  # noqa: BLE001
                pass
        self.log.info("Scaricato %s (%s in %.1f s)" % (path, fw.human(total), time.time() - t0))
        return path, False

    def _prepare_group(self, cam):
        """D226 (file originale) e D227 (dimensione vera) una volta sola per coda di download,
        con la pausa prima di D227. Verificato il 6 nov 2026 (X-Pro3, Wi-Fi diretto): con D227
        acceso una volta, 4 JPG di fila arrivano tutti interi. D227 si rispegne a fine coda."""
        cam.get_events()
        if self._group_cam is cam:
            return
        cam.set_prop16(fw.P_CompressSmall, 2, check=False)
        cam.correct_size_on()
        self._group_cam = cam

    def _finish_props(self):
        self._group_cam = None
        try:
            with self.lock:
                self.cam.get_events()
                if not self.cam.autosave:
                    self.cam.set_prop16(fw.P_CorrectFileSize, 0, check=False)
        except Exception:
            pass

    # ------------------------------------------------------------ manutenzione
    def _lost(self, err):
        if self.usb is not None:
            return
        if isinstance(err, (OSError, socket.timeout)) or "chiuso la connessione" in str(err):
            self._close_cam()
            with self.state_lock:
                if self.current is None and self.queue:
                    pass  # la coda resta: ripartira' dopo il ricollegamento
            if self.abort or self.status == "setup":
                return
            self.set_status("waiting", "lost_direct" if self.wireless else "lost_home")
            if not self.stop:
                threading.Thread(target=lambda: (time.sleep(1), self.start_connect()), daemon=True).start()

    def watch_folder(self):
        """Ogni 3 s ricontrolla quali file sono gia' nella cartella di destinazione, cosi' i segni di spunta
        restano giusti anche se la cartella viene rinominata o svuotata mentre Provino e' aperto."""
        while not self.stop:
            time.sleep(3)
            if self.status != "ready" or not self.files:
                continue
            try:
                with self.state_lock:
                    for f in self.files:
                        f["on_mac"] = self._on_mac(f["name"], f.get("size"), f)
            except Exception as e:  # noqa: BLE001
                self.log.debug("controllo cartella: %r" % (e,))

    def keepalive(self):
        while not self.stop:
            time.sleep(2)
            if self.cam is None or self.status != "ready":
                continue
            if time.time() - self.last_activity < 8:
                continue
            try:
                with self.lock:
                    self.cam.get_events()
                    self.last_activity = time.time()
            except Exception as e:  # noqa: BLE001
                self._lost(e)

    def shutdown(self):
        self.stop = True
        self._close_cam()
        if self.usb:
            try:
                self.usb.stop()
            except Exception:
                pass


class _Busy(Exception):
    pass


class _Cancelled(Exception):
    pass


# ---------------------------------------------------------------- server web
def make_handler(app):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json", headers=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store" if ctype != "image/jpeg" else "max-age=3600")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                return json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return {}

        def _local_only(self):
            """Difesa contro siti esterni (DNS rebinding, richieste da altre pagine): solo 127.0.0.1/localhost."""
            from urllib.parse import urlsplit
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
            if host not in ("127.0.0.1", "localhost"):
                self._send(403, {"error": "host non ammesso"})
                return False
            origin = self.headers.get("Origin") or ""
            if origin and origin != "null":
                try:
                    oh = (urlsplit(origin).hostname or "").lower()
                except ValueError:
                    oh = ""
                if oh not in ("127.0.0.1", "localhost"):
                    self._send(403, {"error": "origine non ammessa"})
                    return False
            return True

        def do_GET(self):
            if not self._local_only():
                return
            static = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/index.html": ("index.html", "text/html; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"),
                      "/icon.png": ("icon.png", "image/png")}
            if self.path in static:
                name, ctype = static[self.path]
                with open(os.path.join(HERE, "web", name), "rb") as fh:
                    return self._send(200, fh.read(), ctype)
            if self.path == "/api/cameras":
                with open(CAMERAS_PATH, "rb") as fh:
                    return self._send(200, fh.read(), "application/json")
            if self.path == "/api/devices":
                return self._send(200, connected_devices())
            if self.path == "/api/state":
                st = app.snapshot()
                st["platform"] = sys.platform   # la UI disattiva il cavo dove non c'e' ancora
                return self._send(200, st)
            if self.path.startswith("/api/thumb/"):
                try:
                    h = int(self.path.rsplit("/", 1)[1].split("?")[0])
                except ValueError:
                    return self._send(400, {"error": "handle"})
                data = app.thumb(h)
                if data:
                    return self._send(200, data, "image/jpeg")
                return self._send(404, {"error": "nessuna anteprima"})
            if self.path == "/api/meta":
                with app.state_lock:
                    return self._send(200, dict(app.meta))
            if self.path.startswith("/api/meta/"):
                try:
                    h = int(self.path.rsplit("/", 1)[1].split("?")[0])
                except ValueError:
                    return self._send(400, {"error": "handle"})
                f = next((x for x in app.files if x["handle"] == h), None)
                m = app.shot_meta(f) if f else None
                return self._send(200 if m else 404, m or {"error": "nessun metadato"})
            if self.path.startswith("/api/big/"):
                try:
                    h = int(self.path.rsplit("/", 1)[1].split("?")[0])
                except ValueError:
                    return self._send(400, {"error": "handle"})
                st, data, info = app.big_image(h)
                if st == "ok":
                    return self._send(200, data, "image/jpeg", {"X-Provino-Source": info.get("kind", "")})
                return self._send(409 if st in ("busy", "stale") else 404, {"error": st})
            return self._send(404, {"error": "non trovato"})

        def do_POST(self):
            # accetta richieste solo dalla pagina locale
            if not self._local_only():
                return
            body = self._json()
            if self.path == "/api/start":
                cam = body.get("camera")
                method = body.get("method")
                profiles = load_cameras()["cameras"]
                if cam not in profiles or method not in profiles[cam].get("methods", []):
                    return self._send(400, {"error": "combinazione non disponibile"})
                threading.Thread(target=app.choose, args=(cam, method), daemon=True).start()
                return self._send(200, {"ok": True})
            if self.path == "/api/dest-settings":
                d = body.get("dest")
                if d is not None:
                    d = os.path.expanduser(str(d)).strip()
                    if not d or not os.path.isabs(d):
                        return self._send(400, {"error": app.tr("Scegli una cartella valida.", "Choose a valid folder.")})
                    try:
                        os.makedirs(d, exist_ok=True)
                    except OSError as e:
                        return self._send(400, {"error": app.tr("Non riesco a usare questa cartella: %s", "I can't use this folder: %s") % e})
                    app.dest = d
                    app.settings["dest"] = d
                for k in ("split_type", "by_date", "ask_dest"):
                    if k in body:
                        app.settings[k] = bool(body[k])
                app.save_settings()
                app.refresh_on_mac()
                return self._send(200, {"settings": app.settings, "dest": app.dest})
            if self.path == "/api/choose-folder":
                path = choose_folder(app.dest, app.tr("Dove scarico le foto?", "Where should I download the photos?"))
                return self._send(200, {"path": path})
            if self.path == "/api/ui-lang":
                if body.get("lang") in ("it", "en"):
                    app.settings["ui_lang"] = body["lang"]
                    app.save_settings()
                return self._send(200, {"settings": app.settings})
            if self.path == "/api/menu-lang":
                cam = body.get("camera")
                lang = body.get("lang")
                if cam in load_cameras()["cameras"] and lang in ("it", "en"):
                    app.settings.setdefault("menu_lang", {})[cam] = lang
                    app.save_settings()
                return self._send(200, {"settings": app.settings})
            if self.path == "/api/stop":
                threading.Thread(target=app.stop_session, daemon=True).start()
                return self._send(200, {"ok": True})
            if self.path == "/api/register":
                app.choice = {"camera": body.get("camera") or "X-Pro3", "method": "home"}
                app.register()
                return self._send(200, {"ok": True})
            if self.path == "/api/xacquire":
                return self._send(200, {"running": xacquire_running()})
            if self.path == "/api/xacquire-quit":
                return self._send(200, {"closed": xacquire_quit(), "running": xacquire_running()})
            if self.path == "/api/open-imagecapture":
                try:
                    if sys.platform == "darwin":
                        subprocess.Popen(["open", "-a", "Image Capture"])
                except Exception:
                    pass
                return self._send(200, {"ok": True})
            if self.path == "/api/check":
                return self._send(200, {"conflicts": app.check([int(x) for x in body.get("handles", [])])})
            if self.path == "/api/download":
                n = app.enqueue([int(x) for x in body.get("handles", [])], body.get("options") or {})
                return self._send(200, {"queued": n})
            if self.path == "/api/cancel":
                app.cancel = True
                return self._send(200, {"ok": True})
            if self.path == "/api/reconnect":
                app.start_connect()
                return self._send(200, {"ok": True})
            if self.path == "/api/open-folder":
                last = app.done[-1]["path"] if app.done and app.done[-1].get("path") else ""
                try:
                    if sys.platform == "darwin" and last and os.path.exists(last):
                        subprocess.Popen(["open", "-R", last])   # Finder sull'ultimo file scaricato
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", app.dest])
                    elif sys.platform.startswith("win"):
                        os.startfile(app.dest)  # noqa
                    else:
                        subprocess.Popen(["xdg-open", app.dest])
                except Exception:
                    pass
                return self._send(200, {"ok": True})
            if self.path == "/api/quit":
                self._send(200, {"ok": True})
                def _quit():
                    time.sleep(0.3)
                    app.log.info("Chiusura richiesta (un'altra copia di Provino si e' aperta).")
                    app.shutdown()
                    app.log.info("Chiuso.")
                    app.log.close()
                    os._exit(0)
                threading.Thread(target=_quit, daemon=True).start()
                return None
            return self._send(404, {"error": "non trovato"})

    return H





def close_old_instances(log):
    """Se Provino e' gia' aperto in un'altra finestra, lo chiude: due copie insieme
    si rubano i messaggi della fotocamera e il collegamento non parte."""
    import urllib.request
    closed = 0
    for p in range(8765, 8795):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/state" % p, timeout=0.3) as r:
                if b'"version"' not in r.read(4096):
                    continue
            req = urllib.request.Request("http://127.0.0.1:%d/api/quit" % p, data=b"{}",
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=1).read()
            closed += 1
        except Exception:
            continue
    if closed:
        log.info("Chiusa una copia di Provino gia' aperta.")
        time.sleep(1.5)


def free_port(start=8765):
    for p in range(start, start + 30):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            s.close()
    raise OSError("nessuna porta libera")


def main():
    ap = argparse.ArgumentParser(description="Provino - scegli e scarica le foto dalle fotocamere Fujifilm")
    ap.add_argument("--wireless", action="store_true", help="usa la rete Wi-Fi della fotocamera (solo JPG)")
    ap.add_argument("--ip", default=fw.CAM_IP)
    ap.add_argument("--dest", default=default_dest())
    ap.add_argument("--auto", action="store_true", help="salta la scelta iniziale: X-Pro3 via rete di casa")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.dest, exist_ok=True)
    logdir = os.path.join(DATA, "log")
    os.makedirs(logdir, exist_ok=True)
    logpath = os.path.join(logdir, "app_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    log = fw.Log(logpath, verbose=args.verbose)
    log.info("Provino %s (modulo %s) - Python %s - %s" % (APP_VERSION, fw.VERSION, sys.version.split()[0], sys.platform))

    close_old_instances(log)
    app = App(args.dest, args.wireless, args.ip, log)
    port = args.port or free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    srv.daemon_threads = True
    threading.Thread(target=app.worker, daemon=True).start()
    threading.Thread(target=app.keepalive, daemon=True).start()
    threading.Thread(target=app.watch_folder, daemon=True).start()
    if args.wireless:
        app.choose("X-Pro3", "direct")
    elif args.auto:
        app.choose("X-Pro3", "home")
    url = "http://127.0.0.1:%d/" % port
    log.info("Interfaccia: %s" % url)
    pf = os.environ.get("PROVINO_PORT_FILE")   # app per Mac: la finestra legge qui la porta
    if pf:
        try:
            with open(pf + ".tmp", "w") as fh:
                fh.write(str(port))
            os.replace(pf + ".tmp", pf)
        except OSError as e:
            log.info("Non riesco a scrivere la porta in %s: %s" % (pf, e))
    log.info("Per chiudere: chiudi questa finestra del Terminale (o premi Ctrl+C).")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    # Chiudere la finestra del Terminale manda SIGHUP: senza questo Provino morirebbe senza salutare
    # la fotocamera, e una X-Pro3 in Wi-Fi resterebbe "collegata" (e puo' non spegnersi).
    import signal

    def _bye(signum, frame):
        log.info("Chiusura (segnale %d): chiudo il collegamento con la fotocamera." % signum)
        try:
            app.shutdown()
        finally:
            log.info("Chiuso.")
            log.close()
            os._exit(0)
    for sig in (getattr(signal, "SIGHUP", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            signal.signal(sig, _bye)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()
        log.info("Chiuso.")
        log.close()


if __name__ == "__main__":
    main()
