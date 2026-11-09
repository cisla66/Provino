#!/usr/bin/env python3
"""
Provino in una finestra nativa GNOME (Linux), invece che nel browser.

Usa i componenti gia' presenti nei sistemi GNOME (verificato il 6 nov 2026 su Fedora 45):
GTK 4, WebKitGTK 6.0 e libadwaita, tramite PyGObject. Nessun pacchetto da installare.
La pagina e' la stessa dell'interfaccia web: cambia solo la finestra che la contiene.

Avvio:  python3 provino_finestra.py   (opzioni come provino.py, per esempio --verbose)
Chiudere la finestra chiude anche Provino e saluta la fotocamera.
"""
import argparse
import datetime
import os
import shutil
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Adw, Gdk, Gio, GLib, Gtk, WebKit
except (ImportError, ValueError) as e:
    print("Mancano i componenti GNOME per la finestra (%s)." % e)
    print("Su Fedora: sudo dnf install webkitgtk6.0 libadwaita python3-gobject")
    print("Intanto puoi usare Provino nel browser: python3 provino.py")
    sys.exit(1)

import json  # noqa: E402
import provino as pv  # noqa: E402
import provino_wifi as fw  # noqa: E402

APP_ID = "io.github.cisla66.Provino"


def start_core(args):
    """Avvia Provino (server locale, download, controlli) senza browser. Ritorna (app, srv, url, log)."""
    os.makedirs(args.dest, exist_ok=True)
    logdir = os.path.join(pv.DATA, "log")
    os.makedirs(logdir, exist_ok=True)
    log = fw.Log(os.path.join(logdir, "app_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")),
                 verbose=args.verbose)
    log.info("Provino %s (modulo %s) - Python %s - %s - finestra GNOME" % (
        pv.APP_VERSION, fw.VERSION, sys.version.split()[0], sys.platform))
    pv.close_old_instances(log)
    app = pv.App(args.dest, False, fw.CAM_IP, log)
    port = pv.free_port()
    srv = pv.ThreadingHTTPServer(("127.0.0.1", port), pv.make_handler(app))
    srv.daemon_threads = True
    for target in (app.worker, app.keepalive, app.watch_folder, srv.serve_forever):
        threading.Thread(target=target, daemon=True).start()
    url = "http://127.0.0.1:%d/" % port
    log.info("Interfaccia (finestra): %s" % url)
    return app, srv, url, log


class Ring(Gtk.Widget):
    """Anello di avanzamento disegnato con GSK (niente cairo): blu mentre scarica, segno di spunta alla fine."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.set_size_request(18, 18)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)

    def do_snapshot(self, snap):
        import math
        from gi.repository import Graphene, Gsk
        w, h = self.get_width(), self.get_height()
        tr = self.owner.tr
        mode, pct = tr["mode"], tr["pct"]
        try:
            fg = self.get_color()
        except AttributeError:
            fg = self.owner._rgba("#808080")
        track = fg.copy()
        track.alpha = 0.22
        acc = self.owner._ring_colors()
        cx, cy, r = w / 2, h / 2, min(w, h) / 2 - 1.5
        stroke = Gsk.Stroke.new(2.4)
        stroke.set_line_cap(Gsk.LineCap.ROUND)

        def circle(color):
            pb = Gsk.PathBuilder.new()
            pb.add_circle(Graphene.Point().init(cx, cy), r)
            snap.append_stroke(pb.to_path(), stroke, color)

        def poly(points, color):
            pb = Gsk.PathBuilder.new()
            pb.move_to(*points[0])
            for p in points[1:]:
                pb.line_to(*p)
            snap.append_stroke(pb.to_path(), stroke, color)

        if mode == "run":
            circle(track)
            f = max(0.03, min(1.0, pct / 100.0))
            if f >= 0.999:
                circle(acc)
                return
            a0, a1 = -math.pi / 2, -math.pi / 2 + 2 * math.pi * f
            pb = Gsk.PathBuilder.new()
            pb.move_to(cx + r * math.cos(a0), cy + r * math.sin(a0))
            steps = max(2, int(48 * f))
            for i in range(1, steps + 1):
                a = a0 + (a1 - a0) * i / steps
                pb.line_to(cx + r * math.cos(a), cy + r * math.sin(a))
            snap.append_stroke(pb.to_path(), stroke, acc)
        elif mode == "ok":
            circle(acc)
            poly([(cx - 3.6, cy + 0.2), (cx - 1, cy + 2.8), (cx + 3.8, cy - 2.4)], acc)
        elif mode == "warn":
            circle(acc)
            poly([(cx, cy - 3.6), (cx, cy + 0.6)], acc)
            poly([(cx, cy + 3.4), (cx, cy + 3.5)], acc)



# ------------------------------------------------------------ AppImage: icona e voce nel menu delle applicazioni
DESK_FILE = os.path.join(GLib.get_user_data_dir(), "applications", APP_ID + ".desktop")
ICON_DIR = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor")


_MOVED = [None]   # dove e' finito l'AppImage se l'ho spostato mentre Provino era aperto


def appimage_path():
    p = _MOVED[0] or os.environ.get("APPIMAGE")
    return p if p and os.path.isfile(p) else None


def menu_entry_path():
    """L'AppImage a cui punta la voce nel menu (None se non c'e' la voce). Legge anche la voce delle
    versioni di prova con il vecchio identificativo, cosi' l'aggiornamento la sostituisce."""
    for f in [DESK_FILE] + [os.path.join(os.path.dirname(DESK_FILE), o + ".desktop") for o in OLD_IDS]:
        p = _entry_target(f)
        if p:
            return p
    return None


def _entry_target(path):
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("X-Provino-AppImage="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def install_menu_entry(img=None):
    """Copia icona e voce .desktop nella cartella dell'utente (niente sudo): Provino compare in Attivita' e nel dock."""
    img, appdir = img or appimage_path(), os.environ.get("APPDIR") or ""
    if not img or not appdir:
        return False
    with open(os.path.join(appdir, APP_ID + ".desktop"), encoding="utf-8") as fh:
        lines = [x for x in fh.read().splitlines() if not x.startswith(("Exec=", "TryExec=", "X-Provino-AppImage="))]
    q = '"%s"' % img.replace('"', '\\"')
    lines = [x for x in lines if not x.startswith("StartupWMClass=")]
    lines += ["Exec=%s" % q, "TryExec=%s" % img, "StartupWMClass=%s" % APP_ID, "X-Provino-AppImage=%s" % img]
    os.makedirs(os.path.dirname(DESK_FILE), exist_ok=True)
    src = os.path.join(appdir, "usr", "share", "icons", "hicolor")
    for size in os.listdir(src) if os.path.isdir(src) else []:
        for ext in ("png", "svg"):
            f = os.path.join(src, size, "apps", APP_ID + "." + ext)
            if os.path.isfile(f):
                d = os.path.join(ICON_DIR, size, "apps")
                os.makedirs(d, exist_ok=True)
                shutil.copyfile(f, os.path.join(d, APP_ID + "." + ext))
    _remove_old_ids()
    tmp = DESK_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o755)
    os.replace(tmp, DESK_FILE)
    for cmd in (["gtk-update-icon-cache", "-f", "-t", ICON_DIR],
                ["update-desktop-database", os.path.dirname(DESK_FILE)]):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass
    return True


def apps_dir():
    """La cartella delle applicazioni nella home: ~/Applicazioni (o ~/Applications se esiste gia' quella)."""
    home = os.path.expanduser("~")
    for n in ("Applicazioni", "Applications", "AppImages"):
        if os.path.isdir(os.path.join(home, n)):
            return os.path.join(home, n)
    it = (GLib.get_language_names() or ["en"])[0].startswith("it")
    return os.path.join(home, "Applicazioni" if it else "Applications")


def in_apps_dir(img):
    return os.path.dirname(os.path.realpath(img)) == os.path.realpath(apps_dir())


def move_to_apps(img):
    """Sposta l'AppImage nella cartella delle applicazioni (il programma in esecuzione non se ne accorge)."""
    d = apps_dir()
    os.makedirs(d, exist_ok=True)
    dest = os.path.join(d, os.path.basename(img))
    if os.path.exists(dest) and not os.path.samefile(dest, img):
        os.remove(dest)                      # una versione precedente con lo stesso nome
    shutil.move(img, dest)
    os.chmod(dest, 0o755)
    _MOVED[0] = dest
    return dest


OLD_IDS = ("io.github.provino.Provino",)   # identificativi delle versioni di prova precedenti


def _remove_old_ids():
    for old in OLD_IDS:
        try:
            os.remove(os.path.join(os.path.dirname(DESK_FILE), old + ".desktop"))
        except OSError:
            pass
        for root, _dirs, files in os.walk(ICON_DIR):
            for f in files:
                if f.startswith(old + "."):
                    try:
                        os.remove(os.path.join(root, f))
                    except OSError:
                        pass


def remove_menu_entry():
    _remove_old_ids()
    try:
        os.remove(DESK_FILE)
    except OSError:
        pass
    for root, _dirs, files in os.walk(ICON_DIR):
        for f in files:
            if f.startswith(APP_ID + "."):
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass


class ProvinoApp(Adw.Application):
    def __init__(self, args):
        super().__init__(application_id=APP_ID)
        self.args = args
        self.core = None
        self.connect("activate", self.on_activate)
        self.connect("shutdown", self.on_shutdown)

    # testi della cornice (la pagina ha i suoi in i18n.js)
    TXT = {"it": {"download": "Scarica", "change": "Cambia fotocamera…", "changeShort": "Cambia fotocamera", "camera": "Fotocamera e collegamento",
                  "panel": "Foto grande e informazioni", "menu": "Menu principale",
                  "system": "Segui il sistema", "light": "Chiaro", "dark": "Scuro",
                  "about": "Informazioni su Provino", "quit": "Esci", "site": "Sito e guida",
                  "issues": "Segnala un problema", "comments": "Progetto indipendente, non affiliato a FUJIFILM Corporation.",
                  "all": "Tutto", "video": "Video", "films_all": "Tutte le pellicole", "pick": "Seleziona",
                  "pick_none": "Nessun file scelto", "sel_jpg": "Tutti i JPG", "sel_raf": "Tutti i RAF",
                  "sel_both": "Tutti i JPG e i RAF", "sel_heif": "Tutti gli HEIF", "sel_video": "Tutti i video",
                  "sel_fresh": "Solo quelli non ancora scaricati", "sel_visible": "Tutto quello che vedi",
                  "sel_none": "Deseleziona tutto", "by_type": "Seleziona per tipo, su tutta la scheda",
                  "dl_title": "Scarica {n} file", "folder": "Cartella", "choose": "Cambia…",
                  "by_date": "Una cartella per ogni giorno di scatto", "by_date_one": "Tutte le foto scelte sono del {d}",
                  "by_date_n": "Le foto scelte sono di {n} giorni: {n} cartelle", "split": "Separa per tipo",
                  "split_sub": "Sottocartelle {k}", "where": "Dove finiscono", "cancel": "Annulla",
                  "new_dirs": "In grassetto le cartelle che Provino crea adesso.", "choose_title": "Scegli la cartella",
                  "files": "file", "and": "e", "transfers": "Download in corso",
                  "prefs": "Preferenze", "keys": "Scorciatoie da tastiera", "p_dl": "Download",
                  "p_dl_sub": "Valgono come proposta: prima di ogni download puoi cambiarle.",
                  "p_by_date_sub": "Per esempio 2026-11-07", "p_split_sub": "Sottocartelle JPG, RAF, HEIF e VIDEO",
                  "p_look": "Aspetto", "p_lang": "Lingua", "p_theme": "Stile",
                  "p_safe": "Sicurezza", "p_safe_t": "Provino legge soltanto",
                  "p_safe_s": "Non cancella, non modifica e non formatta mai nulla sulla scheda.",
                  "k_photos": "Scelta delle foto", "k_all": "Scegli tutto quello che vedi", "k_none": "Deseleziona tutto",
                  "k_space": "Scegli o togli la foto corrente", "k_move": "Passa da una foto all'altra",
                  "k_view": "Foto grande", "k_full": "Foto intera, poi 100%", "k_back": "Torna alla griglia",
                  "k_app": "Generale", "k_dl": "Scarica i file scelti",
                  "menu_q": "Vuoi Provino tra le applicazioni, con la sua icona?", "menu_add": "Aggiungi",
                  "menu_done": "Provino è tra le applicazioni", "menu_fail": "Non sono riuscito ad aggiungerlo",
                  "menu_row": "Tra le applicazioni", "menu_row_sub": "Icona di Provino in Attività e nel dock",
                  "inst_h": "Installare Provino?",
                  "inst_b_move": "Lo sposto nella cartella %(dir)s, così non rischi di cancellarlo con i download, e lo aggiungo alle applicazioni con la sua icona.",
                  "inst_b": "Lo aggiungo alle applicazioni con la sua icona, così lo trovi in Attività e nel dock.",
                  "inst_yes_move": "Sposta e aggiungi", "inst_no": "Non ora",
                  "un_row": "Disinstalla Provino…", "un_h": "Disinstallare Provino?",
                  "un_b": "Tolgo Provino dalle applicazioni, cancello impostazioni e registri e metto il programma nel Cestino.\n\nLe foto scaricate (%(photos)s) non vengono toccate.",
                  "un_yes": "Disinstalla",
                  "upd_h": "Aggiornare Provino?",
                  "upd_b": "In %(dir)s c'è già Provino (%(old)s). Metto questa versione al suo posto e la vecchia nel Cestino. Impostazioni e foto restano come sono.",
                  "upd_yes": "Aggiorna", "upd_done": "Provino è aggiornato",
                  "upd_check": "Controlla aggiornamenti…", "upd_err": "Non riesco a controllare gli aggiornamenti adesso",
                  "upd_none": "Provino è aggiornato (%(c)s)", "upd_new": "È disponibile Provino %(v)s",
                  "upd_info": "Hai la versione %(c)s.", "upd_get": "Scarica", "upd_later": "Più tardi",
                  "upd_auto": "Controlla gli aggiornamenti all'avvio",
                  "pdf_sel": "Crea PDF delle foto scelte…", "pdf_vis": "Crea PDF di quello che vedi…",
                  "pdf_read": "Leggi le scelte da un PDF…"},
           "en": {"download": "Download", "change": "Change camera…", "changeShort": "Change camera", "camera": "Camera and connection",
                  "panel": "Large photo and info", "menu": "Main menu",
                  "system": "Follow system", "light": "Light", "dark": "Dark",
                  "about": "About Provino", "quit": "Quit", "site": "Website and guide",
                  "issues": "Report a problem", "comments": "Independent project, not affiliated with FUJIFILM Corporation.",
                  "all": "All", "video": "Video", "films_all": "All film simulations", "pick": "Select",
                  "pick_none": "No files picked", "sel_jpg": "All JPGs", "sel_raf": "All RAFs",
                  "sel_both": "All JPGs and RAFs", "sel_heif": "All HEIFs", "sel_video": "All videos",
                  "sel_fresh": "Only not downloaded yet", "sel_visible": "Everything you see",
                  "sel_none": "Deselect all", "by_type": "Select by type, across the card",
                  "dl_title": "Download {n} files", "folder": "Folder", "choose": "Change…",
                  "by_date": "One folder per shooting day", "by_date_one": "All picked photos are from {d}",
                  "by_date_n": "The picked photos span {n} days: {n} folders", "split": "Split by type",
                  "split_sub": "Subfolders {k}", "where": "Where they go", "cancel": "Cancel",
                  "new_dirs": "Folders in bold are created now.", "choose_title": "Choose the folder",
                  "files": "files", "and": "and", "transfers": "Downloads",
                  "prefs": "Preferences", "keys": "Keyboard Shortcuts", "p_dl": "Download",
                  "p_dl_sub": "These are suggestions: you can change them before each download.",
                  "p_by_date_sub": "For example 2026-11-07", "p_split_sub": "JPG, RAF, HEIF and VIDEO subfolders",
                  "p_look": "Appearance", "p_lang": "Language", "p_theme": "Style",
                  "p_safe": "Safety", "p_safe_t": "Provino only reads",
                  "p_safe_s": "It never deletes, changes or formats anything on the card.",
                  "k_photos": "Picking photos", "k_all": "Pick everything you see", "k_none": "Deselect all",
                  "k_space": "Pick or unpick the current photo", "k_move": "Move between photos",
                  "k_view": "Large photo", "k_full": "Full photo, then 100%", "k_back": "Back to the grid",
                  "k_app": "General", "k_dl": "Download the picked files",
                  "menu_q": "Add Provino to your applications, with its icon?", "menu_add": "Add",
                  "menu_done": "Provino is in your applications", "menu_fail": "Couldn't add it",
                  "menu_row": "In applications", "menu_row_sub": "Provino's icon in Activities and the dock",
                  "inst_h": "Install Provino?",
                  "inst_b_move": "I'll move it to %(dir)s, so you won't delete it along with your downloads, and add it to your applications with its icon.",
                  "inst_b": "I'll add it to your applications with its icon, so you'll find it in Activities and the dock.",
                  "inst_yes_move": "Move and Add", "inst_no": "Not Now",
                  "un_row": "Uninstall Provino…", "un_h": "Uninstall Provino?",
                  "un_b": "I'll remove Provino from your applications, delete its settings and logs and move the program to the Trash.\n\nYour downloaded photos (%(photos)s) are not touched.",
                  "un_yes": "Uninstall",
                  "upd_h": "Update Provino?",
                  "upd_b": "Provino is already in %(dir)s (%(old)s). I'll put this version in its place and move the old one to the Trash. Settings and photos stay as they are.",
                  "upd_yes": "Update", "upd_done": "Provino is up to date",
                  "upd_check": "Check for Updates…", "upd_err": "Can't check for updates right now",
                  "upd_none": "Provino is up to date (%(c)s)", "upd_new": "Provino %(v)s is available",
                  "upd_info": "You have version %(c)s.", "upd_get": "Download", "upd_later": "Later",
                  "upd_auto": "Check for updates at launch",
                  "pdf_sel": "Create PDF of Picked Photos…", "pdf_vis": "Create PDF of What You See…",
                  "pdf_read": "Read Choices from a PDF…"}}

    def t(self, key):
        return self.TXT.get(self.lang, self.TXT["it"]).get(key, key)

    def on_activate(self, *_):
        if self.get_active_window():
            self.get_active_window().present()   # gia' aperta: la porto davanti, niente seconda copia
            return
        self.core = start_core(self.args)
        app, srv, url, log = self.core
        self.log = log
        self.lang = (app.settings.get("ui_lang") if isinstance(getattr(app, "settings", None), dict) else None) or \
            ("it" if (os.environ.get("LANG") or "it").startswith("it") else "en")
        self.state = {}

        win = Adw.ApplicationWindow(application=self, title="Provino")
        win.set_default_size(1320, 860)
        win.set_icon_name(APP_ID)
        self.win = win

        # ---- la pagina, con il canale verso la finestra
        ucm = WebKit.UserContentManager()
        ucm.register_script_message_handler("provino", None)
        ucm.connect("script-message-received::provino", self.on_page_state)
        view = WebKit.WebView(user_content_manager=ucm)
        self.view = view
        # la pagina parla la lingua del sistema (come le app GNOME), se l'utente non ne ha scelta una
        try:
            sys_lang = (GLib.get_language_names() or ["it"])[0].split(".")[0].replace("_", "-")
            view.get_context().set_preferred_languages([sys_lang, "en"])
        except Exception:  # noqa: BLE001
            pass
        st = view.get_settings()
        st.set_enable_developer_extras(bool(self.args.verbose))
        st.set_javascript_can_access_clipboard(True)   # "Copia ricetta"
        # i link esterni (es. pagina firmware Fujifilm) si aprono nel browser, non nella finestra
        view.connect("decide-policy", self.on_policy)

        # ---- barra della finestra (stile GNOME): Fotocamera a sinistra, titolo, Scarica + pannello + menu a destra
        bar = Adw.HeaderBar()
        self.title = Adw.WindowTitle(title="Provino", subtitle="")
        bar.set_title_widget(self.title)

        cam_menu = Gio.Menu()
        cam_menu.append(self.t("change"), "app.change")
        # icona di Provino per "cambia fotocamera": fotocamera con le frecce di rotazione ai lati
        Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(os.path.join(HERE, "icons"))
        self.cam_btn = Gtk.MenuButton(menu_model=cam_menu, tooltip_text=self.t("camera"))
        # disegno largo: un po' piu' grande delle icone da 16 px, cosi' fotocamera e frecce si leggono
        self._cam_label = "?"
        self._cam_child(None)
        bar.pack_start(self.cam_btn)

        main_menu = self._main_menu()
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=main_menu, primary=True,
                                  tooltip_text=self.t("menu"))
        bar.pack_end(menu_btn)
        self.menu_btn = menu_btn

        self.panel_btn = Gtk.ToggleButton(icon_name="sidebar-show-right-symbolic", tooltip_text=self.t("panel"))
        self.panel_btn.connect("toggled", self.on_panel)
        bar.pack_end(self.panel_btn)

        self.go_btn = Gtk.Button(label=self.t("download"))
        self.go_btn.add_css_class("suggested-action")
        self.go_btn.connect("clicked", lambda *_: self.js("download"))
        bar.pack_end(self.go_btn)
        self._build_transfer(bar)

        self._actions()
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.download", ["<Control>Return"])
        self.set_accels_for_action("app.prefs", ["<Control>comma"])
        self.set_accels_for_action("app.pdf", ["<Control>p"])
        self.set_accels_for_action("app.shortcuts", ["<Control>question"])

        tv = Adw.ToolbarView()
        tv.add_top_bar(bar)
        self.toolbar = self._build_toolbar()
        tv.add_top_bar(self.toolbar)
        self.toasts = Adw.ToastOverlay()
        self.toasts.set_child(view)
        tv.set_content(self.toasts)
        win.set_content(tv)
        # lo schermo intero della foto (tasto F) nasconde anche la barra della finestra
        view.connect("enter-fullscreen", lambda *_: (tv.set_reveal_top_bars(False), win.fullscreen(), False)[-1])
        view.connect("leave-fullscreen", lambda *_: (tv.set_reveal_top_bars(True), win.unfullscreen(), False)[-1])
        self.apply_state({})
        view.load_uri(url)
        win.present()
        GLib.timeout_add_seconds(2, self._offer_menu_entry)
        GLib.timeout_add_seconds(6, self._auto_update)

    def _main_menu(self):
        main_menu = Gio.Menu()
        theme = Gio.Menu()
        theme.append(self.t("system"), "app.theme::system")
        theme.append(self.t("light"), "app.theme::light")
        theme.append(self.t("dark"), "app.theme::dark")
        main_menu.append_section(None, theme)
        links = Gio.Menu()
        links.append(self.t("site"), "app.site")
        links.append(self.t("issues"), "app.issues")
        main_menu.append_section(None, links)
        last = Gio.Menu()
        last.append(self.t("prefs"), "app.prefs")
        if appimage_path():
            last.append(self.t("upd_check"), "app.update")
        last.append(self.t("keys"), "app.shortcuts")
        last.append(self.t("about"), "app.about")
        last.append(self.t("quit"), "app.quit")
        main_menu.append_section(None, last)
        return main_menu

    def _relabel(self):
        """La lingua e' cambiata: rifaccio le etichette della finestra."""
        self.menu_btn.set_menu_model(self._main_menu())
        self.menu_btn.set_tooltip_text(self.t("menu"))
        self.panel_btn.set_tooltip_text(self.t("panel"))
        cm = Gio.Menu()
        cm.append(self.t("change"), "app.change")
        self.cam_btn.set_menu_model(cm)
        self.cam_btn.set_tooltip_text(self.t("camera"))
        for key, btn in getattr(self, "fbtn", {}).items():
            if key in ("both", "VIDEO"):
                btn.set_label(self.t("all") if key == "both" else self.t("video"))

    # ------------------------------------------------------------ azioni della finestra
    def _actions(self):
        def add(name, cb, param=None, state=None):
            a = Gio.SimpleAction.new_stateful(name, param, state) if state is not None else Gio.SimpleAction.new(name, param)
            a.connect("activate", cb)
            self.add_action(a)
            return a
        add("change", lambda *_: self.js("change"))
        add("download", lambda *_: self.js("download"))
        add("quit", lambda *_: self.quit())
        add("about", lambda *_: self.about())
        add("prefs", lambda *_: self.prefs())
        add("update", lambda *_: self.check_updates(True))
        add("pdf", lambda *_: self.js("pdf"))
        add("pdfread", lambda *_: self.read_pdf())
        add("shortcuts", lambda *_: self.shortcuts())
        add("site", lambda *_: Gtk.UriLauncher.new("https://github.com/cisla66/Provino").launch(self.win, None, None, None))
        add("issues", lambda *_: Gtk.UriLauncher.new("https://github.com/cisla66/Provino/issues").launch(self.win, None, None, None))
        saved = "system"
        try:
            saved = (self.core[0].settings.get("theme") or "system")
        except Exception:  # noqa: BLE001
            pass
        self.theme_action = add("theme", self.on_theme, GLib.VariantType.new("s"), GLib.Variant("s", saved))
        self._set_theme(saved)

    def on_theme(self, action, value):
        action.set_state(value)
        self._set_theme(value.get_string())
        try:
            self.core[0].settings["theme"] = value.get_string()
            self.core[0].save_settings()
        except Exception:  # noqa: BLE001
            pass

    def _set_theme(self, name):
        sm = Adw.StyleManager.get_default()
        sm.set_color_scheme({"light": Adw.ColorScheme.FORCE_LIGHT, "dark": Adw.ColorScheme.FORCE_DARK}
                            .get(name, Adw.ColorScheme.DEFAULT))
        self.js("theme", "" if name == "system" else name)

    def on_panel(self, btn):
        if bool(self.state.get("split")) != btn.get_active():
            self.js("split")

    def js(self, cmd, arg=None):
        view = getattr(self, "view", None)
        if view is None:
            return
        code = "window.provinoNative && window.provinoNative(%s, %s)" % (json.dumps(cmd), json.dumps(arg))
        try:
            view.evaluate_javascript(code, -1, None, None, None, None, None)
        except TypeError:
            view.evaluate_javascript(code, -1, None, None, None, None)

    def on_page_state(self, ucm, value):
        try:
            st = json.loads(value.to_string())
        except Exception:  # noqa: BLE001
            return
        kind = st.get("type", "state")
        if kind == "askDest":
            self.ask_dest(st)
        elif kind == "conflicts":
            self.ask_conflicts(st)
        elif kind == "toast":
            self.toasts.add_toast(Adw.Toast(title=st.get("text") or "", timeout=6))
        elif kind == "pdfAsk":
            self.ask_pdf(st)
        elif kind == "pdfDone":
            t = Adw.Toast(title=st.get("title") or "", timeout=8)
            t.set_button_label(st.get("open") or "")
            path = st.get("path") or ""
            t.connect("button-clicked", lambda *_: Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self.win, None, None))
            self.toasts.add_toast(t)
        elif kind == "transfer":
            self.on_transfer(st)
        elif kind == "error":
            self.toast(st.get("text") or "")
        else:
            self.apply_state(st)

    # ------------------------------------------------------------ barra sotto la testata (Mostra, Pellicole, Da scaricare)
    def _build_toolbar(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(12); box.set_margin_end(12); box.set_margin_top(6); box.set_margin_bottom(6)
        seg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        seg.add_css_class("linked")
        self.fbtn = {}
        first = None
        for key, label in (("both", self.t("all")), ("JPG", "JPG"), ("RAF", "RAF"), ("HIF", "HEIF"), ("VIDEO", self.t("video"))):
            b = Gtk.ToggleButton(label=label)
            if first is None:
                first = b
            else:
                b.set_group(first)
            b.connect("toggled", self.on_filter, key)
            seg.append(b)
            self.fbtn[key] = b
        box.append(seg)
        self.film_model = Gtk.StringList()
        self.film_values = [""]
        self.film_model.append(self.t("films_all"))
        self.film_dd = Gtk.DropDown(model=self.film_model)
        self.film_dd.connect("notify::selected", self.on_film)
        box.append(self.film_dd)
        spacer = Gtk.Box(); spacer.set_hexpand(True); box.append(spacer)
        self.sum_lbl = Gtk.Label(label="")
        self.sum_lbl.add_css_class("dim-label")
        self.sum_lbl.add_css_class("numeric")
        box.append(self.sum_lbl)
        self.pick_menu = Gio.Menu()
        self.pick_btn = Gtk.MenuButton(label=self.t("pick"), menu_model=self.pick_menu, always_show_arrow=True)
        box.append(self.pick_btn)
        for name in ("JPG", "RAF", "both", "HIF", "VIDEO", "fresh", "visible", "none"):
            a = Gio.SimpleAction.new("sel-" + name, None)
            a.connect("activate", lambda _a, _p, n=name: self.js("select", n))
            self.add_action(a)
        self._updating = False
        bar = Adw.Bin()
        bar.set_child(box)
        bar.set_visible(False)
        return bar

    def on_filter(self, btn, key):
        if btn.get_active() and not self._updating and self.state.get("filter") != key:
            self.js("filter", key)

    def on_film(self, dd, _pspec):
        if self._updating:
            return
        i = dd.get_selected()
        if 0 <= i < len(self.film_values) and self.film_values[i] != self.state.get("film", ""):
            self.js("film", self.film_values[i])

    def _update_toolbar(self, st):
        ready = bool(st.get("ready"))
        self.toolbar.set_visible(ready)
        if not ready:
            return
        self._updating = True
        try:
            c = st.get("counts") or {}
            self.fbtn["VIDEO"].set_visible(bool(c.get("VIDEO")))
            self.fbtn["HIF"].set_visible(bool(c.get("HIF")))
            f = st.get("filter") or "both"
            if f in self.fbtn and not self.fbtn[f].get_active():
                self.fbtn[f].set_active(True)
            films = st.get("films") or []
            vals = [v for v, _l in films] or [""]
            labels = [l for _v, l in films] or [self.t("films_all")]
            # anche le etichette: cambiando lingua "Tutte le pellicole" diventa "All film simulations"
            if vals != self.film_values or labels != getattr(self, "film_labels", None):
                self.film_values = vals
                self.film_labels = labels
                cur_sel = self.film_dd.get_selected()
                self.film_model.splice(0, self.film_model.get_n_items(), labels)
                self.film_dd.set_selected(cur_sel)
            self.film_dd.set_visible(len(films) > 1)
            cur = st.get("film") or ""
            if cur in self.film_values and self.film_dd.get_selected() != self.film_values.index(cur):
                self.film_dd.set_selected(self.film_values.index(cur))
            n = int(st.get("picked") or 0)
            self.sum_lbl.set_label((st.get("sum") or "") if n else self.t("pick_none"))
            m = self.pick_menu
            m.remove_all()
            sec = Gio.Menu()
            for key, label in (("JPG", "sel_jpg"), ("RAF", "sel_raf"), ("both", "sel_both"), ("HIF", "sel_heif"), ("VIDEO", "sel_video")):
                if c.get(key):
                    sec.append("%s  (%d)" % (self.t(label), c[key]), "app.sel-" + key)
            m.append_section(self.t("by_type"), sec)
            sec2 = Gio.Menu()
            sec2.append("%s  (%d)" % (self.t("sel_fresh"), c.get("fresh", 0)), "app.sel-fresh")
            sec2.append(self.t("sel_visible"), "app.sel-visible")
            m.append_section(None, sec2)
            sec3 = Gio.Menu()
            sec3.append(self.t("sel_none"), "app.sel-none")
            m.append_section(None, sec3)
            sec4 = Gio.Menu()
            sec4.append(self.t("pdf_sel") if n else self.t("pdf_vis"), "app.pdf")
            sec4.append(self.t("pdf_read"), "app.pdfread")
            m.append_section(None, sec4)
            self.pick_btn.set_label(self.t("pick"))   # il numero e' gia' sul pulsante Scarica
        finally:
            self._updating = False

    # ------------------------------------------------------------ PDF: titolo e dove salvarlo
    def ask_pdf(self, req):
        L = req.get("labels") or {}
        dlg = Adw.AlertDialog(heading=L.get("head") or "", body=L.get("body") or "")
        ent = Adw.EntryRow(title=L.get("title") or "")
        ent.set_text(req.get("title") or "")
        box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        box.add_css_class("boxed-list")
        box.append(ent)
        dlg.set_extra_child(box)
        dlg.add_response("cancel", L.get("cancel") or self.t("cancel"))
        dlg.add_response("ok", L.get("ok") or "PDF")
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("ok")
        dlg.set_close_response("cancel")
        ent.connect("entry-activated", lambda *_: dlg.response("ok") if hasattr(dlg, "response") else None)

        def done(_d, resp):
            if resp != "ok":
                return
            title = ent.get_text().strip() or req.get("title") or "Provino"
            safe = "".join("-" if ch in '\\/:*?"<>|' else ch for ch in title).strip(" .") or "Provino"
            fd = Gtk.FileDialog(title=L.get("ok") or "PDF", initial_name=safe + ".pdf", modal=True)
            try:
                fd.set_initial_folder(Gio.File.new_for_path(self.core[0].dest))
            except Exception:  # noqa: BLE001
                pass

            def saved(d, res):
                try:
                    f = d.save_finish(res)
                except GLib.Error:
                    return
                if f and f.get_path():
                    self.js("pdfGo", {"title": title, "path": f.get_path()})
            fd.save(self.win, None, saved)
        dlg.connect("response", done)
        self.pdf_dlg = dlg
        dlg.present(self.win)

    def read_pdf(self):
        fd = Gtk.FileDialog(title=self.t("pdf_read"), modal=True)
        flt = Gtk.FileFilter()
        flt.set_name("PDF")
        flt.add_suffix("pdf")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        fd.set_filters(store)

        def opened(d, res):
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            if f and f.get_path():
                self.js("pdfRead", f.get_path())
        fd.open(self.win, None, opened)

    # ------------------------------------------------------------ finestra Scarica (nativa)
    def ask_dest(self, req):
        dest = {"path": req.get("dest") or "", "by_date": bool(req.get("by_date")), "split": bool(req.get("split_type"))}
        dlg = Adw.Dialog(title=self.t("dl_title").replace("{n}", str(req.get("n"))), content_width=520)
        tb = Adw.ToolbarView()
        hb = Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False)
        cancel = Gtk.Button(label=self.t("cancel"))
        cancel.connect("clicked", lambda *_: dlg.close())
        hb.pack_start(cancel)
        go = Gtk.Button(label=self.t("download"))
        go.add_css_class("suggested-action")
        hb.pack_end(go)
        tb.add_top_bar(hb)
        page = Adw.PreferencesPage()
        kinds = req.get("kinds") or {}
        summary = ", ".join("%d %s" % (v, k) for k, v in kinds.items()) + " · " + (req.get("size") or "")
        grp = Adw.PreferencesGroup(description=summary)
        row = Adw.ActionRow(title=self.t("folder"), subtitle=self._nice(dest["path"]))
        row.set_subtitle_selectable(True)
        pick = Gtk.Button(label=self.t("choose"), valign=Gtk.Align.CENTER)
        row.add_suffix(pick)
        grp.add(row)
        days = req.get("days") or []
        sw_date = Adw.SwitchRow(title=self.t("by_date"))
        sw_date.set_active(dest["by_date"])
        if len(days) == 1:
            d = days[0]
            sw_date.set_subtitle(self.t("by_date_one").replace("{d}", "%s-%s-%s" % (d[:4], d[4:6], d[6:8])))
        elif len(days) > 1:
            sw_date.set_subtitle(self.t("by_date_n").replace("{n}", str(len(days))))
        grp.add(sw_date)
        ks = [k for k in ("RAF", "JPG", "HEIF", "VIDEO") if k in kinds]
        sw_split = Adw.SwitchRow(title=self.t("split"),
                                 subtitle=self.t("split_sub").replace("{k}", (" " + self.t("and") + " ").join([", ".join(ks[:-1]), ks[-1]] if len(ks) > 1 else ks)))
        sw_split.set_active(dest["split"])
        grp.add(sw_split)
        page.add(grp)
        g2 = Adw.PreferencesGroup(title=self.t("where"), description=self.t("new_dirs"))
        prev = Gtk.Label(xalign=0, wrap=True, selectable=True)
        prev.add_css_class("monospace")
        prev.set_margin_top(4)
        g2.add(prev)
        page.add(g2)
        tb.set_content(page)
        dlg.set_child(tb)

        def preview(*_):
            base = self._nice(dest["path"])
            seen, lines = set(), []
            for name, day, k in (req.get("files") or []):
                parts = []
                if sw_date.get_active() and len(day) == 8:
                    parts.append("%s-%s-%s" % (day[:4], day[4:6], day[6:8]))
                if sw_split.get_active():
                    parts.append(k)
                key = "/".join(parts)
                if key in seen:
                    continue
                seen.add(key)
                sub = "/".join("<b>%s</b>" % GLib.markup_escape_text(p) for p in parts)
                lines.append("%s%s%s" % (GLib.markup_escape_text(base), "/" + sub if sub else "", "/" + GLib.markup_escape_text(name)))
                if len(lines) >= 6:
                    break
            prev.set_markup("\n".join(lines))
            row.set_subtitle(self._nice(dest["path"]))
        sw_date.connect("notify::active", preview)
        sw_split.connect("notify::active", preview)
        preview()

        def chosen(fd, res):
            try:
                f = fd.select_folder_finish(res)
            except GLib.Error:
                return
            if f and f.get_path():
                dest["path"] = f.get_path()
                preview()

        def pick_folder(*_):
            fd = Gtk.FileDialog(title=self.t("choose_title"), modal=True)
            try:
                fd.set_initial_folder(Gio.File.new_for_path(dest["path"]))
            except Exception:  # noqa: BLE001
                pass
            fd.select_folder(self.win, None, chosen)
        pick.connect("clicked", pick_folder)

        def confirm(*_):
            dlg.close()
            self.js("destConfirmed", {"dest": dest["path"], "by_date": sw_date.get_active(),
                                      "split_type": sw_split.get_active(), "hs": req.get("hs") or []})
        go.connect("clicked", confirm)
        self.dest_confirm = confirm
        dlg.set_default_widget(go)
        dlg.present(self.win)
        self.dest_dialog = dlg

    # ------------------------------------------------------------ finestra "File gia' nella cartella" (nativa)
    def ask_conflicts(self, req):
        L = req.get("labels") or {}
        dlg = Adw.Dialog(title=req.get("title") or "", content_width=580, content_height=520)
        tb = Adw.ToolbarView()
        hb = Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False)
        cancel = Gtk.Button(label=L.get("cancel") or self.t("cancel"))
        cancel.connect("clicked", lambda *_: dlg.close())
        hb.pack_start(cancel)
        ok = Gtk.Button(label=L.get("ok") or self.t("download"))
        ok.add_css_class("suggested-action")
        hb.pack_end(ok)
        tb.add_top_bar(hb)
        page = Adw.PreferencesPage()
        grp = Adw.PreferencesGroup(description=req.get("sub") or "")
        choices = {}
        radios = {}
        items = req.get("items") or []
        others = int(req.get("others") or 0)

        def ok_label(*_):
            nothing = others == 0 and all(c["act"] == "skip" for c in choices.values())
            ok.set_label((L.get("nothing") if nothing else L.get("ok")) or self.t("download"))
        n_same = sum(1 for it in items if it.get("same"))
        if n_same > 1:
            g0 = Adw.PreferencesGroup(description=req.get("sub") or "")
            grp.set_description(None)
            brow = Adw.ActionRow(title=L.get("sameAll") or "")
            bulk = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
            brow.add_suffix(bulk)
            g0.add(brow)
            page.add(g0)
            for act, key in (("skip", "skipAll"), ("overwrite", "overAll")):
                b = Gtk.Button(label=L.get(key) or act)
                b.connect("clicked", lambda _b, a=act: [radios[(it["h"], a)].set_active(True)
                                                        for it in items if it.get("same")])
                bulk.append(b)
        for it in items:
            exp = Adw.ExpanderRow(title=it.get("name") or "", subtitle=it.get("why") or "")
            exp.set_subtitle_lines(3)
            exp.set_expanded(True)
            tag = Gtk.Label(label="✓" if it.get("same") else "≠")
            tag.add_css_class("success" if it.get("same") else "warning")
            exp.add_prefix(tag)
            opts = [("skip", L.get("skip"))]
            opts.insert(0 if not it.get("same") else 1, ("rename" if not it.get("same") else "overwrite",
                                                         L.get("saveAs") if not it.get("same") else L.get("over")))
            first = None
            state = {"act": "skip" if it.get("same") else "rename", "name": it.get("proposed") or ""}
            choices[it["h"]] = state
            for act, label in opts:
                r = Adw.ActionRow(title=label or act)
                rb = Gtk.CheckButton()
                if first is None:
                    first = rb
                else:
                    rb.set_group(first)
                rb.set_active(act == state["act"])
                rb.connect("toggled", lambda b, a=act, st=state: b.get_active() and (st.__setitem__("act", a), ok_label()))
                radios[(it["h"], act)] = rb
                r.add_prefix(rb)
                r.set_activatable_widget(rb)
                if act == "rename":
                    ent = Gtk.Entry(text=state["name"], valign=Gtk.Align.CENTER, width_chars=18)
                    ent.connect("changed", lambda e, st=state: st.__setitem__("name", e.get_text()))
                    ent.connect("notify::has-focus", lambda e, _p, b=rb: e.has_focus() and b.set_active(True))
                    r.add_suffix(ent)
                exp.add_row(r)
            grp.add(exp)
        page.add(grp)
        tb.set_content(page)
        dlg.set_child(tb)

        def done(*_):
            options = {}
            for h, st in choices.items():
                options[str(h)] = {"action": st["act"], "name": st["name"] if st["act"] == "rename" else None}
            dlg.close()
            self.js("conflictsDone", {"hs": req.get("hs") or [], "options": options})
        ok.connect("clicked", done)
        ok_label()
        self.conflicts_done = done
        dlg.set_default_widget(ok)
        dlg.present(self.win)

    # ------------------------------------------------------------ avanzamento del download (anello nella testata)
    def _build_transfer(self, bar):
        self.tr = {"mode": "none", "pct": 0, "n": -1}
        ring = Ring(self)
        self.tr_ring = ring
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=8, margin_bottom=8,
                      margin_start=8, margin_end=8, width_request=300)
        self.tr_name = Gtk.Label(xalign=0, ellipsize=3)
        self.tr_name.add_css_class("heading")
        self.tr_info = Gtk.Label(xalign=0, wrap=True, max_width_chars=40)
        self.tr_info.add_css_class("dim-label")
        self.tr_info.add_css_class("caption")
        self.tr_bar = Gtk.ProgressBar(margin_top=4)
        self.tr_action = Gtk.Button(halign=Gtk.Align.END, margin_top=6)
        self.tr_action.add_css_class("pill")
        self.tr_action.connect("clicked", self._tr_clicked)
        for w in (self.tr_name, self.tr_info, self.tr_bar, self.tr_action):
            box.append(w)
        pop.set_child(box)
        pop.connect("closed", self._tr_closed)
        self.tr_btn = Gtk.MenuButton(child=ring, popover=pop, visible=False, tooltip_text=self.t("transfers"))
        self.tr_btn.add_css_class("flat")
        bar.pack_end(self.tr_btn)

    def _rgba(self, spec):
        c = Gdk.RGBA()
        c.parse(spec)
        return c

    def _ring_colors(self):
        dark = Adw.StyleManager.get_default().get_dark()
        mode = self.tr["mode"]
        if mode == "ok":
            return self._rgba("#8ff0a4" if dark else "#26a269")
        if mode == "warn":
            return self._rgba("#ffc252" if dark else "#c64600")
        try:
            return Adw.StyleManager.get_default().get_accent_color_rgba()
        except AttributeError:
            return self._rgba("#78aeed" if dark else "#3584e4")

    def on_transfer(self, st):
        mode = st.get("mode") or "none"
        prev, prev_n = self.tr.get("mode"), self.tr.get("n")
        self.tr.update(st)
        self.tr["pct"] = st.get("pct") or 0
        if mode == "none":
            self.tr_btn.set_visible(False)
            return
        self.tr_btn.set_visible(True)
        self.tr_name.set_label(st.get("name") or "")
        self.tr_info.set_label(st.get("info") or "")
        self.tr_info.set_visible(bool(st.get("info")))
        self.tr_bar.set_visible(mode == "run")
        self.tr_bar.set_fraction(self.tr["pct"] / 100.0)
        self.tr_action.set_label(st.get("cancel") if mode == "run" else st.get("open") or "")
        self.tr_action.set_visible(mode == "run" or bool(st.get("open")))
        self.tr_btn.set_tooltip_text(st.get("name") or self.t("transfers"))
        self.tr_ring.queue_draw()
        if mode in ("ok", "warn") and (prev != mode or prev_n != st.get("n")):
            t = Adw.Toast(title=st.get("name") or "", timeout=6)
            if mode == "ok" and st.get("open"):
                t.set_button_label(st.get("open"))
                t.connect("button-clicked", lambda *_: self.js("openFolder"))
            self.toasts.add_toast(t)

    def _tr_clicked(self, *_):
        if self.tr.get("mode") == "run":
            self.js("cancelDownload")
        else:
            self.js("openFolder")
            self.tr_btn.popdown()

    def _tr_closed(self, *_):
        if self.tr.get("mode") in ("ok", "warn"):
            self.js("trayClosed")

    def _offer_menu_entry(self):
        """Avviato da AppImage. Se e' ancora in Scaricati (o altrove), propone una volta di spostarlo in
        ~/Applicazioni e di aggiungerlo alle applicazioni; se la voce c'e' gia', la aggiorna (percorso e icona)."""
        img = appimage_path()
        if not img:
            return False
        cur = menu_entry_path()
        if cur and os.path.isfile(cur) and not os.path.samefile(cur, img):
            self._offer_update(img, cur)          # nuova versione aperta, quella installata c'e' ancora
            return False
        if cur:
            install_menu_entry()   # aggiorna percorso e icona (una nuova versione puo' avere un'icona nuova)
            return False
        S = self.core[0].settings
        if S.get("menu_entry_asked"):
            return False
        S["menu_entry_asked"] = True
        self.core[0].save_settings()
        move = not in_apps_dir(img)
        dlg = Adw.AlertDialog(heading=self.t("inst_h"),
                              body=self.t("inst_b_move" if move else "inst_b") % {"dir": self._nice(apps_dir())})
        dlg.add_response("no", self.t("inst_no"))
        dlg.add_response("yes", self.t("inst_yes_move" if move else "menu_add"))
        dlg.set_response_appearance("yes", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("yes")
        dlg.set_close_response("no")

        def done(_d, resp):
            if resp != "yes":
                return
            try:
                path = move_to_apps(img) if move else img
                ok = install_menu_entry(path)
            except OSError as e:
                self.log.info("Installazione nelle applicazioni non riuscita: %s" % e)
                ok = False
            self.toasts.add_toast(Adw.Toast(title=self.t("menu_done" if ok else "menu_fail"), timeout=5))
        dlg.connect("response", done)
        dlg.present(self.win)
        self.inst_dlg = dlg
        return False

    def _offer_update(self, img, old):
        """Si apre una versione nuova mentre quella installata e' ancora in ~/Applicazioni: propone di sostituirla."""
        dlg = Adw.AlertDialog(heading=self.t("upd_h"),
                              body=self.t("upd_b") % {"old": os.path.basename(old), "dir": self._nice(os.path.dirname(old))})
        dlg.add_response("no", self.t("inst_no"))
        dlg.add_response("yes", self.t("upd_yes"))
        dlg.set_response_appearance("yes", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("yes")
        dlg.set_close_response("no")

        def done(_d, resp):
            if resp != "yes":
                return
            ok = False
            try:
                d = os.path.dirname(old)
                dest = os.path.join(d, os.path.basename(img))
                if os.path.realpath(os.path.dirname(img)) != os.path.realpath(d):
                    if os.path.exists(dest) and not os.path.samefile(dest, img):
                        os.remove(dest)
                    shutil.move(img, dest)
                    os.chmod(dest, 0o755)
                    _MOVED[0] = dest
                if os.path.exists(old) and not os.path.samefile(old, dest):
                    Gio.File.new_for_path(old).trash(None)     # la versione vecchia nel Cestino
                ok = install_menu_entry(dest)
            except (OSError, GLib.Error) as e:
                self.log.info("Aggiornamento non riuscito: %s" % e)
            self.toasts.add_toast(Adw.Toast(title=self.t("upd_done" if ok else "menu_fail"), timeout=5))
        dlg.connect("response", done)
        dlg.present(self.win)
        self.inst_dlg = dlg

    # ------------------------------------------------------------ aggiornamenti (solo AppImage: Flathub aggiorna da se')
    def _auto_update(self):
        S = self.core[0].settings
        if not appimage_path() or S.get("auto_update") is False:
            return False
        if time.time() - float(S.get("last_update_check") or 0) > 20 * 3600:
            self.check_updates(False)
        return False

    def check_updates(self, manual):
        def work():
            r = pv.check_update("linux")
            GLib.idle_add(lambda: (self._update_result(r, manual), False)[1])
        threading.Thread(target=work, daemon=True).start()

    def _update_result(self, r, manual):
        S = self.core[0].settings
        S["last_update_check"] = time.time()
        self.core[0].save_settings()
        if not r.get("ok"):
            if manual:
                self.toasts.add_toast(Adw.Toast(title=self.t("upd_err"), timeout=5))
            return
        latest = r.get("latest") or ""
        if not r.get("newer"):
            if manual:
                self.toasts.add_toast(Adw.Toast(title=self.t("upd_none") % {"c": r.get("current")}, timeout=5))
            return
        if not manual and S.get("skip_version") == latest:
            return
        body = self.t("upd_info") % {"c": r.get("current")}
        if r.get("notes"):
            body += "\n\n" + r["notes"]
        dlg = Adw.AlertDialog(heading=self.t("upd_new") % {"v": latest}, body=body)
        dlg.add_response("later", self.t("upd_later"))
        dlg.add_response("get", self.t("upd_get"))
        dlg.set_response_appearance("get", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("get")
        dlg.set_close_response("later")

        def done(_d, resp):
            if resp == "get":
                Gtk.UriLauncher.new(r.get("download") or r.get("url")).launch(self.win, None, None)
            elif not manual:
                S["skip_version"] = latest
                self.core[0].save_settings()
        dlg.connect("response", done)
        dlg.present(self.win)

    def uninstall(self, *_):
        dlg = Adw.AlertDialog(heading=self.t("un_h"), body=self.t("un_b") % {"photos": self._nice(self.core[0].dest)})
        dlg.add_response("no", self.t("cancel"))
        dlg.add_response("yes", self.t("un_yes"))
        dlg.set_response_appearance("yes", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_close_response("no")

        def done(_d, resp):
            if resp != "yes":
                return
            remove_menu_entry()
            img = appimage_path()
            if img:
                try:
                    Gio.File.new_for_path(img).trash(None)
                except GLib.Error as e:
                    self.log.info("Cestino non riuscito: %s" % e.message)
            self.uninstalling = True      # impostazioni e registro si tolgono dopo la chiusura
            self.quit()
        dlg.connect("response", done)
        self.un_dlg = dlg
        dlg.present(self.prefs_dlg if getattr(self, "prefs_dlg", None) else self.win)

    def _nice(self, path):
        home = os.path.expanduser("~")
        return "~" + path[len(home):] if path.startswith(home) else path

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=4))

    def apply_state(self, st):
        self.state = st
        if hasattr(self, "toolbar"):
            self._update_toolbar(st)
        ready = bool(st.get("ready"))
        self.title.set_title(st.get("title") or "Provino")
        self.title.set_subtitle(st.get("subtitle") or "")
        go = st.get("go") or {}
        self.go_btn.set_label(go.get("label") or self.t("download"))
        self.go_btn.set_tooltip_text(go.get("small") or None)
        self.go_btn.set_sensitive(bool(go.get("enabled")))
        self.go_btn.set_visible(ready)
        self.panel_btn.set_visible(ready)
        if self.panel_btn.get_active() != bool(st.get("split")):
            self.panel_btn.set_active(bool(st.get("split")))
        self.cam_btn.set_sensitive(bool(st.get("canChange")))
        # nella scelta iniziale non c'e' niente da cambiare: il pulsante sparisce
        self.cam_btn.set_visible(bool(st.get("canChange")))
        # prima di entrare: icona + "Cambia fotocamera", cosi' si impara il simbolo; dentro solo l'icona
        self._cam_child(None if ready else self.t("changeShort"))
        lang = st.get("lang")
        if lang in self.TXT and lang != self.lang:
            self.lang = lang
            self._relabel()

    def _cam_child(self, label):
        if label == self._cam_label:
            return
        self._cam_label = label
        box = Gtk.Box(spacing=6)
        box.append(Gtk.Image(icon_name="provino-camera-switch-symbolic", pixel_size=22))
        if label:
            box.append(Gtk.Label(label=label))
            self.cam_btn.remove_css_class("image-button")
        else:
            self.cam_btn.add_css_class("image-button")
        self.cam_btn.set_child(box)

    # ------------------------------------------------------------ Preferenze
    def prefs(self):
        app = self.core[0]
        S = app.settings
        try:
            dlg = Adw.PreferencesDialog(title=self.t("prefs"))
        except AttributeError:   # libadwaita < 1.5
            dlg = Adw.PreferencesWindow(transient_for=self.win, modal=True, title=self.t("prefs"))
        page = Adw.PreferencesPage(title=self.t("prefs"), icon_name="preferences-system-symbolic")
        g1 = Adw.PreferencesGroup(title=self.t("p_dl"), description=self.t("p_dl_sub"))
        folder = Adw.ActionRow(title=self.t("folder"), subtitle=self._nice(app.dest))
        folder.add_css_class("property")
        ch = Gtk.Button(label=self.t("choose"), valign=Gtk.Align.CENTER)
        folder.add_suffix(ch)
        folder.set_activatable_widget(ch)
        g1.add(folder)

        def save(**kw):
            for k, v in kw.items():
                S[k] = v
            app.save_settings()
            try:
                app.refresh_on_mac()
            except Exception:  # noqa: BLE001
                pass

        def chosen(fd, res):
            try:
                f = fd.select_folder_finish(res)
            except GLib.Error:
                return
            if f and f.get_path():
                app.dest = f.get_path()
                save(dest=app.dest)
                folder.set_subtitle(self._nice(app.dest))

        def pick(*_):
            fd = Gtk.FileDialog(title=self.t("choose_title"), modal=True)
            try:
                fd.set_initial_folder(Gio.File.new_for_path(app.dest))
            except Exception:  # noqa: BLE001
                pass
            fd.select_folder(self.win, None, chosen)
        ch.connect("clicked", pick)
        for key, title, sub in (("by_date", "by_date", "p_by_date_sub"), ("split_type", "split", "p_split_sub")):
            row = Adw.SwitchRow(title=self.t(title), subtitle=self.t(sub), active=bool(S.get(key)))
            row.connect("notify::active", lambda r, _p, k=key: save(**{k: r.get_active()}))
            g1.add(row)
        page.add(g1)

        g2 = Adw.PreferencesGroup(title=self.t("p_look"))
        langs = [("it", "Italiano"), ("en", "English")]
        lrow = Adw.ComboRow(title=self.t("p_lang"), model=Gtk.StringList.new([n for _c, n in langs]))
        cur = S.get("ui_lang") or self.lang
        lrow.set_selected(next((i for i, (c, _n) in enumerate(langs) if c == cur), 0))
        lrow.connect("notify::selected", lambda r, _p: self.js("lang", langs[r.get_selected()][0]))
        g2.add(lrow)
        themes = ["system", "light", "dark"]
        trow = Adw.ComboRow(title=self.t("p_theme"), model=Gtk.StringList.new([self.t(x) for x in themes]))
        trow.set_selected(themes.index(self.theme_action.get_state().get_string())
                          if self.theme_action.get_state().get_string() in themes else 0)
        trow.connect("notify::selected", lambda r, _p: self.theme_action.activate(GLib.Variant("s", themes[r.get_selected()])))
        g2.add(trow)
        if appimage_path():
            mrow = Adw.SwitchRow(title=self.t("menu_row"), subtitle=self.t("menu_row_sub"), active=bool(menu_entry_path()))
            mrow.connect("notify::active", lambda r, _p: install_menu_entry() if r.get_active() else remove_menu_entry())
            g2.add(mrow)
            urow2 = Adw.SwitchRow(title=self.t("upd_auto"), active=S.get("auto_update") is not False)
            urow2.connect("notify::active", lambda r, _p: save(auto_update=r.get_active()))
            g2.add(urow2)
        page.add(g2)

        if appimage_path():
            gu = Adw.PreferencesGroup()
            urow = Adw.ButtonRow(title=self.t("un_row")) if hasattr(Adw, "ButtonRow") else None
            if urow is not None:
                urow.add_css_class("destructive-action")
                urow.connect("activated", self.uninstall)
            else:
                urow = Adw.ActionRow(title=self.t("un_row"), activatable=True)
                urow.add_css_class("error")
                urow.connect("activated", self.uninstall)
            gu.add(urow)
            self._uninstall_group = gu
        g3 = Adw.PreferencesGroup(title=self.t("p_safe"))
        g3.add(Adw.ActionRow(title=self.t("p_safe_t"), subtitle=self.t("p_safe_s")))
        page.add(g3)
        if getattr(self, "_uninstall_group", None) is not None and appimage_path():
            page.add(self._uninstall_group)
            self._uninstall_group = None
        dlg.add(page)
        self.prefs_dlg = dlg
        try:
            dlg.present(self.win)
        except TypeError:
            dlg.present()

    # ------------------------------------------------------------ Scorciatoie da tastiera
    def shortcuts(self):
        T = self.t
        groups = [
            (T("k_photos"), [("<Control>a", T("k_all")), ("Escape", T("k_none")), ("space", T("k_space")),
                             ("Left Right Up Down", T("k_move"))]),
            (T("k_view"), [("f", T("k_full")), ("Escape", T("k_back"))]),
            (T("k_app"), [("<Control>Return", T("k_dl")), ("<Control>comma", T("prefs")),
                          ("<Control>question", T("keys")), ("<Control>q", T("quit"))]),
        ]
        from xml.sax.saxutils import escape as esc
        xml = ['<interface><object class="GtkShortcutsWindow" id="w"><property name="modal">1</property><property name="title">%s</property>' % esc(T("keys")),
               '<child><object class="GtkShortcutsSection"><property name="section-name">main</property>']
        for title, items in groups:
            xml.append('<child><object class="GtkShortcutsGroup"><property name="title">%s</property>' % esc(title))
            for acc, label in items:
                xml.append('<child><object class="GtkShortcutsShortcut"><property name="accelerator">%s</property>'
                           '<property name="title">%s</property></object></child>' % (esc(acc), esc(label)))
            xml.append('</object></child>')
        xml.append('</object></child></object></interface>')
        b = Gtk.Builder.new_from_string("".join(xml), -1)
        w = b.get_object("w")
        w.set_transient_for(self.win)
        w.set_title(T("keys"))
        self.shortcuts_win = w
        w.present()

    def about(self):
        try:
            dlg = Adw.AboutDialog(application_name="Provino", application_icon=APP_ID,
                                  version=pv.APP_VERSION, developer_name="Marco Cislaghi",
                                  license_type=Gtk.License.MIT_X11, website="https://github.com/cisla66/Provino",
                                  issue_url="https://github.com/cisla66/Provino/issues",
                                  comments=self.t("comments"))
            dlg.present(self.win)
        except (AttributeError, TypeError):   # libadwaita < 1.5
            dlg = Adw.AboutWindow(transient_for=self.win, application_name="Provino", application_icon=APP_ID,
                                  version=pv.APP_VERSION, developer_name="Marco Cislaghi",
                                  license_type=Gtk.License.MIT_X11, website="https://github.com/cisla66/Provino")
            dlg.present()

    def on_policy(self, view, decision, kind):
        if kind != WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        uri = decision.get_navigation_action().get_request().get_uri() or ""
        if uri.startswith("http://127.0.0.1:") or uri.startswith("about:"):
            return False
        decision.ignore()
        Gtk.UriLauncher.new(uri).launch(None, None, None, None)
        return True

    def on_shutdown(self, *_):
        if not self.core:
            return
        app, srv, url, log = self.core
        log.info("Finestra chiusa: chiudo il collegamento con la fotocamera.")
        try:
            app.shutdown()
            srv.shutdown()
        finally:
            log.info("Chiuso.")
            log.close()
            if getattr(self, "uninstalling", False):
                shutil.rmtree(pv.DATA, ignore_errors=True)   # impostazioni e registri; le foto restano dove sono


def main():
    ap = argparse.ArgumentParser(description="Provino in una finestra GNOME")
    ap.add_argument("--dest", default=pv.default_dest())
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    a = ProvinoApp(args)
    # Ctrl+C nel terminale chiude la finestra in modo pulito (saluta la fotocamera)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: (a.quit(), True)[1])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (a.quit(), True)[1])
    sys.exit(a.run([sys.argv[0]]))


if __name__ == "__main__":
    main()
