#!/usr/bin/env python3
"""
Provino - protocollo Wi-Fi delle fotocamere Fujifilm (PTP/IP) e strumento a riga di comando.

Usa la modalita' "Comunicazione wireless" della fotocamera (quella pensata per
l'app per smartphone). Il protocollo e' quello ricostruito dal progetto open
source libfuji (https://github.com/petabyt/libfuji, licenza MIT).

SICUREZZA: questo programma legge e copia soltanto. I comandi PTP che cancellano
o formattano (DeleteObject, FormatStore, ecc.) sono bloccati nel codice: anche
per errore non possono partire verso la fotocamera.

Requisiti: solo Python 3.8 o superiore, nessun pacchetto da installare.
"""

import argparse
import datetime
import os
import socket
import struct
import sys
import time

VERSION = "1.0.0-rc16"

# ---------------------------------------------------------------- costanti
CAM_IP = "192.168.0.1"
CMD_PORT = 55740
EVENT_PORT = 55741
LIVEVIEW_PORT = 55742

FUJI_PROTOCOL_VERSION = 0x8F53E4F2
CLIENT_NAME = "Provino"

# Tipi di container PTP (stile USB, usato da Fuji anche su TCP)
T_CMD, T_DATA, T_RESP = 1, 2, 3
INIT_FAIL = 5

# Opcode PTP standard
OC_OpenSession = 0x1002
OC_CloseSession = 0x1003
OC_GetStorageIDs = 0x1004
OC_GetObjectInfo = 0x1008
OC_GetThumb = 0x100A
OC_GetDevicePropValue = 0x1015
OC_SetDevicePropValue = 0x1016
OC_TerminateOpenCapture = 0x1018
OC_GetPartialObject = 0x101B
OC_InitiateOpenCapture = 0x101C

# Opcode che MODIFICANO o CANCELLANO dati: vietati in questo programma.
FORBIDDEN_OPCODES = {
    0x100B,  # DeleteObject
    0x100C,  # SendObjectInfo
    0x100D,  # SendObject
    0x100F,  # FormatStore
    0x1012,  # MoveObject
    0x1013,  # SetObjectProtection
    0x1017,  # ResetDevicePropValue
    0x101D,  # ... riservato
    0x900C, 0x900D, 0x901D,  # scrittura file su scheda (Fuji)
    0x9040, 0x9041, 0x9042,  # invio firmware/oggetti (Fuji)
}

RC_OK = 0x2001
RC_SessionAlreadyOpen = 0x201E

# Proprieta' Fuji
P_EventsList = 0xD212
P_ObjectCount = 0xD222
P_CompressSmall = 0xD226
P_CorrectFileSize = 0xD227
P_StorageID = 0xD244
P_CameraState = 0xDF00
P_ClientState = 0xDF01
P_ImageGetVersion = 0xDF21
P_GetObjectVersion = 0xDF22
P_AutoSaveVersion = 0xDF23
P_RemoteVersion = 0xDF24
P_RemoteGetObjectVersion = 0xDF25

CAM_CONNECT_REMOTE_VER = 0x2000C

# Stati della fotocamera (DF00)
ST_WAIT_FOR_ACCESS = 0
ST_MULTIPLE_TRANSFER = 1
ST_FULL_ACCESS = 2
ST_PC_AUTO_SAVE = 3
ST_REMOTE_ACCESS = 6

# Modalita' del client (DF01)
# Porte del protocollo "PC AutoSave"
AS_NOTIFY = 51540
AS_CONNECT = 51541
AS_REGISTER = 51542
AS_CLIENT_NAME = "Provino"   # le fotocamere gia' registrate come "FujiWiFi" funzionano lo stesso

MODE_VIEW_MULTIPLE = 1
MODE_VIEW_ALL_IMGS = 2
MODE_OLD_REMOTE = 3
MODE_REMOTE = 5
MODE_REMOTE_IMG_VIEW = 11

# Mac: 1 MB per richiesta, come l'app ufficiale (verificato, RAF da 55 MB in ~32 s).
# Linux: 128 KB (verificato sul ThinkPad in Wi-Fi diretto, 5 nov 2026: 8,3 MB in 4,6 s).
MAX_CHUNK = 0x100000 if sys.platform == "darwin" else 0x20000

OBJ_FORMATS = {
    0x3000: "?", 0x3001: "cartella", 0x3801: "JPEG", 0x3808: "JFIF",
    0x380D: "TIFF", 0xB103: "RAF", 0xB982: "MP4", 0x300D: "MOV",
    0xB802: "HEIF", 0x3009: "MP3",
}


class FujiError(Exception):
    pass


class Log:
    """Scrive tutto sia a schermo sia nel file di log."""

    def __init__(self, path, verbose=False):
        self.path = path
        self.verbose = verbose
        self.f = open(path, "a", encoding="utf-8") if path else None

    def _w(self, line, show):
        stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        if self.f:
            self.f.write("[%s] %s\n" % (stamp, line))
            self.f.flush()
        if show:
            print(line, flush=True)

    def info(self, msg):
        self._w(msg, True)

    def debug(self, msg):
        self._w("  . " + msg, self.verbose)

    def close(self):
        if self.f:
            self.f.close()


# ---------------------------------------------------------------- utilita'
def utf16_fixed(text, size):
    raw = text.encode("utf-16-le") + b"\x00\x00"
    return raw[:size].ljust(size, b"\x00")


def read_utf16z(buf, off=0):
    out = []
    i = off
    while i + 1 < len(buf):
        ch = buf[i] | (buf[i + 1] << 8)
        if ch == 0:
            break
        out.append(chr(ch))
        i += 2
    return "".join(out)


def read_ptp_string(buf, off):
    """Stringa PTP: 1 byte di lunghezza (caratteri, incluso lo zero finale) + UTF-16LE."""
    if off >= len(buf):
        return "", off
    n = buf[off]
    off += 1
    s = buf[off:off + n * 2].decode("utf-16-le", "replace").rstrip("\x00")
    return s, off + n * 2


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def jpeg_size(path):
    """Restituisce (larghezza, altezza) dell'immagine principale di un JPEG, o None."""
    try:
        with open(path, "rb") as f:
            d = f.read(4 * 1024 * 1024)
        i = 2
        while i + 9 < len(d):
            if d[i] != 0xFF:
                i += 1
                continue
            m = d[i + 1]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", d[i + 5:i + 9])
                return w, h
            if m == 0xDA:
                return None
            (seg,) = struct.unpack(">H", d[i + 2:i + 4])
            i += 2 + seg
    except (OSError, struct.error):
        pass
    return None


def exif_thumbnail(buf):
    """Cerca la miniatura EXIF dentro i primi byte di un JPEG.
    Ritorna (bytes_miniatura, None) se trovata, (None, byte_necessari) se il buffer
    e' troppo corto, (None, 0) se non c'e'."""
    if len(buf) < 4 or buf[:2] != b"\xff\xd8":
        return None, 0
    i = 2
    while i + 4 <= len(buf):
        if buf[i] != 0xFF:
            return None, 0
        marker = buf[i + 1]
        (seg_len,) = struct.unpack(">H", buf[i + 2:i + 4])
        if marker == 0xE1:
            if i + 4 + seg_len > len(buf) + 2:
                return None, i + 4 + seg_len
            seg = buf[i + 4:i + 2 + seg_len]
            if seg[:6] == b"Exif\x00\x00":
                tiff = seg[6:]
                base = i + 4 + 6
                try:
                    end = "<" if tiff[:2] == b"II" else ">"
                    (ifd0,) = struct.unpack(end + "I", tiff[4:8])
                    (n0,) = struct.unpack(end + "H", tiff[ifd0:ifd0 + 2])
                    (ifd1,) = struct.unpack(end + "I", tiff[ifd0 + 2 + 12 * n0:ifd0 + 6 + 12 * n0])
                    if not ifd1:
                        return None, 0
                    (n1,) = struct.unpack(end + "H", tiff[ifd1:ifd1 + 2])
                    toff = tlen = None
                    for k in range(n1):
                        e = tiff[ifd1 + 2 + 12 * k:ifd1 + 14 + 12 * k]
                        tag, typ, cnt, val = struct.unpack(end + "HHII", e)
                        if tag == 0x0201:
                            toff = val
                        elif tag == 0x0202:
                            tlen = val
                    if toff is None or not tlen:
                        return None, 0
                    if base + toff + tlen > len(buf):
                        return None, base + toff + tlen
                    th = buf[base + toff:base + toff + tlen]
                    return (th, None) if th[:2] == b"\xff\xd8" else (None, 0)
                except struct.error:
                    return None, 0
        if marker in (0xDA, 0xD9):
            return None, 0
        i += 2 + seg_len
    return None, i + 4


def camera_info_from_jpeg(buf):
    """Dati del corpo macchina dall'EXIF di un JPEG (anche quello dentro un RAF).
    Verificato su file X100VI: Software 'Digital Camera X100VI Ver1.31',
    BodySerialNumber (0xA431), ImageCount Fuji (0x1438) che cresce di 1 a ogni scatto."""
    info = {}
    i = buf.find(b"Exif\x00\x00")
    if i < 0:
        return info
    t = buf[i + 6:]
    try:
        e = "<" if t[:2] == b"II" else ">"

        def entries(tb, off, en):
            (n,) = struct.unpack(en + "H", tb[off:off + 2])
            for k in range(n):
                yield struct.unpack(en + "HHII", tb[off + 2 + 12 * k:off + 14 + 12 * k])

        def text(tb, typ, cnt, v, en):
            raw = tb[v:v + cnt] if cnt > 4 else struct.pack(en + "I", v)[:cnt]
            return raw.rstrip(b"\x00 ").decode("ascii", "replace").strip()

        (ifd0,) = struct.unpack(e + "I", t[4:8])
        exif = None
        for tag, typ, cnt, v in entries(t, ifd0, e):
            if tag == 0x0110 and typ == 2:
                info["model"] = text(t, typ, cnt, v, e)
            elif tag == 0x0131 and typ == 2:
                sw = text(t, typ, cnt, v, e)
                info["software"] = sw
                if "Ver" in sw:
                    info["firmware"] = sw.split("Ver", 1)[1].strip()
            elif tag == 0x0132 and typ == 2:
                info["date"] = text(t, typ, cnt, v, e)
            elif tag == 0x8769:
                exif = v
        if exif:
            for tag, typ, cnt, v in entries(t, exif, e):
                if tag == 0xA431 and typ == 2:
                    info["serial"] = text(t, typ, cnt, v, e)
        m = buf.find(b"FUJIFILM\x0c\x00\x00\x00")
        if m >= 0:
            mn = buf[m:]
            (mi,) = struct.unpack("<I", mn[8:12])
            for tag, typ, cnt, v in entries(mn, mi, "<"):
                if tag == 0x1438 and typ == 3:
                    # ImageCount: 15 bit + un bit di stato (maschera 0x7FFF come ExifTool). NON e' il totale
                    # scatti: sulla X-Pro3 si e' azzerato dopo il reset di data/ora (5 nov 2026, da 315 a 2).
                    info["shots"] = v & 0x7FFF
                elif tag == 0x0010 and typ == 2 and "serial" not in info:
                    info["internal_serial"] = text(mn, typ, cnt, v, "<").split(" ")[0]
    except (struct.error, IndexError, ValueError):
        pass
    return info


def jpeg_from_raf_head(head):
    """Offset e lunghezza del JPEG dentro un RAF (dai primi 100 byte)."""
    if head[:15] != b"FUJIFILMCCD-RAW":
        return None
    return struct.unpack(">II", head[84:92])


def parse_selection(text, maximum):
    """'1,3,5-8' -> [1,3,5,6,7,8]"""
    text = text.strip().lower()
    if text in ("tutti", "tutte", "all", "*"):
        return list(range(1, maximum + 1))
    out = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            if a > b:
                a, b = b, a
            out.extend(range(a, b + 1))
        else:
            out.append(int(part))
    seen = []
    for x in out:
        if 1 <= x <= maximum and x not in seen:
            seen.append(x)
    return seen


# ---------------------------------------------------------------- PTP/IP Fuji
class FujiCamera:
    def __init__(self, ip=CAM_IP, log=None, timeout=10.0):
        self.ip = ip
        self.log = log or Log(None)
        self.timeout = timeout
        self.sock = None
        self.extra_socks = []
        self.transaction = 0
        self.session = 0
        self.cam_name = ""
        self.camera_state = -1
        self.num_objects = -1
        self.versions = {}
        self.remote_version = -1
        self.last_events = {}
        self.autosave = False

    # ---- socket
    def _recv_exact(self, n):
        chunks = []
        got = 0
        while got < n:
            part = self.sock.recv(min(n - got, 1 << 20))
            if not part:
                raise FujiError("La fotocamera ha chiuso la connessione")
            chunks.append(part)
            got += len(part)
        return b"".join(chunks)

    def _read_container(self):
        head = self._recv_exact(4)
        (length,) = struct.unpack("<I", head)
        if length < 12:
            rest = self._recv_exact(length - 4) if length > 4 else b""
            return head + rest
        return head + self._recv_exact(length - 4)

    # ---- connessione
    def connect(self, attempts=3):
        last = None
        for i in range(attempts):
            try:
                self.log.debug("Connessione TCP a %s:%d (tentativo %d)" % (self.ip, CMD_PORT, i + 1))
                self.sock = socket.create_connection((self.ip, CMD_PORT), timeout=self.timeout)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._handshake()
                return
            except (OSError, FujiError) as e:
                last = e
                self.log.debug("Tentativo fallito: %r" % (e,))
                self._close_sock()
                time.sleep(1.0)
        raise FujiError("Impossibile collegarsi alla fotocamera: %s" % (last,))

    def _handshake(self):
        pkt = struct.pack(
            "<IIIIIII", 0x52, 1, FUJI_PROTOCOL_VERSION,
            0x5D48A5AD, 0x0B7FB287, 0xD0DED5D3, 0x0,
        ) + utf16_fixed(CLIENT_NAME, 54)
        assert len(pkt) == 0x52
        self.log.debug("Invio pacchetto di inizializzazione")
        self.sock.sendall(pkt)
        # La X-Pro3 puo' mostrare una richiesta di conferma: attendiamo di piu'.
        self.sock.settimeout(max(self.timeout, 60.0))
        resp = self._read_container()
        self.sock.settimeout(self.timeout)
        ptype, code = struct.unpack("<HH", resp[4:8])
        self.log.debug("Risposta init: %d byte, tipo=%d, codice=0x%04X" % (len(resp), ptype, code))
        if ptype == INIT_FAIL:
            raise FujiError("La fotocamera ha rifiutato la connessione (INIT_FAIL)")
        self.cam_name = read_utf16z(resp, 12 + 16)
        self.log.info("Collegato a: %s" % (self.cam_name or "(nome non ricevuto)"))

    def _close_sock(self):
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.sock = None

    def close(self):
        for s in self.extra_socks:
            try:
                s.close()
            except OSError:
                pass
        self.extra_socks = []
        if self.sock:
            try:
                if self.session:
                    self.transact(OC_CloseSession, check=False)
            except Exception:
                pass
            try:
                # pacchetto di "arrivederci" usato da Fuji
                self.sock.sendall(struct.pack("<II", 8, 0xFFFFFFFF))
            except OSError:
                pass
        self._close_sock()

    # ---- transazioni
    def transact(self, code, params=(), data_out=None, check=True, timeout=None):
        if code in FORBIDDEN_OPCODES:
            raise FujiError("Comando 0x%04X bloccato: questo programma non modifica la scheda" % code)
        params = list(params)
        cmd = struct.pack("<IHHI", 12 + 4 * len(params), T_CMD, code, self.transaction)
        cmd += b"".join(struct.pack("<I", p & 0xFFFFFFFF) for p in params)
        self.sock.sendall(cmd)
        if data_out is not None:
            self.sock.sendall(struct.pack("<IHHI", 12 + len(data_out), T_DATA, code, self.transaction) + data_out)

        old = self.sock.gettimeout()
        if timeout is not None:
            self.sock.settimeout(timeout)
        data = b""
        try:
            while True:
                c = self._read_container()
                ctype, ccode = struct.unpack("<HH", c[4:8])
                if ctype == T_DATA:
                    data += c[12:]
                elif ctype == T_RESP:
                    rparams = [struct.unpack("<I", c[i:i + 4])[0] for i in range(12, len(c) - 3, 4)]
                    break
                else:
                    self.log.debug("Container inatteso tipo %d codice 0x%04X" % (ctype, ccode))
        finally:
            self.sock.settimeout(old)
        self.transaction += 1
        self.log.debug("OP 0x%04X %s -> 0x%04X (%d byte di dati)" % (
            code, [hex(p) for p in params], ccode, len(data)))
        if check and ccode != RC_OK:
            raise FujiError("Comando 0x%04X fallito con codice 0x%04X" % (code, ccode))
        return ccode, data, rparams

    def get_prop(self, prop):
        rc, data, _ = self.transact(OC_GetDevicePropValue, [prop], check=False)
        if rc != RC_OK:
            self.log.debug("Proprieta' 0x%04X non disponibile (0x%04X)" % (prop, rc))
            return None, data
        if len(data) == 1:
            return data[0], data
        if len(data) == 2:
            return struct.unpack("<H", data)[0], data
        if len(data) == 4:
            return struct.unpack("<I", data)[0], data
        return -1, data

    def set_prop16(self, prop, value, check=True, timeout=None):
        return self.transact(OC_SetDevicePropValue, [prop], struct.pack("<H", value), check=check, timeout=timeout)

    def set_prop32(self, prop, value, check=True):
        return self.transact(OC_SetDevicePropValue, [prop], struct.pack("<I", value & 0xFFFFFFFF), check=check)

    def get_events(self):
        rc, data, _ = self.transact(OC_GetDevicePropValue, [P_EventsList], check=False)
        if rc != RC_OK or len(data) < 2:
            return {}
        (count,) = struct.unpack("<H", data[:2])
        ev = {}
        for i in range(count):
            off = 2 + i * 6
            if off + 6 > len(data):
                break
            code, value = struct.unpack("<HI", data[off:off + 6])
            ev[code] = value
        if ev:
            self.log.debug("Eventi: " + ", ".join("%04X=%X" % kv for kv in ev.items()))
        if P_CameraState in ev:
            self.camera_state = ev[P_CameraState]
        if P_ObjectCount in ev:
            self.num_objects = ev[P_ObjectCount]
        self.last_events.update(ev)
        return ev

    # ---- configurazione (sequenza dell'app ufficiale, come in libfuji)
    def setup(self):
        time.sleep(0.1)  # Fuji vuole almeno 50 ms prima di OpenSession
        self.session = 1
        self.transaction = 1  # Fuji parte da 1, non da 0
        rc, _, _ = self.transact(OC_OpenSession, [self.session], check=False)
        if rc not in (RC_OK, RC_SessionAlreadyOpen):
            raise FujiError("Apertura sessione fallita (0x%04X)" % rc)
        self.log.debug("Sessione aperta")

        self.get_events()
        if self.camera_state == -1:
            # Se la fotocamera non lo comunica negli eventi, lo chiediamo direttamente
            val, _ = self.get_prop(P_CameraState)
            if isinstance(val, int) and val >= 0:
                self.camera_state = val
        if self.camera_state in (ST_WAIT_FOR_ACCESS, -1):
            self.log.info(">>> Premi OK sulla fotocamera per autorizzare il collegamento...")
            t0 = time.time()
            while self.camera_state in (ST_WAIT_FOR_ACCESS, -1):
                if time.time() - t0 > 120:
                    raise FujiError("Nessuna conferma dalla fotocamera entro 2 minuti")
                time.sleep(0.3)
                self.get_events()

        for name, prop in (("GetObjectVersion", P_GetObjectVersion),
                           ("RemoteGetObjectVersion", P_RemoteGetObjectVersion),
                           ("ImageGetVersion", P_ImageGetVersion),
                           ("RemoteVersion", P_RemoteVersion)):
            val, _ = self.get_prop(prop)
            self.versions[name] = val
            self.log.debug("%s = %s" % (name, hex(val) if isinstance(val, int) and val >= 0 else val))
        rv = self.versions.get("RemoteVersion")
        self.remote_version = rv if isinstance(rv, int) and rv >= 0 else -1
        self.log.info("Stato fotocamera: %s, versione remota: %s" % (
            self.camera_state, hex(self.remote_version) if self.remote_version >= 0 else "nessuna"))

        self.autosave = (self.camera_state == ST_PC_AUTO_SAVE)
        if self.autosave:
            self.log.info("Modalita' PC AutoSave: dovrebbero essere visibili anche i RAF")

        # Modalita' client
        if self.autosave:
            mode = MODE_OLD_REMOTE
        elif self.remote_version != -1 or self.camera_state == ST_REMOTE_ACCESS:
            mode = MODE_REMOTE
        elif self.camera_state == ST_MULTIPLE_TRANSFER:
            mode = MODE_VIEW_MULTIPLE
        elif self.camera_state == ST_PC_AUTO_SAVE:
            mode = MODE_OLD_REMOTE
        else:
            mode = MODE_VIEW_ALL_IMGS
        self.log.debug("Imposto modalita' client %d" % mode)
        rc, _, _ = self.set_prop16(P_ClientState, mode, check=False, timeout=120)
        if rc != RC_OK:
            raise FujiError("La fotocamera non accetta la modalita' %d (0x%04X)" % (mode, rc))
        self.get_events()

        if self.camera_state == ST_MULTIPLE_TRANSFER:
            self.log.info("La fotocamera e' in modalita' 'invio immagini selezionate'.")
            return

        # Versioni
        if self.autosave:
            val, _ = self.get_prop(P_AutoSaveVersion)
            if isinstance(val, int) and val >= 0:
                self.set_prop32(P_AutoSaveVersion, val, check=False)
            self.set_prop16(P_CorrectFileSize, 1, check=False)
        elif self.remote_version == -1:
            val, _ = self.get_prop(P_GetObjectVersion)
            if isinstance(val, int) and val >= 0:
                self.set_prop32(P_GetObjectVersion, val, check=False)
        else:
            self.set_prop32(P_RemoteVersion, CAM_CONNECT_REMOTE_VER, check=False)

        self.get_prop(P_StorageID)

        if not self.autosave and self.remote_version != -1 and self.camera_state == ST_REMOTE_ACCESS:
            self._remote_prepare()
            self._remote_gallery()

        if self.num_objects < 0:
            self.get_events()
        if self.num_objects < 0:
            val, _ = self.get_prop(P_ObjectCount)
            if isinstance(val, int) and val >= 0:
                self.num_objects = val
        self.log.info("Foto e video sulla scheda: %s" % self.num_objects)

    def _remote_prepare(self):
        """Apre e chiude il modo remoto: senza, alcune fotocamere smettono di rispondere."""
        self.log.debug("Preparazione modo remoto")
        start_tx = self.transaction
        self.transact(OC_InitiateOpenCapture, [0, 0], check=False)
        self.get_events()
        time.sleep(0.05)
        for port in (EVENT_PORT, LIVEVIEW_PORT):
            try:
                s = socket.create_connection((self.ip, port), timeout=5)
                self.extra_socks.append(s)
                self.log.debug("Aperta porta %d" % port)
            except OSError as e:
                self.log.debug("Porta %d non disponibile: %r" % (port, e))
        self.get_events()
        self.transact(OC_TerminateOpenCapture, [start_tx], check=False)
        # Il flusso del mirino non ci serve: lo chiudiamo
        for s in self.extra_socks[1:]:
            try:
                s.close()
            except OSError:
                pass
        self.extra_socks = self.extra_socks[:1]

    def _remote_gallery(self):
        self.log.debug("Configurazione galleria")
        self.get_events()
        self.set_prop16(P_CameraState, ST_REMOTE_ACCESS, check=False)
        self.get_events()
        self.get_events()
        self.set_prop16(P_ClientState, MODE_REMOTE_IMG_VIEW, check=False)
        self.get_events()
        self.get_prop(P_RemoteGetObjectVersion)
        self.set_prop32(P_RemoteGetObjectVersion, 5, check=False)
        self.get_events()

    # ---- oggetti
    def handles(self):
        if self.num_objects <= 0:
            return []
        return list(range(1, self.num_objects + 1))

    def object_info(self, handle, timeout=None):
        rc, d, _ = self.transact(OC_GetObjectInfo, [handle], check=False, timeout=timeout)
        if rc != RC_OK or len(d) < 52:
            return None
        info = {"handle": handle}
        (info["storage"], info["format"], info["protection"], info["size"],
         info["thumb_format"], info["thumb_size"], info["thumb_w"], info["thumb_h"],
         info["width"], info["height"]) = struct.unpack("<IHHIHIIIII", d[:34])
        off = 52
        info["filename"], off = read_ptp_string(d, off)
        info["date"], off = read_ptp_string(d, off)
        info["raw_len"] = len(d)
        info["format_name"] = OBJ_FORMATS.get(info["format"], "0x%04X" % info["format"])
        return info

    def correct_size_on(self, timeout=30):
        """D227=1: la fotocamera dichiara la dimensione vera del file.
        Va mandato dopo una breve pausa e una lettura degli eventi: sul ThinkPad (Fedora,
        X-Pro3 in Wi-Fi diretto, 5 nov 2026) D227 mandato subito dopo D226 non riceveva
        mai risposta; con 0,5 s di pausa + eventi risponde subito (prova C)."""
        time.sleep(0.5)
        self.get_events()
        return self.set_prop16(P_CorrectFileSize, 1, check=False, timeout=timeout)

    def object_info_full(self, handle):
        """Info con la dimensione reale del file (la fotocamera altrimenti dichiara ~100 KB)."""
        self.get_events()
        self.set_prop16(P_CorrectFileSize, 1, check=False, timeout=30)
        try:
            return self.object_info(handle)
        finally:
            self.get_events()
            self.set_prop16(P_CorrectFileSize, 0, check=False)

    def thumbnail(self, handle):
        if self.autosave:
            return None  # in PC AutoSave GetThumb non e' supportato
        if self.remote_version > 0x20006:
            self.object_info(handle)  # altrimenti GetThumb si blocca sulle fotocamere recenti
        rc, d, _ = self.transact(OC_GetThumb, [handle], check=False, timeout=30)
        if rc != RC_OK or len(d) < 100:
            return None
        return d

    def partial(self, handle, offset, length, timeout=30):
        rc, d, _ = self.transact(OC_GetPartialObject, [handle, offset, length], check=False, timeout=timeout)
        if rc != RC_OK:
            raise FujiError("Lettura parziale fallita (0x%04X)" % rc)
        return d

    def _thumb_from_jpeg_at(self, handle, base):
        want = 0x10000
        for _ in range(3):
            buf = self.partial(handle, base, want, timeout=15)
            self.last_head = buf   # contiene anche l'EXIF completo: Provino ne ricava la ricetta
            th, need = exif_thumbnail(buf)
            if th:
                return th
            if not need or need <= len(buf) or need > 0x80000:
                return None
            want = need + 16
        return None

    def preview(self, handle, filename=""):
        """Miniatura di un file. In AutoSave la ricava dai primi byte del file stesso."""
        if not self.autosave:
            return self.thumbnail(handle)
        self.get_events()
        self.last_head = b""
        # Sequenza verificata sulla X-Pro3 (1 nov 2026, "Test anteprime", metodo 2):
        # 1) info del file  2) lettura dell'inizio  3) lettura degli ultimi byte.
        # Senza il punto 3 la fotocamera non accetta piu' comandi su altri file.
        info = self.object_info(handle, timeout=30)
        size = (info or {}).get("size") or 0
        th = None
        try:
            if filename.upper().endswith(".RAF"):
                head = self.partial(handle, 0, 0x60, timeout=15)
                if head[:15] == b"FUJIFILMCCD-RAW":
                    jpeg_off, jpeg_len = struct.unpack(">II", head[84:92])
                    th = self._thumb_from_jpeg_at(handle, jpeg_off)
            else:
                th = self._thumb_from_jpeg_at(handle, 0)
        except FujiError as e:
            self.log.debug("Anteprima %d non disponibile: %s" % (handle, e))
        if size > 0x1000:
            self.partial(handle, size - 0x1000, 0x1000, timeout=15)  # "chiude" il file
        for _ in range(3):
            time.sleep(0.2)
            self.get_events()
        return th

    def read_head(self, handle, filename, length=0x20000):
        """Primi byte utili per i metadati (JPEG o JPEG dentro il RAF), chiudendo poi il file."""
        self.get_events()
        info = self.object_info(handle, timeout=30)
        size = (info or {}).get("size") or 0
        data = b""
        try:
            if filename.upper().endswith(".RAF"):
                head = self.partial(handle, 0, 0x60, timeout=15)
                loc = jpeg_from_raf_head(head)
                if loc:
                    data = self.partial(handle, loc[0], min(length, loc[1]), timeout=20)
            else:
                data = self.partial(handle, 0, length, timeout=20)
        finally:
            if self.autosave and size > 0x1000:
                self.partial(handle, size - 0x1000, 0x1000, timeout=15)
            for _ in range(3):
                time.sleep(0.2)
                self.get_events()
        return data

    def download(self, handle, dest_dir, progress=None):
        self.get_events()
        cur, _ = self.get_prop(P_CompressSmall)
        self.log.debug("CompressSmall prima del download = %s" % (cur,))
        # 2 = file originale a piena risoluzione, 1 = versione ridotta per smartphone
        self.set_prop16(P_CompressSmall, 2, check=False)
        self.correct_size_on()
        try:
            info = self.object_info(handle)
            if info is None:
                raise FujiError("Informazioni non disponibili per l'oggetto %d" % handle)
            name = info["filename"] or ("oggetto_%04d" % handle)
            total = info["size"]
            path = os.path.join(dest_dir, name)
            base, ext = os.path.splitext(path)
            n = 1
            while os.path.exists(path):  # mai sovrascrivere nulla
                path = "%s_%d%s" % (base, n, ext)
                n += 1
            tmp = path + ".part"
            got = 0
            t0 = time.time()
            with open(tmp, "wb") as f:
                while got < total:
                    want = min(MAX_CHUNK, total - got)
                    rc, d, _ = self.transact(OC_GetPartialObject, [handle, got, want], check=False, timeout=60)
                    if rc != RC_OK:
                        raise FujiError("Download interrotto (0x%04X) a %d/%d byte" % (rc, got, total))
                    if not d:
                        raise FujiError("La fotocamera ha inviato 0 byte a %d/%d" % (got, total))
                    f.write(d)
                    got += len(d)
                    if progress:
                        progress(got, total, time.time() - t0)
            os.rename(tmp, path)
            secs = max(time.time() - t0, 0.001)
            return path, total, secs
        finally:
            self.get_events()
            if not self.autosave:
                self.set_prop16(P_CorrectFileSize, 0, check=False)


# ---------------------------------------------------------------- PC AutoSave
def _http_fields(text):
    out = {}
    first = text.split("\r\n", 1)[0].split("\n", 1)[0]
    for line in text.replace("\r", "").split("\n")[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip().upper()] = v.strip()
    return first, out


def network_report(log):
    """Scrive nel log le informazioni di rete del Mac (per la diagnosi)."""
    import subprocess
    cmds = [
        ["ipconfig", "getifaddr", "en0"],
        ["ipconfig", "getifaddr", "en1"],
        ["route", "-n", "get", "default"],
        ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"],
        ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getblockall"],
        ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getstealthmode"],
        ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getallowsigned"],
        ["networksetup", "-getairportnetwork", "en0"],
    ]
    for c in cmds:
        try:
            out = subprocess.run(c, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 timeout=5).stdout.decode("utf-8", "replace").strip()
            out = " | ".join(l.strip() for l in out.splitlines() if l.strip())[:300]
        except Exception as e:
            out = "n/d (%s)" % e.__class__.__name__
        log.info("  rete> %s: %s" % (" ".join(c[-2:]), out))
    log.info("  rete> python: %s" % sys.executable)


def _as_reply(log, data, addr, srv, register, info=None):
    """Risponde a un annuncio DISCOVER: NOTIFY alla fotocamera, poi lei si ricollega a noi."""
    text = data.decode("ascii", "replace")
    first, f = _http_fields(text)
    cam_ip = f.get("DSCADDR") or addr[0]
    log.info("Ricevuto annuncio dalla fotocamera (%s)%s" % (cam_ip, " per la registrazione" if register else ""))
    log.debug("Annuncio: %r" % text)
    target = first.split(" ")[1] if len(first.split(" ")) > 1 else "*"
    name = AS_CLIENT_NAME if target in ("*", "") else target

    n = socket.create_connection((cam_ip, AS_NOTIFY), timeout=10)
    msg = "NOTIFY * HTTP/1.1\r\nHOST: %s:%d\r\nIMPORTER: %s\r\n" % (cam_ip, AS_NOTIFY, name)
    n.sendall(msg.encode("ascii"))
    ack = n.recv(512).decode("ascii", "replace")
    n.close()
    log.debug("Risposta NOTIFY: %r" % ack)
    if "200 OK" not in ack:
        raise FujiError("La fotocamera ha rifiutato il saluto: %r" % ack)

    srv.settimeout(30)
    try:
        c, caddr = srv.accept()
    except socket.timeout:
        raise FujiError("La fotocamera non si e' ricollegata (forse il firewall del Mac blocca Python?)")
    c.settimeout(10)
    req = c.recv(2048).decode("ascii", "replace")
    log.debug("Richiesta fotocamera: %r" % req)
    _, rf = _http_fields(req)
    if register:
        c.sendall(b"HTTP/1.1 200 OK\r\nFOLDER: guest\r\nServiceName: PCAUTOSAVE/1.0\r\n")
        log.info("Mac registrato nella fotocamera %s (%s)." % (rf.get("DSCNAME", "?"), rf.get("DSCMODEL", "?")))
    else:
        c.sendall(b"HTTP/1.1 200 OK\r\n")
        log.info("La fotocamera %s ha accettato il collegamento." % rf.get("DSCNAME", "?"))
    if info is not None:
        info["dscname"] = rf.get("DSCNAME", "")
        info["model"] = rf.get("DSCMODEL", "")
        info["ip"] = cam_ip
    c.close()
    return cam_ip


def autosave_handshake(log, register=False, wait=180, info=None, should_stop=None, on_registered=None):
    """Fa la parte di 'PC AutoSave' (il vecchio software Fujifilm).
    register=True: registra questo computer nella fotocamera (una volta sola).
    register=False: attende che la fotocamera si colleghi e restituisce il suo IP.
      Se nel frattempo la fotocamera chiede di registrare un computer (succede dopo aver
      impostato una rete nuova) e on_registered e' dato, la registrazione si fa da sola
      e poi si continua ad aspettare il collegamento."""
    import select
    port = AS_REGISTER if register else AS_CONNECT
    network_report(log)
    udps = {}
    for pnum in (AS_CONNECT, AS_REGISTER, 51562):
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        try:
            u.bind(("", pnum))
            udps[u] = pnum
        except OSError as e:
            log.info("  porta UDP %d non disponibile: %s" % (pnum, e))
            u.close()
    srvs = {}
    for pnum in ([port] if (register or not on_registered) else [AS_CONNECT, AS_REGISTER]):
        sv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sv.bind(("", pnum))
        sv.listen(2)
        srvs[pnum] = sv
    try:
        log.info("In attesa della fotocamera (fino a %d secondi)..." % wait)
        if register:
            log.info(">>> Sulla fotocamera avvia ora la registrazione del PC (PC AUTO SAVE SETTING).")
        else:
            log.info(">>> Sulla fotocamera avvia ora PC AUTO SAVE (menu riproduzione).")
        t0 = time.time()
        got = None
        last_dot = t0
        while got is None:
            if should_stop and should_stop():
                raise FujiError("annullato")
            left = wait - (time.time() - t0)
            if left <= 0:
                raise FujiError("Nessun segnale dalla fotocamera in %d s (vedi le righe 'rete>' nel log)." % wait)
            r, _, _ = select.select(list(udps.keys()), [], [], min(left, 1))
            if time.time() - last_dot > 30:
                log.info("  ...ancora in ascolto (%d s)" % int(time.time() - t0))
                last_dot = time.time()
            for u in r:
                data, addr = u.recvfrom(2048)
                pnum = udps[u]
                log.info("  Ricevuto pacchetto UDP sulla porta %d da %s" % (pnum, addr[0]))
                log.debug("  contenuto: %r" % data[:300])
                if pnum == port and data.startswith(b"DISCOVER"):
                    got = (data, addr)
                elif data.startswith(b"DISCOVER") and pnum == AS_REGISTER and on_registered and not register:
                    # la fotocamera cerca un computer da registrare: lo registro e continuo ad aspettare
                    try:
                        reg = {}
                        _as_reply(log, data, addr, srvs[AS_REGISTER], True, reg)
                        on_registered(reg)
                        t0 = time.time()
                    except (FujiError, OSError) as e:
                        log.info("  Registrazione automatica non riuscita: %s" % e)
                elif data.startswith(b"DISCOVER"):
                    log.info("  (e' un annuncio per l'altra modalita': porta %d)" % pnum)
        data, addr = got
        return _as_reply(log, data, addr, srvs[port], register, info)
    finally:
        for u in udps:
            u.close()
        for sv in srvs.values():
            sv.close()


# ---------------------------------------------------------------- esperimenti anteprime
def _exp_pick(cam, log):
    infos = []
    for h in cam.handles():
        i = cam.object_info(h)
        if i and i["format"] != 0x3001:
            infos.append(i)
    jpgs = [i for i in infos if i["filename"].upper().endswith(".JPG")]
    if len(jpgs) < 2:
        raise FujiError("servono almeno 2 JPG sulla scheda")
    a, b = jpgs[-1], jpgs[-2]
    log.info("  file A: %s (%d), file B: %s (%d)" % (a["filename"], a["handle"], b["filename"], b["handle"]))
    return a, b, infos


def experiment(cam, log, n):
    """Ritorna (riuscito, descrizione)."""
    a, b, infos = _exp_pick(cam, log)
    T = 15
    if n == 1:
        log.info("ESPERIMENTO 1: comando GetThumb su A e poi su B")
        for f in (a, b):
            cam.object_info(f["handle"], timeout=T)
            rc, d, _ = cam.transact(OC_GetThumb, [f["handle"]], check=False, timeout=T)
            log.info("  GetThumb %s -> 0x%04X, %d byte" % (f["filename"], rc, len(d)))
            if rc != RC_OK or len(d) < 100:
                return False, "GetThumb non supportato (0x%04X)" % rc
        cam.object_info(a["handle"], timeout=T)
        return True, "GetThumb funziona"
    if n == 2:
        log.info("ESPERIMENTO 2: inizio di A, poi ultimi byte di A, poi B")
        cam.object_info(a["handle"], timeout=T)
        d = cam.partial(a["handle"], 0, 0x10000, timeout=T)
        th, _ = exif_thumbnail(d)
        log.info("  inizio A: %d byte, miniatura %s" % (len(d), "trovata" if th else "non trovata"))
        size = a["size"]
        tail = cam.partial(a["handle"], size - 0x1000, 0x1000, timeout=T)
        log.info("  fine A: %d byte" % len(tail))
        for _ in range(3):
            time.sleep(0.2)
            cam.get_events()
        i = cam.object_info(b["handle"], timeout=T)
        log.info("  info B: %s" % ("OK" if i else "nessuna"))
        d = cam.partial(b["handle"], 0, 0x10000, timeout=T)
        log.info("  inizio B: %d byte" % len(d))
        cam.partial(b["handle"], b["size"] - 0x1000, 0x1000, timeout=T)
        cam.object_info(a["handle"], timeout=T)
        return True, "leggere anche la fine del file sblocca la fotocamera"
    if n == 3:
        log.info("ESPERIMENTO 3: inizio di A, di nuovo info di A, poi B")
        cam.object_info(a["handle"], timeout=T)
        d = cam.partial(a["handle"], 0, 0x10000, timeout=T)
        log.info("  inizio A: %d byte" % len(d))
        cam.object_info(a["handle"], timeout=T)
        log.info("  info A di nuovo: OK")
        i = cam.object_info(b["handle"], timeout=T)
        log.info("  info B: %s" % ("OK" if i else "nessuna"))
        return True, "ripetere le info dello stesso file sblocca la fotocamera"
    raise FujiError("esperimento sconosciuto")


def run_experiments(log):
    """Prova i metodi uno dopo l'altro. Si ricollega solo se la fotocamera si blocca."""
    results = {}
    cam = None
    for n in (1, 2, 3):
        log.info("")
        log.info("===== Tentativo %d di 3 =====" % n)
        try:
            if cam is None:
                cam = FujiCamera(CAM_IP, log)
                cam.ip = autosave_handshake(log, register=False, wait=300)
                time.sleep(0.5)
                cam.connect()
                cam.setup()
            ok, desc = experiment(cam, log, n)
            blocked = False
        except (OSError, socket.timeout) as e:
            ok, desc, blocked = False, "la fotocamera si e' bloccata (%r)" % (e,), True
        except FujiError as e:
            ok, desc = False, str(e)
            blocked = "chiuso la connessione" in str(e) or "collegarsi" in str(e)
        results[n] = (ok, desc)
        log.info(">>> RISULTATO %d: %s - %s" % (n, "RIUSCITO" if ok else "NON riuscito", desc))
        if ok:
            log.info("Trovato un metodo che funziona: mi fermo qui.")
            break
        if blocked:
            try:
                cam.close()
            except Exception:
                pass
            cam = None
            if n < 3:
                log.info(">>> Sulla fotocamera: spegni e riaccendi, poi avvia di nuovo PC AUTO SAVE.")
        else:
            log.info("(la fotocamera risponde ancora: provo subito il metodo successivo)")
    if cam is not None:
        try:
            cam.close()
        except Exception:
            pass
    log.info("")
    log.info("RIEPILOGO: " + "; ".join("%d=%s" % (k, "OK" if v[0] else "no") for k, v in results.items()))
    return results


# ---------------------------------------------------------------- programma
def progress_bar(got, total, secs):
    pct = 100.0 * got / total if total else 100.0
    speed = got / secs / 1024 / 1024 if secs > 0 else 0
    bar = "#" * int(pct / 4)
    sys.stdout.write("\r    [%-25s] %5.1f%%  %s/%s  %.2f MB/s " % (bar, pct, human(got), human(total), speed))
    sys.stdout.flush()
    if got >= total:
        sys.stdout.write("\n")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Scarica via Wi-Fi le foto da una Fujifilm")
    ap.add_argument("--ip", default=CAM_IP, help="indirizzo della fotocamera (default 192.168.0.1)")
    ap.add_argument("--dest", default=os.path.join(here, "scaricate"), help="cartella di destinazione")
    ap.add_argument("--test", action="store_true",
                    help="prova automatica: elenca le foto, scarica 3 miniature e 1 file, senza domande")
    ap.add_argument("--lista", type=int, default=40, help="quante foto mostrare nell'elenco (default 40)")
    ap.add_argument("--autosave", action="store_true",
                    help="collegamento tramite rete di casa (PC AUTO SAVE): permette anche i RAF")
    ap.add_argument("--registra", action="store_true",
                    help="registra il Mac nella fotocamera per PC AUTO SAVE (da fare una volta)")
    ap.add_argument("--esperimenti", action="store_true", help="prova i metodi per le anteprime in PC AUTO SAVE")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    logdir = os.path.join(here, "log")
    os.makedirs(logdir, exist_ok=True)
    os.makedirs(args.dest, exist_ok=True)
    logpath = os.path.join(logdir, "provino_cli_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    log = Log(logpath, verbose=args.verbose)
    log.info("Provino CLI %s - Python %s - %s" % (VERSION, sys.version.split()[0], sys.platform))
    log.info("Log: %s" % logpath)

    if args.esperimenti:
        try:
            run_experiments(log)
            log.info("Esito: OK")
            return 0
        finally:
            log.close()

    if args.registra:
        try:
            autosave_handshake(log, register=True)
            log.info("Fatto. Ora puoi usare PC AUTO SAVE con l'opzione --autosave.")
            log.info("Esito: OK")
            return 0
        except (FujiError, OSError) as e:
            log.info("ERRORE: %s" % e)
            log.info("Esito: NON riuscito")
            return 1
        finally:
            log.close()

    cam = FujiCamera(args.ip, log)
    ok = False
    try:
        if args.autosave:
            cam.ip = autosave_handshake(log, register=False)
            time.sleep(0.5)
        log.info("Mi collego alla fotocamera su %s ..." % cam.ip)
        cam.connect()
        cam.setup()

        handles = cam.handles()
        if not handles:
            log.info("Nessuna foto trovata (o la fotocamera non ha comunicato il numero).")
            return 2

        # Fotocamere recenti mettono la piu' vecchia per prima: mostriamo le ultime.
        shown = handles[-args.lista:] if len(handles) > args.lista else handles
        log.info("")
        log.info("Ultime %d di %d:" % (len(shown), len(handles)))
        listing = []
        for h in shown:
            info = cam.object_info(h)
            if info is not None and info["format"] == 0x3001:
                log.debug("salto la cartella %s" % info["filename"])
                continue
            listing.append((h, info))
            i = len(listing)
            if info is None:
                log.info("  %3d) oggetto %d: info non disponibili" % (i, h))
            else:
                log.info("  %3d) %-14s %-5s %s" % (i, info["filename"], info["format_name"], info["date"]))
                log.debug("info %d: %r" % (h, info))
        if not listing:
            log.info("Nessun file scaricabile trovato.")
            return 2

        if args.test:
            thumbdir = os.path.join(args.dest, "miniature_test")
            os.makedirs(thumbdir, exist_ok=True)
            log.info("")
            log.info("TEST: scarico 3 miniature...")
            for h, info in listing[-3:]:
                th = cam.preview(h, (info or {}).get("filename", ""))
                if th:
                    p = os.path.join(thumbdir, "mini_%s.jpg" % ((info or {}).get("filename") or h))
                    with open(p, "wb") as f:
                        f.write(th)
                    log.info("  miniatura OK: %s (%s)" % (os.path.basename(p), human(len(th))))
                else:
                    log.info("  miniatura non disponibile per l'oggetto %d" % h)
            jpgs = [(hh, ii) for hh, ii in listing if ii and not ii["filename"].upper().endswith(".RAF")]
            h, info = (jpgs or listing)[-1]
            log.info("TEST: scarico un file completo (%s)..." % ((info or {}).get("filename") or h))
            path, total, secs = cam.download(h, args.dest, progress_bar)
            log.info("  OK: %s, %s in %.1f s (%.2f MB/s)" % (
                os.path.basename(path), human(total), secs, total / secs / 1024 / 1024))
            sz = jpeg_size(path)
            if sz:
                exp = (info or {}).get("width"), (info or {}).get("height")
                if exp[0]:
                    verdict = "PIENA RISOLUZIONE" if sz[0] >= exp[0] else "RIDOTTA"
                else:
                    verdict = "originale sconosciuta"
                log.info("  Risoluzione: %dx%d (originale %sx%s) -> %s" % (
                    sz[0], sz[1], exp[0], exp[1], verdict))
            # Prova anche un RAF, se c'e' nell'elenco
            raf = [(hh, ii) for hh, ii in listing if ii and ii["filename"].upper().endswith(".RAF")]
            if raf and raf[-1][0] != h:
                hh, ii = raf[-1]
                log.info("TEST: provo a scaricare anche un RAW (%s)..." % ii["filename"])
                try:
                    path, total, secs = cam.download(hh, args.dest, progress_bar)
                    log.info("  OK RAW: %s, %s" % (os.path.basename(path), human(total)))
                except FujiError as e:
                    log.info("  RAW non scaricabile: %s" % e)
            elif not raf:
                log.info("TEST: nessun file RAF visibile nell'elenco.")
            ok = True
            return 0

        log.info("")
        log.info("Quali vuoi scaricare? Scrivi i numeri (es. 1,4,7-10), 'tutti', oppure Invio per uscire.")
        try:
            sel = input("> ")
        except EOFError:
            sel = ""
        chosen = parse_selection(sel, len(listing)) if sel.strip() else []
        if not chosen:
            log.info("Nessun file scelto.")
            ok = True
            return 0
        log.info("Scelte: %s" % chosen)
        for n, idx in enumerate(chosen, 1):
            h, info = listing[idx - 1]
            log.info("[%d/%d] %s" % (n, len(chosen), (info or {}).get("filename", h)))
            try:
                path, total, secs = cam.download(h, args.dest, progress_bar)
                sz = jpeg_size(path)
                log.info("    salvato: %s%s" % (path, (" (%dx%d)" % sz) if sz else ""))
            except FujiError as e:
                log.info("    ERRORE: %s" % e)
        log.info("Fatto. I file sono in: %s" % args.dest)
        ok = True
        return 0
    except KeyboardInterrupt:
        log.info("\nInterrotto.")
        return 130
    except (FujiError, OSError) as e:
        log.info("ERRORE: %s" % e)
        return 1
    except Exception:
        import traceback
        log.info("ERRORE IMPREVISTO:\n" + traceback.format_exc())
        return 1
    finally:
        cam.close()
        log.info("Esito: %s" % ("OK" if ok else "NON riuscito"))
        log.close()


if __name__ == "__main__":
    sys.exit(main())
