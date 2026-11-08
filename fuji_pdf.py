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


def build(path, items, title, subtitle="", footer="", cols=3, rows=4, dark=False):
    """items: lista di dict {jpeg: bytes, name, line2, line3}. Scrive il PDF in path e ne restituisce le pagine."""
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
    kids = []
    npages = max(1, (len(items) + per - 1) // per)
    for p in range(npages):
        chunk = items[p * per:(p + 1) * per]
        xobjs, cs = [], []
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
            cs.append(b"BT /F2 9.5 Tf " + col(ink) + b" rg %.2f %.2f Td (%s) Tj ET"
                      % (x, ty, _txt(_fit(it.get("name", ""), 9.5, pw, True))))
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
        kids.append(doc.add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] /Resources %s /Contents %d 0 R >>"
                            % (pages_n, W, H, res, content)))
    doc.set(pages_n, b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids)))
    doc.set(catalog, b"<< /Type /Catalog /Pages %d 0 R >>" % pages_n)
    doc.save(path, catalog)
    return npages
