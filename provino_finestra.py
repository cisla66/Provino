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
import signal
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Adw, Gio, GLib, Gtk, WebKit
except (ImportError, ValueError) as e:
    print("Mancano i componenti GNOME per la finestra (%s)." % e)
    print("Su Fedora: sudo dnf install webkitgtk6.0 libadwaita python3-gobject")
    print("Intanto puoi usare Provino nel browser: python3 provino.py")
    sys.exit(1)

import json  # noqa: E402
import provino as pv  # noqa: E402
import fuji_wifi as fw  # noqa: E402

APP_ID = "io.github.provino.Provino"


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


class ProvinoApp(Adw.Application):
    def __init__(self, args):
        super().__init__(application_id=APP_ID)
        self.args = args
        self.core = None
        self.connect("activate", self.on_activate)
        self.connect("shutdown", self.on_shutdown)

    # testi della cornice (la pagina ha i suoi in i18n.js)
    TXT = {"it": {"download": "Scarica", "change": "Cambia fotocamera…", "camera": "Fotocamera e collegamento",
                  "panel": "Foto grande e informazioni", "menu": "Menu principale",
                  "system": "Segui il sistema", "light": "Chiaro", "dark": "Scuro",
                  "about": "Informazioni su Provino", "quit": "Esci", "site": "Sito e guida",
                  "issues": "Segnala un problema", "comments": "Progetto indipendente, non affiliato a FUJIFILM Corporation.",
                  "all": "Tutto", "video": "Video", "films_all": "Tutte le pellicole", "pick": "Da scaricare",
                  "pick_none": "Nessun file scelto", "sel_jpg": "Tutti i JPG", "sel_raf": "Tutti i RAF",
                  "sel_both": "Tutti i JPG e i RAF", "sel_heif": "Tutti gli HEIF", "sel_video": "Tutti i video",
                  "sel_fresh": "Solo quelli non ancora scaricati", "sel_visible": "Tutto quello che vedi",
                  "sel_none": "Deseleziona tutto", "by_type": "Per tipo, su tutta la scheda",
                  "dl_title": "Scarica {n} file", "folder": "Cartella", "choose": "Cambia…",
                  "by_date": "Una cartella per ogni giorno di scatto", "by_date_one": "Tutte le foto scelte sono del {d}",
                  "by_date_n": "Le foto scelte sono di {n} giorni: {n} cartelle", "split": "Separa per tipo",
                  "split_sub": "Sottocartelle {k}", "where": "Dove finiscono", "cancel": "Annulla",
                  "new_dirs": "In grassetto le cartelle che Provino crea adesso.", "choose_title": "Scegli la cartella",
                  "files": "file", "and": "e"},
           "en": {"download": "Download", "change": "Change camera…", "camera": "Camera and connection",
                  "panel": "Large photo and info", "menu": "Main menu",
                  "system": "Follow system", "light": "Light", "dark": "Dark",
                  "about": "About Provino", "quit": "Quit", "site": "Website and guide",
                  "issues": "Report a problem", "comments": "Independent project, not affiliated with FUJIFILM Corporation.",
                  "all": "All", "video": "Video", "films_all": "All film simulations", "pick": "To download",
                  "pick_none": "No files picked", "sel_jpg": "All JPGs", "sel_raf": "All RAFs",
                  "sel_both": "All JPGs and RAFs", "sel_heif": "All HEIFs", "sel_video": "All videos",
                  "sel_fresh": "Only not downloaded yet", "sel_visible": "Everything you see",
                  "sel_none": "Deselect all", "by_type": "By type, across the card",
                  "dl_title": "Download {n} files", "folder": "Folder", "choose": "Change…",
                  "by_date": "One folder per shooting day", "by_date_one": "All picked photos are from {d}",
                  "by_date_n": "The picked photos span {n} days: {n} folders", "split": "Split by type",
                  "split_sub": "Subfolders {k}", "where": "Where they go", "cancel": "Cancel",
                  "new_dirs": "Folders in bold are created now.", "choose_title": "Choose the folder",
                  "files": "files", "and": "and"}}

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
        self.cam_btn = Gtk.MenuButton(icon_name="camera-photo-symbolic", menu_model=cam_menu,
                                      tooltip_text=self.t("camera"))
        bar.pack_start(self.cam_btn)

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
        last.append(self.t("about"), "app.about")
        last.append(self.t("quit"), "app.quit")
        main_menu.append_section(None, last)
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

        self._actions()
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.download", ["<Control>Return"])

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
            if vals != self.film_values:
                self.film_values = vals
                labels = [l for _v, l in films] or [self.t("films_all")]
                self.film_model.splice(0, self.film_model.get_n_items(), labels)
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
            self.pick_btn.set_label(("%s · %d" % (self.t("pick"), n)) if n else self.t("pick"))
        finally:
            self._updating = False

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
        lang = st.get("lang")
        if lang in self.TXT:
            self.lang = lang

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
