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
                  "issues": "Segnala un problema", "comments": "Progetto indipendente, non affiliato a FUJIFILM Corporation."},
           "en": {"download": "Download", "change": "Change camera…", "camera": "Camera and connection",
                  "panel": "Large photo and info", "menu": "Main menu",
                  "system": "Follow system", "light": "Light", "dark": "Dark",
                  "about": "About Provino", "quit": "Quit", "site": "Website and guide",
                  "issues": "Report a problem", "comments": "Independent project, not affiliated with FUJIFILM Corporation."}}

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
        tv.set_content(view)
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
        self.apply_state(st)

    def apply_state(self, st):
        self.state = st
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
