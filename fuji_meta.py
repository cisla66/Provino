"""Provino - lettura dei metadati di uno scatto Fujifilm (EXIF + "ricetta" nella makernote).

Legge solo l'inizio del JPEG (o del JPEG incorporato nel RAF): bastano ~128 KB.
I codici delle impostazioni Fujifilm non sono documentati: i significati vengono dalle
tabelle di ExifTool (Image::ExifTool::FujiFilm, Phil Harvey), verificate dove indicato.

Restituisce valori neutri (codici e numeri), che l'interfaccia traduce in italiano/inglese.
"""
import struct

TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}

# ---------------------------------------------------------------- tabelle (da ExifTool)
FILM = {0x000: "provia", 0x100: "studio_portrait", 0x110: "studio_portrait_sat",
        0x120: "astia", 0x130: "studio_portrait_sharp", 0x200: "velvia", 0x300: "studio_portrait_ex",
        0x400: "velvia", 0x500: "pro_neg_std", 0x501: "pro_neg_hi", 0x600: "classic_chrome",
        0x700: "eterna", 0x800: "classic_neg", 0x900: "eterna_bleach", 0xA00: "nostalgic_neg",
        0xB00: "reala_ace"}
# per le pellicole in bianco e nero il tag FilmMode manca e la "Saturation" dice quale
MONO = {0x300: "monochrome", 0x301: "monochrome_r", 0x302: "monochrome_ye", 0x303: "monochrome_g",
        0x310: "sepia", 0x500: "acros", 0x501: "acros_r", 0x502: "acros_ye", 0x503: "acros_g"}
COLOR = {0x0: 0, 0x080: 1, 0x100: 2, 0x0C0: 3, 0x0E0: 4, 0x180: -1, 0x400: -2, 0x4C0: -3, 0x4E0: -4}
SHARP = {0x00: -4, 0x01: -3, 0x02: -2, 0x03: 0, 0x04: 2, 0x05: 3, 0x06: 4, 0x82: -1, 0x84: 1}
NR = {0x000: 0, 0x100: 2, 0x180: 1, 0x1C0: 3, 0x1E0: 4, 0x200: -2, 0x280: -1, 0x2C0: -3, 0x2E0: -4}
WB = {0x0: "auto", 0x1: "auto_white", 0x2: "auto_ambience", 0x100: "daylight", 0x200: "shade",
      0x300: "fluo1", 0x301: "fluo2", 0x302: "fluo3", 0x303: "fluo_warm", 0x304: "fluo_living",
      0x400: "incandescent", 0x500: "flash", 0x600: "underwater", 0xF00: "custom1", 0xF01: "custom2",
      0xF02: "custom3", 0xF03: "custom4", 0xF04: "custom5", 0xFF0: "kelvin"}
STRENGTH = {0: "off", 32: "weak", 64: "strong"}
GRAIN_ROUGH = {0: "off", 16: "weak", 32: "weak", 48: "strong", 64: "strong"}
GRAIN_SIZE = {0: "off", 16: "small", 32: "large"}
SHUTTER = {0: "mechanical", 1: "electronic", 2: "electronic", 3: "efc"}
DR_PRIO_AUTO = {1: "weak", 2: "strong", 3: "plus"}
DR_PRIO_FIXED = {1: "weak", 2: "strong"}
EXPO_PROGRAM = {1: "manual", 2: "program", 3: "aperture", 4: "shutter"}


def _ifd(buf, off, en, base=0):
    """Voci di una IFD: dict tag -> (tipo, conteggio, byte del valore)."""
    out = {}
    try:
        (n,) = struct.unpack(en + "H", buf[off:off + 2])
    except struct.error:
        return out
    if n > 500:
        return out
    for i in range(n):
        e = buf[off + 2 + 12 * i: off + 14 + 12 * i]
        if len(e) < 12:
            break
        tag, typ, cnt = struct.unpack(en + "HHI", e[:8])
        size = TYPE_SIZE.get(typ, 1) * cnt
        if size <= 4:
            raw = e[8:8 + size]
        else:
            (p,) = struct.unpack(en + "I", e[8:12])
            raw = buf[base + p: base + p + size]
            if len(raw) < size:
                continue
        out[tag] = (typ, cnt, raw)
    return out


def _val(entry, en, index=0):
    if not entry:
        return None
    typ, cnt, raw = entry
    try:
        if typ == 2:
            return raw.split(b"\0", 1)[0].decode("ascii", "replace").strip()
        if typ in (1, 7):
            return raw[index]
        if typ == 6:
            return struct.unpack("b", raw[index:index + 1])[0]
        if typ == 3:
            return struct.unpack_from(en + "H", raw, 2 * index)[0]
        if typ == 8:
            return struct.unpack_from(en + "h", raw, 2 * index)[0]
        if typ == 4:
            return struct.unpack_from(en + "I", raw, 4 * index)[0]
        if typ == 9:
            return struct.unpack_from(en + "i", raw, 4 * index)[0]
        if typ in (5, 10):
            a, b = struct.unpack_from(en + ("II" if typ == 5 else "ii"), raw, 8 * index)
            return a / b if b else None
    except (struct.error, IndexError):
        return None
    return None


def parse(buf):
    """Metadati da un JPEG (anche parziale). Restituisce {} se non trova l'EXIF."""
    # il primo "Exif\0\0" valido: nei file HEIF (.HIF) la parola compare prima anche come nome di un blocco
    i = -1
    j = buf.find(b"Exif\0\0")
    while j >= 0:
        if buf[j + 6:j + 10] in (b"II*\0", b"MM\0*"):
            i = j
            break
        j = buf.find(b"Exif\0\0", j + 6)
    if i < 0:
        return {}
    t = buf[i + 6:]
    en = "<" if t[:2] == b"II" else ">"
    try:
        (ifd0,) = struct.unpack(en + "I", t[4:8])
    except struct.error:
        return {}
    d0 = _ifd(t, ifd0, en)
    meta = {}
    model = _val(d0.get(0x0110), en)
    if model:
        meta["model"] = model
    ori = _val(d0.get(0x0112), en)
    if ori in (3, 6, 8):
        meta["orientation"] = {3: 180, 6: 90, 8: 270}[ori]   # gradi in senso orario
    res, unit = _val(d0.get(0x011A), en), _val(d0.get(0x0128), en)   # XResolution, ResolutionUnit
    if res and res > 0:
        meta["dpi"] = round(res * 2.54) if unit == 3 else round(res)       # 3 = per centimetro
    sw = _val(d0.get(0x0131), en) or ""
    if "Ver" in sw:
        meta["firmware"] = sw.rsplit("Ver", 1)[1].strip()
    exif_off = _val(d0.get(0x8769), en)
    if exif_off:
        ex = _ifd(t, exif_off, en)
        g = lambda tag: _val(ex.get(tag), en)  # noqa: E731
        exp = g(0x829A)
        if exp:
            meta["exposure"] = exp
        for key, tag in (("fnumber", 0x829D), ("iso", 0x8827), ("focal", 0x920A),
                         ("focal35", 0xA405), ("ev", 0x9204), ("program", 0x8822)):
            v = g(tag)
            if v is not None:
                meta[key] = v
        if "program" in meta:
            meta["program"] = EXPO_PROGRAM.get(meta["program"], "")
        w, h = g(0xA002), g(0xA003)
        if w and h:
            meta["width"], meta["height"] = w, h
        lens = g(0xA434)
        if lens:
            meta["lens"] = lens
        dt = g(0x9003)
        if dt:
            meta["date"] = dt
        serial = g(0xA431)
        if serial:
            meta["serial"] = serial
    meta.update(_recipe(buf))
    # verticale? o lo dice l'orientamento (pixel orizzontali da girare) o i pixel sono gia' verticali
    if meta.get("orientation") in (90, 270) or (meta.get("height", 0) > meta.get("width", 0) > 0):
        meta["portrait"] = True
    meta["orientation_raw"] = ori or 0
    return meta


def _recipe(buf):
    m = buf.find(b"FUJIFILM\x0c\x00\x00\x00")
    if m < 0:
        return {}
    mn = buf[m:]
    try:
        (off,) = struct.unpack("<I", mn[8:12])
    except struct.error:
        return {}
    d = _ifd(mn, off, "<")
    g = lambda tag: _val(d.get(tag), "<")  # noqa: E731
    r = {}
    shots = g(0x1438)
    if shots is not None:
        r["shots"] = shots & 0x7FFF   # contatore immagini, si azzera: non e' il totale scatti
    sat = g(0x1003)
    film = g(0x1401)
    if sat in MONO:
        r["film"] = MONO[sat]
        wc, mg = g(0x1049), g(0x104B)
        if wc is not None:
            r["mono_wc"] = _s8(wc)
        if mg is not None:
            r["mono_mg"] = _s8(mg)
    elif film is not None:
        r["film"] = FILM.get(film, "0x%X" % film)
        if sat in COLOR:
            r["color"] = COLOR[sat]
    rough, size = g(0x1047), g(0x104C)
    if rough is not None:
        r["grain"] = GRAIN_ROUGH.get(rough, "?")
        if r["grain"] != "off":
            r["grain_size"] = GRAIN_SIZE.get(size, "small" if rough in (16, 48) else "large") \
                if size is not None else ("small" if rough in (16, 48) else "large")
    for key, tag in (("chrome", 0x1048), ("chrome_blue", 0x104E)):
        v = g(tag)
        if v is not None:
            r[key] = STRENGTH.get(v, "?")
    wb = g(0x1002)
    if wb is not None:
        r["wb"] = WB.get(wb, "0x%X" % wb)
        if r["wb"] == "kelvin":
            k = g(0x1005)
            if k:
                r["wb_kelvin"] = k
        ft = d.get(0x100A)
        if ft:
            red, blue = _val(ft, "<", 0), _val(ft, "<", 1)
            if red is not None and blue is not None:
                # le fotocamere recenti scrivono i passi x20 (nota di ExifTool, verificato X100VI: 180 = +9)
                big = abs(red) > 9 or abs(blue) > 9
                r["wb_shift"] = [int(red / 20) if big else red, int(blue / 20) if big else blue]
    for key, tag in (("highlight", 0x1041), ("shadow", 0x1040)):
        v = g(tag)
        if v is not None:
            r[key] = -v / 16
    sh = g(0x1001)
    if sh is not None and sh in SHARP:
        r["sharpness"] = SHARP[sh]
    nr = g(0x100E)
    if nr is not None and nr in NR:
        r["nr"] = NR[nr]
    cl = g(0x100F)
    if cl is not None:
        r["clarity"] = int(cl / 1000)
    drs, drd = g(0x1402), g(0x1403)
    if drs is not None:
        r["dr"] = "auto" if drs == 0 else (("DR%d" % drd) if drd else "DR100")
    prio = g(0x1443)
    if prio is not None:
        r["dr_priority"] = DR_PRIO_AUTO.get(g(0x1444), "auto") if prio == 0 else \
            DR_PRIO_FIXED.get(g(0x1445), "?")
        if prio == 0 and g(0x1444) is None:
            r.pop("dr_priority")
    st = g(0x1050)
    if st is not None:
        r["shutter"] = SHUTTER.get(st, "?")
    return r


def _s8(v):
    return v - 256 if v > 127 else v


def recipe_key(meta):
    """Chiave breve per raggruppare scatti con la stessa ricetta."""
    keys = ("film", "grain", "grain_size", "chrome", "chrome_blue", "wb", "wb_kelvin", "wb_shift",
            "highlight", "shadow", "color", "sharpness", "nr", "clarity", "dr", "mono_wc", "mono_mg")
    return "|".join("%s=%s" % (k, meta.get(k)) for k in keys if k in meta)


if __name__ == "__main__":
    import json
    import sys
    for p in sys.argv[1:]:
        with open(p, "rb") as fh:
            head = fh.read(0x20000)
            if head[:15] == b"FUJIFILMCCD-RAW":
                off, ln = struct.unpack(">II", head[84:92])
                fh.seek(off)
                head = fh.read(min(ln, 0x20000))
        print(p, json.dumps(parse(head), ensure_ascii=False))
