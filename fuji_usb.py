"""
Provino - collegamento via cavo USB (solo macOS).

Usa ImageCaptureCore, il componente ufficiale di macOS per le fotocamere (lo stesso di
Acquisizione Immagini), tramite un piccolo aiutante in Swift che viene compilato sul Mac
al primo utilizzo con gli strumenti per sviluppatori di Apple (Command Line Tools).

Fotocamera in modalita' "USB CARD READER" / "LETTORE SCHEDA USB".
L'aiutante legge e copia soltanto: non cancella e non modifica nulla sulla scheda.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time

SWIFT_SOURCE = r'''
import Foundation
import ImageCaptureCore

setvbuf(stdout, nil, _IOLBF, 0)
let outLock = NSLock()
func emit(_ d: [String: Any]) {
    guard let j = try? JSONSerialization.data(withJSONObject: d, options: []),
          let s = String(data: j, encoding: .utf8) else { return }
    outLock.lock(); print(s); fflush(stdout); outLock.unlock()
}

let args = CommandLine.arguments
let thumbDir = args.count > 1 ? args[1] : NSTemporaryDirectory()
let wanted = args.count > 2 ? args[2].lowercased() : ""
// le altre fotocamere supportate: se ne e' collegata piu' d'una, apro solo quella scelta
let others = args.count > 3 ? args[3].lowercased().split(separator: ",").map(String.init).filter { !$0.isEmpty } : []

let df = DateFormatter()
df.locale = Locale(identifier: "en_US_POSIX")
df.dateFormat = "yyyyMMdd'T'HHmmss"

final class Ctl: NSObject, ICDeviceBrowserDelegate, ICCameraDeviceDelegate {
    let browser = ICDeviceBrowser()
    var camera: ICCameraDevice?
    var files: [Int: ICCameraFile] = [:]
    var idByObj: [ObjectIdentifier: Int] = [:]
    var sentReady = false

    func start() {
        browser.delegate = self
        let raw = ICDeviceTypeMask.camera.rawValue | ICDeviceLocationTypeMask.local.rawValue
        if let m = ICDeviceTypeMask(rawValue: raw) as ICDeviceTypeMask? {
            browser.browsedDeviceTypeMask = m
        }
        browser.start()
        emit(["event": "browsing"])
    }

    // MARK: browser
    func deviceBrowser(_ browser: ICDeviceBrowser, didAdd device: ICDevice, moreComing: Bool) {
        let name = device.name ?? "?"
        emit(["event": "device", "name": name])
        guard camera == nil, let cam = device as? ICCameraDevice else { return }
        let norm = name.lowercased().replacingOccurrences(of: "-", with: "").replacingOccurrences(of: " ", with: "")
        let isOther = others.contains { norm.contains($0) }
        if !wanted.isEmpty && !norm.contains(wanted) && (isOther || !norm.contains("fuji")) {
            emit(["event": "skip", "name": name])
            return
        }
        camera = cam
        cam.delegate = self
        emit(["event": "opening", "name": name, "pid": cam.usbProductID])
        cam.requestOpenSession()
    }
    func deviceBrowser(_ browser: ICDeviceBrowser, didRemove device: ICDevice, moreGoing: Bool) {
        if let c = camera, c === device {
            emit(["event": "removed"])
            camera = nil
            files = [:]
            idByObj = [:]
            sentReady = false
        }
    }

    // MARK: device
    func didRemove(_ device: ICDevice) {
        emit(["event": "removed"])
    }
    func device(_ device: ICDevice, didOpenSessionWithError error: Error?) {
        if let e = error { emit(["event": "error", "message": "apertura sessione: \(e.localizedDescription)"]) }
        else { emit(["event": "session"]) }
    }
    func device(_ device: ICDevice, didCloseSessionWithError error: Error?) {
        emit(["event": "closed"])
    }
    func deviceDidBecomeReady(_ device: ICDevice) {}
    func device(_ device: ICDevice, didEncounterError error: Error?) {
        if let e = error { emit(["event": "warning", "message": e.localizedDescription]) }
    }

    // MARK: camera
    func cameraDevice(_ camera: ICCameraDevice, didAdd items: [ICCameraItem]) {
        if sentReady { publish(items) }
    }
    func cameraDevice(_ camera: ICCameraDevice, didRemove items: [ICCameraItem]) {}
    func cameraDevice(_ camera: ICCameraDevice, didReceiveThumbnail thumbnail: CGImage?, for item: ICCameraItem, error: Error?) {}
    func cameraDevice(_ camera: ICCameraDevice, didReceiveMetadata metadata: [AnyHashable: Any]?, for item: ICCameraItem, error: Error?) {}
    func cameraDevice(_ camera: ICCameraDevice, didRenameItems items: [ICCameraItem]) {}
    func cameraDeviceDidChangeCapability(_ camera: ICCameraDevice) {}
    func cameraDevice(_ camera: ICCameraDevice, didReceivePTPEvent eventData: Data) {}
    func cameraDeviceDidRemoveAccessRestriction(_ device: ICDevice) {}
    func cameraDeviceDidEnableAccessRestriction(_ device: ICDevice) {
        emit(["event": "warning", "message": "accesso limitato dalla fotocamera"])
    }
    func deviceDidBecomeReady(withCompleteContentCatalog device: ICCameraDevice) {
        let items = device.mediaFiles ?? []
        publish(items)
        sentReady = true
        emit(["event": "ready", "count": files.count, "name": device.name ?? ""])
    }

    func publish(_ items: [ICCameraItem]) {
        for it in items {
            guard let f = it as? ICCameraFile else { continue }
            let oid = ObjectIdentifier(f)
            if idByObj[oid] != nil { continue }   // gia' comunicato
            let id = files.count + 1
            files[id] = f
            idByObj[oid] = id
            var d: [String: Any] = ["event": "file", "id": id, "name": f.name ?? "file\(id)",
                                    "size": NSNumber(value: Int64(f.fileSize))]
            if let c = f.creationDate { d["date"] = df.string(from: c) }
            // cartella sulla fotocamera (serve a capire in quale scheda si trova il file)
            var parts: [String] = []
            var pf = f.parentFolder
            while let x = pf { parts.insert(x.name ?? "?", at: 0); pf = x.parentFolder }
            d["folder"] = parts.joined(separator: "/")
            d["ptp"] = NSNumber(value: f.ptpObjectHandle)
            emit(d)
        }
    }

    // MARK: comandi
    func thumbnail(_ id: Int) {
        guard let f = files[id] else { emit(["event": "thumb", "id": id, "ok": false]); return }
        f.requestThumbnailData(options: nil) { data, error in
            if let data = data {
                let url = URL(fileURLWithPath: thumbDir).appendingPathComponent("\(id).jpg")
                do { try data.write(to: url); emit(["event": "thumb", "id": id, "ok": true]) }
                catch { emit(["event": "thumb", "id": id, "ok": false]) }
            } else {
                emit(["event": "thumb", "id": id, "ok": false, "message": error?.localizedDescription ?? ""])
            }
        }
    }

    func read(_ id: Int, offset: Int64, length: Int64) {
        guard let f = files[id] else { emit(["event": "read", "id": id, "ok": false]); return }
        f.requestReadData(atOffset: offset, length: length) { data, error in
            if let data = data {
                let url = URL(fileURLWithPath: thumbDir).appendingPathComponent("read_\(id)_\(offset).bin")
                do { try data.write(to: url); emit(["event": "read", "id": id, "ok": true, "offset": NSNumber(value: offset)]) }
                catch { emit(["event": "read", "id": id, "ok": false]) }
            } else {
                emit(["event": "read", "id": id, "ok": false, "message": error?.localizedDescription ?? ""])
            }
        }
    }

    func download(_ id: Int, dir: String, name: String, overwrite: Bool) {
        guard let f = files[id] else { emit(["event": "downloaded", "id": id, "ok": false, "message": "file sconosciuto"]); return }
        var opts: [ICDownloadOption: Any] = [:]
        opts[.downloadsDirectoryURL] = URL(fileURLWithPath: dir, isDirectory: true)
        opts[.saveAsFilename] = name
        opts[.overwrite] = NSNumber(value: overwrite)
        var timer: Timer?
        let progress = f.requestDownload(options: opts) { filename, error in
            timer?.invalidate()
            if let e = error {
                emit(["event": "downloaded", "id": id, "ok": false, "message": e.localizedDescription])
            } else {
                emit(["event": "downloaded", "id": id, "ok": true, "file": filename ?? name])
            }
        }
        if let p = progress {
            timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
                emit(["event": "progress", "id": id, "fraction": p.fractionCompleted])
            }
        }
    }
}

let ctl = Ctl()
ctl.start()

DispatchQueue.global().async {
    while let line = readLine() {
        guard let data = line.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data, options: []) as? [String: Any],
              let cmd = obj["cmd"] as? String else { continue }
        DispatchQueue.main.async {
            switch cmd {
            case "thumb":
                ctl.thumbnail(obj["id"] as? Int ?? 0)
            case "read":
                ctl.read(obj["id"] as? Int ?? 0, offset: Int64(obj["offset"] as? Int ?? 0), length: Int64(obj["length"] as? Int ?? 65536))
            case "download":
                ctl.download(obj["id"] as? Int ?? 0, dir: obj["dir"] as? String ?? NSTemporaryDirectory(),
                             name: obj["name"] as? String ?? "file", overwrite: obj["overwrite"] as? Bool ?? false)
            case "quit":
                if let c = ctl.camera { c.requestCloseSession() }
                exit(0)
            default:
                break
            }
        }
    }
    DispatchQueue.main.async { exit(0) }
}

RunLoop.main.run()
'''


class UsbError(Exception):
    pass


def helper_path(base_dir, log):
    """Compila l'aiutante Swift se serve e ritorna il percorso dell'eseguibile."""
    if sys.platform != "darwin":
        raise UsbError("Il collegamento via cavo dentro l'app funziona solo su macOS.")
    pre = os.environ.get("PROVINO_USB_HELPER")   # app per Mac: aiutante gia' compilato dentro Provino.app
    if pre and os.access(pre, os.X_OK):
        return pre
    bindir = os.path.join(base_dir, ".provino_bin")
    old = os.path.join(base_dir, ".fujiwifi_bin")   # nome usato fino a FujiWiFi 2.8
    if not os.path.isdir(bindir) and os.path.isdir(old):
        try:
            os.rename(old, bindir)
        except OSError:
            pass
    os.makedirs(bindir, exist_ok=True)
    digest = hashlib.sha1(SWIFT_SOURCE.encode("utf-8")).hexdigest()[:10]
    exe = os.path.join(bindir, "fujiusb_" + digest)
    if os.path.exists(exe):
        return exe
    src = os.path.join(bindir, "fujiusb.swift")
    with open(src, "w", encoding="utf-8") as fh:
        fh.write(SWIFT_SOURCE)
    swiftc = shutil.which("swiftc") or "/usr/bin/swiftc"
    log.info("Compilo l'aiutante USB (solo la prima volta)...")
    try:
        r = subprocess.run([swiftc, "-O", "-o", exe, src], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=300)
    except FileNotFoundError:
        raise UsbError("Mancano gli strumenti per sviluppatori di Apple (swiftc). "
                       "Installali con: xcode-select --install")
    except subprocess.TimeoutExpired:
        raise UsbError("La compilazione dell'aiutante USB ha impiegato troppo tempo.")
    out = r.stdout.decode("utf-8", "replace")
    if r.returncode != 0 or not os.path.exists(exe):
        log.info("ERRORE DI COMPILAZIONE dell'aiutante USB:\n" + out[-6000:])
        # riserva: l'ultima versione gia' compilata funziona ancora (senza le novita')
        prev = sorted((os.path.join(bindir, n) for n in os.listdir(bindir)
                       if n.startswith("fujiusb_") and os.access(os.path.join(bindir, n), os.X_OK)),
                      key=os.path.getmtime, reverse=True)
        if prev:
            log.info("Uso la versione precedente dell'aiutante: %s" % os.path.basename(prev[0]))
            return prev[0]
        raise UsbError("Compilazione dell'aiutante USB non riuscita (dettagli nel log).")
    if out.strip():
        log.debug("swiftc: " + out[-3000:])
    log.info("Aiutante USB pronto.")
    return exe


class UsbSession:
    """Parla con l'aiutante Swift. Eventi -> callback; comandi -> stdin."""

    def __init__(self, base_dir, camera_hint, log, on_event):
        self.base_dir = base_dir
        self.camera_hint = camera_hint
        self.others = []   # le altre fotocamere supportate (le salto se collegate insieme)
        self.log = log
        self.on_event = on_event
        self.proc = None
        self.thumb_dir = os.path.join(base_dir, ".provino_bin", "miniature_usb")
        self.thumb_waiters = {}
        self.dl_waiters = {}
        self.read_waiters = {}
        self.lock = threading.Lock()

    def start(self):
        exe = helper_path(self.base_dir, self.log)
        if os.path.isdir(self.thumb_dir):
            for f in os.listdir(self.thumb_dir):
                try:
                    os.remove(os.path.join(self.thumb_dir, f))
                except OSError:
                    pass
        os.makedirs(self.thumb_dir, exist_ok=True)
        self.proc = subprocess.Popen([exe, self.thumb_dir, self.camera_hint, ",".join(self.others)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for raw in self.proc.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                self.log.debug("usb> " + line[:300])
                continue
            kind = ev.get("event")
            if kind != "progress":
                self.log.debug("usb evento: %s" % line[:300])
            if kind == "thumb":
                w = self.thumb_waiters.pop(ev.get("id"), None)
                if w:
                    w["ok"] = ev.get("ok")
                    w["_ev"].set()
            elif kind == "read":
                w = self.read_waiters.pop((ev.get("id"), int(ev.get("offset") or 0)), None)
                if w is None:  # in caso di errore l'offset non c'e': sblocca la prima attesa di quel file
                    for key in list(self.read_waiters):
                        if key[0] == ev.get("id"):
                            w = self.read_waiters.pop(key)
                            break
                if w:
                    w["ok"] = ev.get("ok")
                    w["_ev"].set()
            elif kind == "downloaded":
                w = self.dl_waiters.pop(ev.get("id"), None)
                if w:
                    w.update({k: v for k, v in ev.items() if k != "event"})
                    w["_ev"].set()
            try:
                self.on_event(ev)
            except Exception as e:  # noqa: BLE001
                self.log.debug("usb callback: %r" % (e,))
        self.on_event({"event": "exited"})

    def _send(self, obj):
        if not self.proc or self.proc.poll() is not None:
            raise UsbError("aiutante USB non attivo")
        with self.lock:
            self.proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
            self.proc.stdin.flush()

    def thumbnail(self, fid, timeout=20):
        ev = threading.Event()
        w = {"_ev": ev, "ok": False}
        self.thumb_waiters[fid] = w
        self._send({"cmd": "thumb", "id": fid})
        if not ev.wait(timeout) or not w["ok"]:
            return None
        p = os.path.join(self.thumb_dir, "%d.jpg" % fid)
        try:
            with open(p, "rb") as fh:
                return fh.read()
        except OSError:
            return None

    def read(self, fid, offset, length, timeout=20):
        ev = threading.Event()
        w = {"_ev": ev, "ok": False}
        self.read_waiters[(fid, offset)] = w
        self._send({"cmd": "read", "id": fid, "offset": int(offset), "length": int(length)})
        if not ev.wait(timeout) or not w["ok"]:
            return None
        p = os.path.join(self.thumb_dir, "read_%d_%d.bin" % (fid, offset))
        try:
            with open(p, "rb") as fh:
                return fh.read()
        except OSError:
            return None
        finally:
            try:
                os.remove(p)   # file temporaneo: le letture grandi (anteprime) occupano spazio
            except OSError:
                pass

    def download(self, fid, dest_dir, name, overwrite, cancelled, timeout=900):
        ev = threading.Event()
        w = {"_ev": ev}
        self.dl_waiters[fid] = w
        self._send({"cmd": "download", "id": fid, "dir": dest_dir, "name": name, "overwrite": bool(overwrite)})
        t0 = time.time()
        while not ev.wait(0.5):
            # "Annulla" non interrompe il file in corso: il Mac lo completerebbe comunque in background.
            # Via cavo un file dura pochi secondi: lo lascio finire e la coda si ferma subito dopo.
            if time.time() - t0 > timeout:
                raise UsbError("download troppo lento o bloccato")
        if not w.get("ok"):
            raise UsbError(w.get("message") or "download non riuscito")
        return os.path.join(dest_dir, w.get("file") or name)

    def stop(self):
        try:
            self._send({"cmd": "quit"})
        except Exception:
            pass
        if self.proc:
            try:
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None
