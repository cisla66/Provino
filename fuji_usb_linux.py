"""
Provino - collegamento via cavo USB su Linux.

Usa libgphoto2, la libreria per fotocamere gia' presente nei sistemi Linux con GNOME (e' la
stessa che usa File per mostrare le fotocamere), chiamata direttamente da Python con ctypes:
nessun pacchetto da installare.

Ha le stesse funzioni e gli stessi eventi di fuji_usb.py (macOS, ImageCaptureCore), cosi'
provino.py non cambia: elenco dei file, miniature, letture parziali, download.

Fotocamera in modalita' "USB CARD READER" / "LETTORE SCHEDA USB", come sul Mac:
la X-Pro3 in questa modalita' si presenta a Linux come fotocamera PTP (verificato il
6 nov 2026 sul ThinkPad con Fedora 45: elenco, miniature, letture parziali e download).

SICUREZZA: questo modulo legge e copia soltanto. Non contiene nessuna chiamata che
cancella, carica o modifica file sulla scheda.
"""

import calendar
import ctypes as C
import ctypes.util
import glob
import os
import re
import struct
import subprocess
import threading
import time

GP_OK = 0
GP_ERROR_IO_USB_CLAIM = -53
GP_ERROR_MODEL_NOT_FOUND = -105
GP_FILE_TYPE_PREVIEW = 0
GP_FILE_TYPE_NORMAL = 1
READ_CHUNK = 0x100000   # 1 MB per lettura
P = C.c_void_p


class UsbError(Exception):
    pass


class _InfoPreview(C.Structure):
    _fields_ = [("fields", C.c_int), ("status", C.c_int), ("size", C.c_uint64), ("type", C.c_char * 64),
                ("width", C.c_uint32), ("height", C.c_uint32)]


class _InfoFile(C.Structure):
    _fields_ = [("fields", C.c_int), ("status", C.c_int), ("size", C.c_uint64), ("type", C.c_char * 64),
                ("width", C.c_uint32), ("height", C.c_uint32), ("permissions", C.c_int), ("mtime", C.c_long)]


class _InfoAudio(C.Structure):
    _fields_ = [("fields", C.c_int), ("status", C.c_int), ("size", C.c_uint64), ("type", C.c_char * 64)]


class _FileInfo(C.Structure):
    _fields_ = [("preview", _InfoPreview), ("file", _InfoFile), ("audio", _InfoAudio)]


class _CameraText(C.Structure):
    _fields_ = [("text", C.c_char * (32 * 1024))]


_lib = None


def _gp():
    global _lib
    if _lib is not None:
        return _lib
    name = ctypes.util.find_library("gphoto2") or "libgphoto2.so.6"
    try:
        g = C.CDLL(name)
    except OSError:
        raise UsbError("Manca la libreria libgphoto2. Su Fedora: sudo dnf install libgphoto2 ; "
                       "su Ubuntu: sudo apt install libgphoto2-6")
    g.gp_result_as_string.restype = C.c_char_p
    g.gp_context_new.restype = P
    g.gp_camera_file_read.argtypes = [P, C.c_char_p, C.c_char_p, C.c_int, C.c_uint64, C.c_char_p,
                                      C.POINTER(C.c_uint64), P]
    g.gp_file_get_data_and_size.argtypes = [P, C.POINTER(C.c_void_p), C.POINTER(C.c_ulong)]
    g.gp_camera_file_get_info.argtypes = [P, C.c_char_p, C.c_char_p, C.POINTER(_FileInfo), P]
    _lib = g
    return g


def _err(code):
    try:
        return _gp().gp_result_as_string(code).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return str(code)


def release_from_gnome(log=None):
    """GNOME (gvfs) tiene occupata la fotocamera per mostrarla in File: la lascio andare.
    Equivale a premere "Espelli" sulla fotocamera nella barra di File. Non tocca la scheda."""
    try:
        subprocess.run(["gio", "mount", "-s", "gphoto2"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=10)
        return True
    except Exception as e:  # noqa: BLE001
        if log:
            log.debug("gio mount -s gphoto2: %r" % (e,))
        return False


def _exif_date(buf):
    """DateTimeOriginal (o DateTime) da un JPEG -> 'YYYYMMDDTHHMMSS' o None."""
    m = re.search(rb"(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})\x00", buf[:0x10000])
    return (b"%s%s%sT%s%s%s" % m.groups()).decode() if m else None


class UsbSession:
    """Stessa interfaccia di fuji_usb.UsbSession (macOS): eventi -> callback, comandi -> metodi."""

    def __init__(self, base_dir, camera_hint, log, on_event):
        self.base_dir = base_dir
        self.camera_hint = (camera_hint or "").lower().replace("-", "")
        self.others = []   # le altre fotocamere supportate (le salto se collegate insieme)
        self.log = log
        self.on_event = on_event
        self.g = None
        self.ctx = None
        self.cam = None
        self.lock = threading.RLock()     # libgphoto2 non regge chiamate da piu' thread insieme
        self.files = {}                   # id -> (cartella, nome, dimensione)
        self.next_id = 1
        self.stopping = False
        self.last_use = 0.0
        self.tz_shift = None              # correzione dell'ora dei file (vedi _date_of)

    # ------------------------------------------------------------ avvio e monitor
    def start(self):
        self.g = _gp()
        self.ctx = P(self.g.gp_context_new())
        threading.Thread(target=self._run, daemon=True).start()

    def _emit(self, ev):
        try:
            self.on_event(ev)
        except Exception as e:  # noqa: BLE001
            self.log.debug("usb callback: %r" % (e,))

    def _run(self):
        warned = False
        while not self.stopping:
            if self.cam is None:
                code = self._open()
                if code == GP_OK:
                    warned = False
                    try:
                        self._publish()
                    except UsbError as e:
                        self.log.info("Cavo USB: elenco non riuscito: %s" % e)
                        self._close()
                        continue
                elif code == GP_ERROR_IO_USB_CLAIM and not warned:
                    self.log.info("Cavo USB: fotocamera occupata da GNOME, la libero e riprovo")
                    warned = True
                time.sleep(2)
                continue
            time.sleep(1)
            if self.cam is not None and not self.usb_present():
                self.log.info("Cavo USB: la fotocamera non e' piu' sul bus USB")
                with self.lock:
                    self._close()
                self._emit({"event": "removed"})
                continue
            # controllo che la fotocamera risponda (solo quando nessuno la sta usando)
            if time.time() - self.last_use < 3 or not self.lock.acquire(blocking=False):
                continue
            alive = True
            try:
                if self.cam is None:
                    continue
                alive = self._alive_locked()
                if not alive:
                    self.log.info("Cavo USB: fotocamera non piu' raggiungibile")
                    self._close()
            finally:
                self.lock.release()
            if not alive:
                self._emit({"event": "removed"})

    def _open(self):
        g = self.g
        cam = P()
        g.gp_camera_new(C.byref(cam))
        rc = g.gp_camera_init(cam, self.ctx)
        if rc == GP_ERROR_IO_USB_CLAIM:
            release_from_gnome(self.log)
            time.sleep(1)
            rc = g.gp_camera_init(cam, self.ctx)
        if rc < 0:
            g.gp_camera_unref(cam)
            return rc
        name = self._model(cam) or "Fotocamera"
        norm = name.lower().replace("-", "").replace(" ", "")
        self._emit({"event": "device", "name": name})
        other = any(o and o in norm for o in self.others)
        if self.camera_hint and self.camera_hint not in norm and (other or "fuji" not in norm):
            self._emit({"event": "skip", "name": name})
            g.gp_camera_exit(cam, self.ctx)
            g.gp_camera_unref(cam)
            return GP_ERROR_MODEL_NOT_FOUND
        with self.lock:
            self.cam = cam
            self.files = {}
            self.tz_shift = None
        self._emit({"event": "opening", "name": name})
        self._emit({"event": "session"})
        self.camera_name = name
        return GP_OK

    def _model(self, cam):
        txt = _CameraText()
        if self.g.gp_camera_get_summary(cam, C.byref(txt), self.ctx) < 0:
            return ""
        s = txt.text.decode("utf-8", "replace")
        maker = re.search(r"^\s*(?:Manufacturer|Produttore)\s*:\s*(.+)$", s, re.M)
        model = re.search(r"^\s*(?:Model|Modello)\s*:\s*(.+)$", s, re.M)
        return (model.group(1).strip() if model else "") or (maker.group(1).strip() if maker else "")

    def _close(self):
        with self.lock:
            if self.cam is not None:
                try:
                    self.g.gp_camera_exit(self.cam, self.ctx)
                    self.g.gp_camera_unref(self.cam)
                except Exception:  # noqa: BLE001
                    pass
            self.cam = None
            self.files = {}

    @staticmethod
    def usb_present():
        """C'e' una Fujifilm sul bus USB? Lo chiedo al sistema (/sys), non a libgphoto2: dopo il distacco
        del cavo libgphoto2 risponde ancora con l'elenco in memoria (verificato il 6 nov 2026, rc13).
        04cb e' il codice USB di Fujifilm."""
        try:
            for p in glob.glob("/sys/bus/usb/devices/*/idVendor"):
                with open(p) as fh:
                    if fh.read().strip().lower() == "04cb":
                        return True
            return False
        except OSError:
            return True   # se /sys non si legge, non concludo niente

    def _alive_locked(self):
        if self.cam is None:
            return False
        if not self.usb_present():
            return False
        lst = P()
        self.g.gp_list_new(C.byref(lst))
        try:
            return self.g.gp_camera_folder_list_folders(self.cam, b"/", lst, self.ctx) >= 0
        finally:
            self.g.gp_list_free(lst)

    def _check_lost(self, err):
        """Dopo un errore di lettura: se la fotocamera non risponde piu' (cavo staccato), lo dico
        subito a Provino con l'evento "removed", prima che il download successivo fallisca a sua volta.
        Verificato il 6 nov 2026: senza questo, staccando il cavo durante 4 RAF tutti e 4 risultavano
        "non riusciti" (Bad parameters) invece di restare in sospeso fino al ricollegamento."""
        with self.lock:
            if self.cam is None:
                return True   # gia' segnalato dal controllo del bus
            if self._alive_locked():
                return False
            self.log.info("Cavo USB: fotocamera non piu' raggiungibile (%s)" % err)
            self._close()
        self._emit({"event": "removed"})
        return True

    # ------------------------------------------------------------ elenco
    def _names(self, fn, folder):
        lst = P()
        self.g.gp_list_new(C.byref(lst))
        try:
            rc = fn(self.cam, folder.encode("utf-8"), lst, self.ctx)
            if rc < 0:
                raise UsbError("%s: %s" % (folder, _err(rc)))
            out = []
            for i in range(self.g.gp_list_count(lst)):
                s = C.c_char_p()
                self.g.gp_list_get_name(lst, i, C.byref(s))
                out.append(s.value.decode("utf-8", "replace"))
            return out
        finally:
            self.g.gp_list_free(lst)

    def _walk(self, folder="/"):
        out = [(folder, n) for n in self._names(self.g.gp_camera_folder_list_files, folder)]
        for sub in self._names(self.g.gp_camera_folder_list_folders, folder):
            out += self._walk(folder.rstrip("/") + "/" + sub)
        return out

    def _info(self, folder, name):
        fi = _FileInfo()
        rc = self.g.gp_camera_file_get_info(self.cam, folder.encode("utf-8"), name.encode("utf-8"),
                                            C.byref(fi), self.ctx)
        if rc < 0:
            return 0, 0
        return int(fi.file.size), int(fi.file.mtime)

    def _date_of(self, mtime):
        """L'ora che libgphoto2 da' ai file non e' quella dell'EXIF: sulla X-Pro3 risultava
        un'ora avanti (6 nov 2026). La correggo con lo scarto misurato su un JPG (vedi _publish)."""
        if not mtime:
            return ""
        return time.strftime("%Y%m%dT%H%M%S", time.gmtime(mtime + (self.tz_shift or 0)))

    def _publish(self):
        with self.lock:
            self.last_use = time.time()
            entries = []
            for folder, name in self._walk():
                size, mtime = self._info(folder, name)
                entries.append((folder, name, size, mtime))
            # scarto tra l'ora dei file e l'ora di scatto (EXIF), misurato su un JPG
            for folder, name, size, mtime in entries:
                if name.upper().endswith((".JPG", ".JPEG")) and mtime:
                    head = self._read_locked(folder, name, 0, 0x10000) or b""
                    exif = _exif_date(head)
                    if exif:
                        t_exif = calendar.timegm(time.strptime(exif, "%Y%m%dT%H%M%S"))
                        self.tz_shift = int(round((t_exif - mtime) / 900.0)) * 900
                        if self.tz_shift:
                            self.log.debug("usb: ora dei file corretta di %+d s (da %s)" % (self.tz_shift, name))
                    break
            for folder, name, size, mtime in entries:
                fid = self.next_id
                self.next_id += 1
                self.files[fid] = (folder, name, size)
                # come sul Mac: cartella senza il nome interno della memoria (store_...), es. "SLOT 1/DCIM/130_FUJI"
                shown = re.sub(r"^/store_[0-9a-fA-F]+/?", "", folder).strip("/")
                self._emit({"event": "file", "id": fid, "name": name, "size": size,
                            "date": self._date_of(mtime), "folder": shown})
        self._emit({"event": "ready", "count": len(entries), "name": getattr(self, "camera_name", "")})

    # ------------------------------------------------------------ comandi (come fuji_usb)
    def _read_locked(self, folder, name, offset, length):
        out = bytearray()
        while len(out) < length:
            want = min(READ_CHUNK, length - len(out))
            buf = C.create_string_buffer(want)
            n = C.c_uint64(want)
            rc = self.g.gp_camera_file_read(self.cam, folder.encode("utf-8"), name.encode("utf-8"),
                                            GP_FILE_TYPE_NORMAL, offset + len(out), buf, C.byref(n), self.ctx)
            if rc < 0:
                raise UsbError("%s: %s" % (name, _err(rc)))
            if n.value == 0:
                break
            out += buf.raw[:n.value]
            if n.value < want:
                break
        return bytes(out)

    def thumbnail(self, fid, timeout=20):
        with self.lock:
            f = self.files.get(fid)
            if not f or self.cam is None:
                return None
            self.last_use = time.time()
            cf = P()
            self.g.gp_file_new(C.byref(cf))
            try:
                rc = self.g.gp_camera_file_get(self.cam, f[0].encode("utf-8"), f[1].encode("utf-8"),
                                               GP_FILE_TYPE_PREVIEW, cf, self.ctx)
                if rc < 0:
                    self.log.debug("usb miniatura %s: %s" % (f[1], _err(rc)))
                    return None
                data, size = C.c_void_p(), C.c_ulong()
                self.g.gp_file_get_data_and_size(cf, C.byref(data), C.byref(size))
                th = C.string_at(data, size.value)
                return th if th[:2] == b"\xff\xd8" else None
            finally:
                self.g.gp_file_free(cf)

    def read(self, fid, offset, length, timeout=20):
        with self.lock:
            f = self.files.get(fid)
            if not f or self.cam is None:
                return None
            self.last_use = time.time()
            try:
                return self._read_locked(f[0], f[1], int(offset), int(length))
            except UsbError as e:
                self.log.debug("usb lettura: %s" % e)
                err = e
            finally:
                self.last_use = time.time()
        self._check_lost(err)
        return None

    def download(self, fid, dest_dir, name, overwrite, cancelled, timeout=900):
        """Scarica il file in dest_dir/name. Come sul Mac, "Annulla" lascia finire il file in corso."""
        f = self.files.get(fid)
        if not f:
            raise UsbError("file sconosciuto")
        folder, cname, size = f
        path = os.path.join(dest_dir, name)
        if os.path.exists(path) and not overwrite:
            raise UsbError("esiste gia': %s" % name)
        got, last = 0, 0.0
        t0 = time.time()
        with open(path, "wb") as out:
            while size == 0 or got < size:
                with self.lock:
                    if self.cam is None:
                        raise UsbError("cavo scollegato")
                    self.last_use = time.time()
                    try:
                        data = self._read_locked(folder, cname, got, READ_CHUNK)
                    except UsbError as e:
                        err = e
                    else:
                        err = None
                if err is not None:
                    self._check_lost(err)
                    raise err
                if not data:
                    break
                out.write(data)
                got += len(data)
                if size and time.time() - last > 0.5:
                    last = time.time()
                    self._emit({"event": "progress", "id": fid, "fraction": got / float(size)})
                if time.time() - t0 > timeout:
                    raise UsbError("download troppo lento o bloccato")
                if len(data) < READ_CHUNK:
                    break
        if size and got != size:
            raise UsbError("file incompleto (%d di %d byte)" % (got, size))
        self._emit({"event": "progress", "id": fid, "fraction": 1.0})
        return path

    def stop(self):
        self.stopping = True
        self._close()
        self._emit({"event": "exited"})
