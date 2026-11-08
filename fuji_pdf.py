"""Provino a contatto in PDF: le foto scelte in griglia, numerate, con nome, data e pellicola.

Scritto senza librerie esterne: le immagini sono JPEG gia' pronti (anteprime), inseriti cosi' come sono
(DCTDecode). Testo in Helvetica con codifica WinAnsi (lettere accentate italiane comprese).
Licenza MIT.
"""
import struct
import zlib

A4 = (595.28, 841.89)          # punti (1/72 di pollice)


def jpeg_size(data):
    """Larghezza e altezza di un JPEG (dal marcatore SOF)."""
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        m = data[i + 1]
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        ln = struct.unpack(">H", data[i + 2:i + 4])[0]
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            comps = data[i + 9]
            return w, h, comps
        i += 2 + ln
    return None


def _txt(s):
    """Stringa PDF in WinAnsi, con le parentesi protette."""
    b = str(s).encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _width(s, size, bold=False):
    """Larghezza approssimata del testo in Helvetica (per centrare e accorciare)."""
    return len(str(s)) * size * (0.56 if bold else 0.52)


def _fit(s, size, maxw, bold=False):
    s = str(s)
    while s and _width(s, size, bold) > maxw:
        s = s[:-2] + "…" if len(s) > 2 else ""
    return s


def _stream(data, dict_extra=b""):
    return b"<< %s /Length %d >>\nstream\n" % (dict_extra, len(data)) + data + b"\nendstream"


def read_choices(path):
    """Le foto spuntate in un PDF di Provino rimandato indietro (anche se salvato da Anteprima, Acrobat o
    dal telefono, che possono comprimere e riscrivere il file). Restituisce la lista dei nomi, in ordine."""
    import re
    with open(path, "rb") as fh:
        raw = fh.read()
    if not raw.startswith(b"%PDF"):
        raise ValueError("non e' un PDF")
    texts = [raw]
    for m in re.finditer(rb"stream\r?\n", raw):
        start = m.end()
        end = raw.find(b"endstream", start)
        if end < 0:
            continue
        if raw[start:start + 1] != b"\x78":      # solo flussi compressi con zlib (non le foto JPEG)
            continue
        try:
            texts.append(zlib.decompressobj().decompress(raw[start:end]))
        except zlib.error:
            pass
    state, order = {}, []
    name_re = re.compile(rb"/T\s*\(((?:[^()\\]|\\.)*)\)|/T\s*<([0-9A-Fa-f\s]+)>", re.S)
    for t in texts:
        for m in name_re.finditer(t):
            if m.group(1) is not None:
                name = _unescape(m.group(1))
                if name[:2] == "\xfe\xff":
                    name = name[2:].encode("latin-1").decode("utf-16-be", "ignore")
                if not name.startswith("P:"):
                    continue
            else:
                hx = bytes.fromhex(re.sub(rb"\s", b"", m.group(2)).decode())
                name = hx[2:].decode("utf-16-be", "ignore") if hx[:2] == b"\xfe\xff" else hx.decode("latin-1")
                if not name.startswith("P:"):
                    continue
            seg = _enclosing_dict(t, m.start())
            v = re.search(rb"/V\s*/(\w+)", seg)
            a_ = re.search(rb"/AS\s*/(\w+)", seg)
            val = (v or a_)
            base = name[2:]
            if base not in state:
                order.append(base)
                state[base] = False
            if val is not None:
                state[base] = val.group(1) not in (b"Off",)      # l'ultima versione salvata vince
    return [b for b in order if state.get(b)]


def _unescape(b):
    """Stringa letterale PDF: \\072 -> ':', \\( -> '(' ecc."""
    import re
    def rep(m):
        x = m.group(1)
        if x[:1].isdigit():
            return bytes([int(x, 8) & 0xFF])
        return {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}.get(x, x)
    return re.sub(rb"\\([0-7]{1,3}|.)", rep, b, flags=re.S).decode("latin-1")


def _enclosing_dict(t, pos):
    """Il dizionario << ... >> che contiene la posizione pos (tenendo conto di quelli annidati)."""
    depth, i, start = 0, pos, 0
    while i > 0:
        two = t[i - 1:i + 1]
        if two == b">>":
            depth += 1
            i -= 2
        elif two == b"<<":
            if depth == 0:
                start = i - 1
                break
            depth -= 1
            i -= 2
        else:
            i -= 1
    depth, j = 0, start
    while j < len(t) - 1:
        two = t[j:j + 2]
        if two == b"<<":
            depth += 1
            j += 2
        elif two == b">>":
            depth -= 1
            j += 2
            if depth == 0:
                return t[start:j]
        else:
            j += 1
    return t[start:start + 2000]


class _Doc:
    def __init__(self):
        self.objs = []

    def add(self, body):
        self.objs.append(body)
        return len(self.objs)

    def set(self, n, body):
        self.objs[n - 1] = body

    def save(self, path, root):
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offs = []
        for i, o in enumerate(self.objs, 1):
            offs.append(len(out))
            out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
        x = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(self.objs) + 1)
        for o in offs:
            out += b"%010d 00000 n \n" % o
        out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(self.objs) + 1, root, x)
        with open(path, "wb") as fh:
            fh.write(out)


def build(path, items, title, subtitle="", footer="", cols=3, rows=4, dark=False, check_label=""):
    """items: lista di dict {jpeg: bytes, name, line2, line3}. Scrive il PDF in path e ne restituisce le pagine.
    Con check_label, sotto ogni foto c'e' una casella da spuntare (modulo PDF): chi riceve il file la spunta
    in Anteprima, Acrobat o sul telefono e lo rimanda; Provino poi rilegge le scelte (read_choices)."""
    W, H = A4
    M = 36.0                      # margine
    head = 64.0                   # spazio per il titolo (solo prima pagina) e per l'intestazione
    gap = 14.0
    cap = 40.0                    # spazio per le didascalie sotto la foto
    per = cols * rows
    cw = (W - 2 * M - gap * (cols - 1)) / cols
    ch = (H - 2 * M - head - 18 - gap * (rows - 1)) / rows
    pw, ph = cw, ch - cap         # riquadro della foto
    bg = (0.11, 0.11, 0.12) if dark else (1, 1, 1)
    ink = (0.95, 0.95, 0.95) if dark else (0.1, 0.1, 0.1)
    soft = (0.65, 0.65, 0.65) if dark else (0.42, 0.42, 0.42)
    frame = (0.2, 0.2, 0.21) if dark else (0.94, 0.94, 0.94)

    doc = _Doc()
    catalog = doc.add(b"")
    pages_n = doc.add(b"")
    font = doc.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    fontb = doc.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    zadb = doc.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>")
    BOX = 13.0
    ap_off = doc.add(_stream(b"1 1 1 rg 0.45 0.45 0.45 RG 0.8 w 0.5 0.5 %.1f %.1f re B" % (BOX - 1, BOX - 1),
                             b"/Type /XObject /Subtype /Form /BBox [0 0 %.1f %.1f]" % (BOX, BOX)))
    ap_yes = doc.add(_stream(b"1 1 1 rg 0.45 0.45 0.45 RG 0.8 w 0.5 0.5 %.1f %.1f re B "
                             b"0.1 0.5 0.2 RG 1.8 w 1 J 1 j 3 6.8 m 5.6 4 l 10.2 9.6 l S" % (BOX - 1, BOX - 1),
                             b"/Type /XObject /Subtype /Form /BBox [0 0 %.1f %.1f] /Resources << /Font << /ZaDb %d 0 R >> >>"
                             % (BOX, BOX, zadb)))
    fields = []
    kids = []
    npages = max(1, (len(items) + per - 1) // per)
    for p in range(npages):
        chunk = items[p * per:(p + 1) * per]
        xobjs, cs, annots = [], [], []
        col = lambda c: b"%.3f %.3f %.3f" % c  # noqa: E731
        cs.append(col(bg) + b" rg 0 0 %.2f %.2f re f" % (W, H))
        top = H - M
        cs.append(b"BT /F2 18 Tf " + col(ink) + b" rg %.2f %.2f Td (%s) Tj ET" % (M, top - 18, _txt(title)))
        right = "%s  ·  %d/%d" % (subtitle, p + 1, npages) if subtitle else "%d/%d" % (p + 1, npages)
        cs.append(b"BT /F1 9.5 Tf " + col(soft) + b" rg %.2f %.2f Td (%s) Tj ET"
                  % (M, top - 36, _txt(right)))
        cs.append(col(soft) + b" RG 0.5 w %.2f %.2f m %.2f %.2f l S" % (M, top - 48, W - M, top - 48))
        y0 = top - head
        for k, it in enumerate(chunk):
            r, c = divmod(k, cols)
            x = M + c * (cw + gap)
            y = y0 - r * (ch + gap)            # bordo alto della cella
            cs.append(col(frame) + b" rg %.2f %.2f %.2f %.2f re f" % (x, y - ph, pw, ph))
            info = jpeg_size(it["jpeg"])
            if info:
                iw, ih, comps = info
                s = min(pw / iw, ph / ih)
                dw, dh = iw * s, ih * s
                dx, dy = x + (pw - dw) / 2, y - ph + (ph - dh) / 2
                cspace = b"/DeviceGray" if comps == 1 else (b"/DeviceCMYK" if comps == 4 else b"/DeviceRGB")
                im = doc.add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace %s "
                             b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n"
                             % (iw, ih, cspace, len(it["jpeg"])) + it["jpeg"] + b"\nendstream")
                nm = b"Im%d" % (k + 1)
                xobjs.append(b"/%s %d 0 R" % (nm, im))
                cs.append(b"q %.3f 0 0 %.3f %.3f %.3f cm /%s Do Q" % (dw, dh, dx, dy, nm))
            num = str(p * per + k + 1)
            # numero nel cerchietto in alto a sinistra: e' quello che la persona ti risponde ("mi piace la 7")
            bx, by, rr = x + 13, y - 13, 9.5
            kappa = 0.5523 * rr
            cs.append(b"0.1 0.1 0.1 rg")
            cs.append(b"%.2f %.2f m %.2f %.2f %.2f %.2f %.2f %.2f c %.2f %.2f %.2f %.2f %.2f %.2f c "
                      b"%.2f %.2f %.2f %.2f %.2f %.2f c %.2f %.2f %.2f %.2f %.2f %.2f c f"
                      % (bx + rr, by, bx + rr, by + kappa, bx + kappa, by + rr, bx, by + rr,
                         bx - kappa, by + rr, bx - rr, by + kappa, bx - rr, by,
                         bx - rr, by - kappa, bx - kappa, by - rr, bx, by - rr,
                         bx + kappa, by - rr, bx + rr, by - kappa, bx + rr, by))
            fs = 9.5 if len(num) < 3 else 8
            cs.append(b"BT /F2 %.1f Tf 1 1 1 rg %.2f %.2f Td (%s) Tj ET"
                      % (fs, bx - _width(num, fs, True) / 2, by - fs * 0.36, _txt(num)))
            ty = y - ph - 13
            namew = pw
            if check_label:
                # casella da spuntare a destra del nome, con l'etichetta ("Mi piace")
                lw = _width(check_label, 8.5)
                bx0 = x + pw - BOX
                by0 = ty - 3
                cs.append(b"BT /F1 8.5 Tf " + col(soft) + b" rg %.2f %.2f Td (%s) Tj ET"
                          % (bx0 - 4 - lw, ty, _txt(check_label)))
                fid = "P:" + str(it.get("name", "")).replace("(", "").replace(")", "").replace("\\", "")
                w_ = doc.add(b"<< /Type /Annot /Subtype /Widget /FT /Btn /T (%s) /Rect [%.2f %.2f %.2f %.2f] /F 4 "
                             b"/V /Off /AS /Off /MK << /CA (4) /BC [0.45 0.45 0.45] /BG [1 1 1] >> "
                             b"/DA (/ZaDb 0 Tf 0.1 0.45 0.2 rg) /AP << /N << /Yes %d 0 R /Off %d 0 R >> >> >>"
                             % (_txt(fid), bx0, by0, bx0 + BOX, by0 + BOX, ap_yes, ap_off))
                annots.append(w_)
                fields.append(w_)
                namew = pw - BOX - 8 - lw
            cs.append(b"BT /F2 9.5 Tf " + col(ink) + b" rg %.2f %.2f Td (%s) Tj ET"
                      % (x, ty, _txt(_fit(it.get("name", ""), 9.5, namew, True))))
            if it.get("line2"):
                cs.append(b"BT /F1 8.5 Tf " + col(soft) + b" rg %.2f %.2f Td (%s) Tj ET"
                          % (x, ty - 12, _txt(_fit(it["line2"], 8.5, pw))))
            if it.get("line3"):
                cs.append(b"BT /F1 8.5 Tf " + col(soft) + b" rg %.2f %.2f Td (%s) Tj ET"
                          % (x, ty - 23, _txt(_fit(it["line3"], 8.5, pw))))
        if footer:
            cs.append(b"BT /F1 7.5 Tf " + col(soft) + b" rg %.2f %.2f Td (%s) Tj ET" % (M, M - 14, _txt(footer)))
        stream = zlib.compress(b"\n".join(x for x in cs if x))
        content = doc.add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
        res = b"<< /Font << /F1 %d 0 R /F2 %d 0 R >> /XObject << %s >> >>" % (font, fontb, b" ".join(xobjs))
        ann = b" /Annots [%s]" % b" ".join(b"%d 0 R" % a for a in annots) if annots else b""
        kids.append(doc.add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] /Resources %s /Contents %d 0 R%s >>"
                            % (pages_n, W, H, res, content, ann)))
    doc.set(pages_n, b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids)))
    form = b""
    if fields:
        form = (b" /AcroForm << /Fields [%s] /NeedAppearances false /DA (/ZaDb 0 Tf 0 g) /DR << /Font << /ZaDb %d 0 R >> >> >>"
                % (b" ".join(b"%d 0 R" % f for f in fields), zadb))
    doc.set(catalog, b"<< /Type /Catalog /Pages %d 0 R%s >>" % (pages_n, form))
    doc.save(path, catalog)
    return npages
