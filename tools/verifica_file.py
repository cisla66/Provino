#!/usr/bin/env python3
"""verifica_file.py - controlla i file ricevuti PRIMA di usarli con Provino.

Accetta soltanto: .RAF, .JPG/.JPEG, .HIF (HEIF) e un .txt breve. Non esegue e non apre
nulla: legge solo le prime righe/byte di ogni file. Non cancella nulla.
Uso:  python3 verifica_file.py CARTELLA [--sposta-scartati] [--ordina DEST]
  --ordina DEST  sposta i file accettati in DEST/<MODELLO>/<data>-<cartella>/
                 e scrive lì un elenco SHA256SUMS per ricontrollarli dopo.
"""
import hashlib, os, re, shutil, sys, struct, datetime

MAX_RAF = 300 * 1024 * 1024
MAX_JPG = 60 * 1024 * 1024
MAX_HIF = 80 * 1024 * 1024
MARCHI_HEIF = (b"heic", b"heix", b"mif1", b"msf1", b"hevc")
MAX_TXT = 64 * 1024
PERICOLOSE = {"exe","dll","bat","cmd","com","scr","msi","js","vbs","ps1","sh","py","app",
              "dmg","pkg","jar","appimage","desktop","lnk","zip","rar","7z","gz","tar","iso"}

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def controlla(p):
    """Restituisce (ok, messaggio, modello)."""
    nome = os.path.basename(p)
    if os.path.islink(p):
        return False, "collegamento simbolico", ""
    if not os.path.isfile(p):
        return False, "non è un file normale", ""
    parti = nome.lower().split(".")
    ext = parti[-1] if len(parti) > 1 else ""
    if any(x in PERICOLOSE for x in parti[1:]):
        return False, "estensione pericolosa o archivio nel nome", ""
    if os.stat(p).st_mode & 0o111:
        return False, "file eseguibile", ""
    size = os.path.getsize(p)
    with open(p, "rb") as f:
        testa = f.read(128)
        if ext == "raf":
            if size > MAX_RAF: return False, "troppo grande per un RAF", ""
            if not testa.startswith(b"FUJIFILMCCD-RAW"):
                return False, "non è un RAF Fujifilm (firma errata)", ""
            if len(testa) < 92: return False, "RAF troncato", ""
            off, ln = struct.unpack(">II", testa[84:92])
            if off == 0 or ln == 0 or off + ln > size:
                return False, "RAF incoerente (anteprima fuori dal file)", ""
            if len(testa) >= 108:
                cfa_off, cfa_len = struct.unpack(">II", testa[100:108])
                if cfa_off == 0 or cfa_off + cfa_len > size:
                    return False, "RAF troncato (dati immagine incompleti)", ""
            f.seek(off)
            if f.read(3) != b"\xff\xd8\xff":
                return False, "RAF senza anteprima JPEG valida", ""
            modello = testa[28:60].split(b"\0")[0].decode("ascii", "replace").strip()
            return True, "RAF valido", modello
        if ext in ("jpg", "jpeg"):
            if size > MAX_JPG: return False, "troppo grande per un JPG", ""
            if not testa.startswith(b"\xff\xd8\xff"):
                return False, "non è un JPEG (firma errata)", ""
            return True, "JPG valido", ""
        if ext in ("hif", "heif", "heic"):
            if size > MAX_HIF: return False, "troppo grande per un HEIF", ""
            if testa[4:8] != b"ftyp" or testa[8:12] not in MARCHI_HEIF:
                return False, "non è un HEIF (firma errata)", ""
            return True, "HEIF valido", ""
        if ext == "txt":
            if size > MAX_TXT: return False, "testo troppo lungo", ""
            f.seek(0); dati = f.read()
            if b"\0" in dati: return False, "il .txt contiene dati binari", ""
            try: testo = dati.decode("utf-8")
            except UnicodeDecodeError: return False, "il .txt non è testo UTF-8", ""
            for ch in testo:
                o = ord(ch)
                if (o < 32 and ch not in "\n\r\t") or o == 127 or 0x80 <= o < 0xA0:
                    return False, "il .txt contiene caratteri di controllo", ""
                if 0x202A <= o <= 0x202E or 0x2066 <= o <= 0x2069 or o in (0x200E, 0x200F, 0x061C):
                    return False, "il .txt contiene caratteri che invertono il testo", ""
            if any(len(r) > 500 for r in testo.splitlines()):
                return False, "il .txt ha righe troppo lunghe", ""
            return True, "testo ok", ""
    return False, "tipo non ammesso (solo RAF, JPG, HIF, txt)", ""

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sposta = "--sposta-scartati" in sys.argv
    dest = None
    if "--ordina" in sys.argv:
        i = sys.argv.index("--ordina")
        if i + 1 >= len(sys.argv) or sys.argv[i + 1].startswith("--"):
            print(__doc__); sys.exit(2)
        dest = sys.argv[i + 1]
        args = [a for a in args if a != dest]
    if len(args) != 1 or not os.path.isdir(args[0]):
        print(__doc__); sys.exit(2)
    cart = args[0]
    ok_n = ko_n = 0
    accettati, modelli = [], set()
    scart = os.path.join(cart, "_SCARTATI")
    for nome in sorted(os.listdir(cart)):
        if nome == "_SCARTATI": continue
        p = os.path.join(cart, nome)
        ok, msg, mod = controlla(p)
        if ok:
            ok_n += 1
            accettati.append(p)
            if mod: modelli.add(mod)
            print(f"OK         {nome}  [{msg}{', ' + mod if mod else ''}]  sha256={sha256(p)[:16]}…")
        else:
            ko_n += 1
            print(f"RIFIUTATO  {nome}  [{msg}]")
            if sposta:
                os.makedirs(scart, exist_ok=True)
                os.rename(p, os.path.join(scart, nome + ".scartato"))
    if dest and accettati:
        modello = re.sub(r"[^A-Za-z0-9._-]", "_", modelli.pop()) if len(modelli) == 1 else "DA-CLASSIFICARE"
        lotto = datetime.date.today().isoformat() + "-" + re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(os.path.abspath(cart)))
        d = os.path.join(dest, modello, lotto)
        os.makedirs(d, exist_ok=True)
        righe = []
        for p in accettati:
            n = os.path.basename(p)
            shutil.move(p, os.path.join(d, n))
            righe.append(f"{sha256(os.path.join(d, n))}  {n}")
        with open(os.path.join(d, "SHA256SUMS"), "w") as f:
            f.write("\n".join(righe) + "\n")
        print(f"\nSpostati {len(accettati)} file in: {d}\nElenco impronte: {os.path.join(d, 'SHA256SUMS')}")
    print(f"\nTotale: {ok_n} accettati, {ko_n} rifiutati. Nulla è stato aperto o eseguito.")
    sys.exit(0 if ko_n == 0 else 1)

if __name__ == "__main__":
    main()
