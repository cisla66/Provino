#!/usr/bin/env python3
"""
Provino - lettore di schede SD (macOS e Linux).

La scheda nel lettore il sistema la monta come un disco con la cartella DCIM.
Qui la si legge SOLTANTO: i file si aprono in sola lettura, sulla scheda non si
scrive, non si sposta e non si cancella nulla.

Stessa interfaccia di fuji_usb.UsbSession / fuji_usb_linux.UsbSession, cosi' provino.py
la usa come il cavo: eventi -> callback (device, session, file, ready, removed, progress, error),
comandi -> metodi (thumbnail, read, download, stop).

Provato il 6 nov 2026 con una scheda della X-Pro3 (DCIM/130_FUJI, nomi _DSF0153.*) sul Mac.
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time

READ_CHUNK = 1 << 20
MEDIA = (".JPG", ".JPEG", ".RAF", ".MOV", ".MP4", ".HIF")
PHOTO = (".JPG", ".JPEG", ".RAF", ".HIF")


class CardError(Exception):
    pass


def _exif_date(buf):
    """DateTimeOriginal (o DateTime) dall'inizio di un JPEG -> 'YYYYMMDDTHHMMSS' o None."""
    m = re.search(rb"(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})\x00", buf[:0x10000])
    return (b"%s%s%sT%s%s%s" % m.groups()).decode() if m else None


def _exif_model(buf):
    """Modello della fotocamera dall'EXIF (es. 'X-Pro3'), se si trova."""
    m = re.search(rb"FUJIFILM\x00+((?:X|GFX)[\w\- ]{1,20}?)\x00", buf[:0x10000])
    return m.group(1).decode("ascii", "ignore").strip() if m else None


def _raf_jpeg_loc(head):
    """Posizione del JPEG di anteprima dentro un RAF (offset, lunghezza) o None."""
    if len(head) < 92 or head[:15] != b"FUJIFILMCCD-RAW":
        return None
    off, ln = struct.unpack(">II", head[84:92])
    return (off, ln) if off and ln else None


def mount_roots():
    """Cartelle dove il sistema monta le schede."""
    if sys.platform == "darwin":
        return ["/Volumes"]
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    return [p for p in ("/run/media/" + user, "/media/" + user, "/media") if p and os.path.isdir(p)]


def find_cards():
    """Volumi montati con una cartella DCIM che contiene foto. -> [percorso del volume]"""
    out = []
    for root in mount_roots():
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for n in names:
            vol = os.path.join(root, n)
            if n.startswith(".") or not os.path.isdir(os.path.join(vol, "DCIM")):
                continue
            if os.path.realpath(vol) == "/":
                continue   # il disco di sistema, mai
            out.append(vol)
    return out


def can_heif():
    """Il sistema sa trasformare un HEIF in JPEG? (sips sul Mac; su Linux GdkPixbuf con il modulo heif o heif-convert)"""
    if sys.platform == "darwin":
        return os.path.exists("/usr/bin/sips")
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        if any("heif" in (fmt.get_name() or "").lower() for fmt in GdkPixbuf.Pixbuf.get_formats()):
            return True
    except Exception:  # noqa: BLE001
        pass
    return bool(shutil.which("heif-convert"))


class CardSession:
    def __init__(self, base_dir, camera_hint, log, on_event, dest_dir=""):
        self.base_dir = base_dir
        self.log = log
        self.on_event = on_event
        self.dest_dir = dest_dir
        self.vol = None
        self.files = {}          # id -> (percorso, nome, dimensione)
        self.next_id = 1
        self.stopping = False
        self.lock = threading.RLock()
        self.camera_name = ""
        self.models = []         # modelli trovati sulla scheda (una scheda puo' avere foto di piu' fotocamere)
        self.heif_cache = {}     # (id, lato) -> JPEG

    # ------------------------------------------------------------ avvio e controllo
    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _emit(self, ev):
        try:
            self.on_event(ev)
        except Exception as e:  # noqa: BLE001
            self.log.debug("scheda callback: %r" % (e,))

    def _run(self):
        while not self.stopping:
            if self.vol is None:
                cards = find_cards()
                if cards:
                    vol = cards[0]
                    if self.dest_dir and os.path.realpath(self.dest_dir).startswith(os.path.realpath(vol) + os.sep):
                        self._emit({"event": "error", "message": "la cartella di destinazione e' sulla scheda"})
                        time.sleep(3)
                        continue
                    try:
                        self._publish(vol)
                    except OSError as e:
                        self.log.info("Scheda: lettura non riuscita: %s" % e)
                        self.vol = None
                time.sleep(1.5)
                continue
            time.sleep(1)
            if not os.path.isdir(os.path.join(self.vol, "DCIM")):
                self.log.info("Scheda tolta: %s" % self.vol)
                with self.lock:
                    self.vol = None
                    self.files = {}
                self._emit({"event": "removed"})

    def _walk(self, vol):
        dcim = os.path.join(vol, "DCIM")
        out = []
        for folder in sorted(os.listdir(dcim)):
            fp = os.path.join(dcim, folder)
            if folder.startswith(".") or not os.path.isdir(fp):
                continue
            for n in sorted(os.listdir(fp)):
                if n.startswith(".") or not n.upper().endswith(MEDIA):
                    continue
                p = os.path.join(fp, n)
                if os.path.isfile(p):
                    out.append((folder, n, p))
        return out

    def _head(self, path, length=0x10000):
        with open(path, "rb") as fh:
            head = fh.read(length)
            loc = _raf_jpeg_loc(head)
            if loc:
                fh.seek(loc[0])
                return fh.read(min(length, loc[1]))
            return head

    def _publish(self, vol):
        entries = self._walk(vol)
        label = os.path.basename(vol.rstrip("/"))
        heads = {}
        models = []
        for folder, n, p in entries:
            if n.upper().endswith(PHOTO):
                try:
                    heads[p] = self._head(p)
                except OSError:
                    continue
                m = _exif_model(heads[p])
                if m and m not in models:
                    models.append(m)
        model = models[0] if len(models) == 1 else ""
        with self.lock:
            self.vol = vol
            self.files = {}
            self.models = models
            self.heif_cache = {}
            self.camera_name = model or ("Scheda %s" % label)
        self.log.info("Scheda trovata: %s (%s), %d file" % (vol, ", ".join(models) or "modello sconosciuto", len(entries)))
        self._emit({"event": "device", "name": self.camera_name})
        self._emit({"event": "session", "name": self.camera_name})
        for folder, n, p in entries:
            try:
                st = os.stat(p)
            except OSError:
                continue
            date = _exif_date(heads[p]) if p in heads else None
            if not date:
                date = time.strftime("%Y%m%dT%H%M%S", time.localtime(st.st_mtime))
            with self.lock:
                fid = self.next_id
                self.next_id += 1
                self.files[fid] = (p, n, st.st_size)
            self._emit({"event": "file", "id": fid, "name": n, "size": st.st_size, "date": date,
                        "folder": "DCIM/" + folder})
        self._emit({"event": "ready", "count": len(entries), "name": self.camera_name, "volume": label})

    # ------------------------------------------------------------ comandi
    def _get(self, fid):
        with self.lock:
            return self.files.get(fid)

    def heif_jpeg(self, fid, side):
        """HEIF (.HIF della X100VI) -> JPEG con il lato lungo `side`, usando gli strumenti del sistema:
        sips sul Mac (sempre presente); su Linux heif-convert o GdkPixbuf, se installati. Altrimenti None."""
        f = self._get(fid)
        if not f:
            return None
        key = (fid, side)
        if key in self.heif_cache:
            return self.heif_cache[key]
        src, data = f[0], None
        tmpdir = tempfile.mkdtemp(prefix="provino_heif_")
        out = os.path.join(tmpdir, "x.jpg")
        try:
            if sys.platform == "darwin" and os.path.exists("/usr/bin/sips"):
                subprocess.run(["/usr/bin/sips", "-s", "format", "jpeg", "-s", "formatOptions", "82",
                                "-Z", str(side), src, "--out", out],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            else:
                try:
                    import gi
                    gi.require_version("GdkPixbuf", "2.0")
                    from gi.repository import GdkPixbuf
                    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(src, side, side, True)
                    pb.savev(out, "jpeg", ["quality"], ["82"])
                except Exception:  # noqa: BLE001
                    tool = shutil.which("heif-convert")
                    if tool and side <= 600 and shutil.which("heif-thumbnailer"):
                        png = os.path.join(tmpdir, "x.png")
                        subprocess.run(["heif-thumbnailer", "-s", str(side), src, png],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
                        out = png
                    elif tool:
                        subprocess.run([tool, "-q", "82", src, out],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if os.path.exists(out):
                with open(out, "rb") as fh:
                    data = fh.read()
                if not data.startswith(b"\xff\xd8"):
                    data = None   # (PNG da heif-thumbnailer: il browser lo mostra comunque come miniatura)
                    with open(out, "rb") as fh:
                        png = fh.read()
                    if png.startswith(b"\x89PNG") and side <= 600:
                        data = png
        except (OSError, subprocess.SubprocessError) as e:
            self.log.debug("HEIF %s: %r" % (f[1], e))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        if data:
            self.heif_cache[key] = data
        return data

    def thumbnail(self, fid, timeout=20):
        f = self._get(fid)
        if not f:
            return None
        if f[1].upper().endswith(".HIF"):
            return self.heif_jpeg(fid, 480)
        import fuji_wifi as fw
        try:
            with open(f[0], "rb") as fh:
                head = fh.read(0x80000)
                loc = _raf_jpeg_loc(head)
                if loc:
                    fh.seek(loc[0])
                    head = fh.read(min(0x80000, loc[1]))
            th, _ = fw.exif_thumbnail(head)
            return th
        except (OSError, struct.error) as e:
            self.log.debug("scheda miniatura %s: %r" % (f[1], e))
            return None

    def read(self, fid, offset, length, timeout=20):
        f = self._get(fid)
        if not f:
            return None
        try:
            with open(f[0], "rb") as fh:
                fh.seek(int(offset))
                return fh.read(int(length))
        except OSError as e:
            self.log.debug("scheda lettura %s: %r" % (f[1], e))
            return None

    def download(self, fid, dest_dir, name, overwrite, cancelled, timeout=900):
        """Copia il file in dest_dir/name (provino.py usa un nome .part e rinomina alla fine)."""
        f = self._get(fid)
        if not f:
            raise CardError("file sconosciuto")
        src, cname, size = f
        path = os.path.join(dest_dir, name)
        if os.path.exists(path) and not overwrite:
            raise CardError("esiste gia': %s" % name)
        got, last, t0 = 0, 0.0, time.time()
        try:
            with open(src, "rb") as inp, open(path, "wb") as out:
                while True:
                    data = inp.read(READ_CHUNK)
                    if not data:
                        break
                    out.write(data)
                    got += len(data)
                    if size and time.time() - last > 0.3:
                        last = time.time()
                        self._emit({"event": "progress", "id": fid, "fraction": got / float(size)})
                    if time.time() - t0 > timeout:
                        raise CardError("copia troppo lenta o bloccata")
        except OSError as e:
            raise CardError("scheda non leggibile (tolta?): %s" % e)
        if size and got != size:
            raise CardError("file incompleto (%d di %d byte)" % (got, size))
        self._emit({"event": "progress", "id": fid, "fraction": 1.0})
        return path

    def stop(self):
        self.stopping = True
        self._emit({"event": "exited"})
