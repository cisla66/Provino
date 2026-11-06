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
    from gi.repository import Adw, GLib, Gtk, WebKit
except (ImportError, ValueError) as e:
    print("Mancano i componenti GNOME per la finestra (%s)." % e)
    print("Su Fedora: sudo dnf install webkitgtk6.0 libadwaita python3-gobject")
    print("Intanto puoi usare Provino nel browser: python3 provino.py")
    sys.exit(1)

import provino as pv  # noqa: E402
import fuji_wifi as fw  # noqa: E402

APP_ID = "io.github.provino.Provino"


def start_core(args):
    """Avvia Provino (server locale, download, controlli) senza browser. Ritorna (app, srv, url, log)."""
    os.makedirs(args.dest, exist_ok=True)
    logdir = os.path.join(HERE, "log")
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

    def on_activate(self, *_):
        if self.get_active_window():
            self.get_active_window().present()   # gia' aperta: la porto davanti, niente seconda copia
            return
        self.core = start_core(self.args)
        app, srv, url, log = self.core

        win = Adw.ApplicationWindow(application=self, title="Provino")
        win.set_default_size(1320, 860)
        view = WebKit.WebView()
        st = view.get_settings()
        st.set_enable_developer_extras(bool(self.args.verbose))
        st.set_javascript_can_access_clipboard(True)   # "Copia ricetta"
        # i link esterni (es. pagina firmware Fujifilm) si aprono nel browser, non nella finestra
        view.connect("decide-policy", self.on_policy)
        bar = Adw.HeaderBar()
        tv = Adw.ToolbarView()
        tv.add_top_bar(bar)
        tv.set_content(view)
        win.set_content(tv)
        # lo schermo intero della foto (tasto F) nasconde anche la barra della finestra
        view.connect("enter-fullscreen", lambda *_: (tv.set_reveal_top_bars(False), win.fullscreen(), False)[-1])
        view.connect("leave-fullscreen", lambda *_: (tv.set_reveal_top_bars(True), win.unfullscreen(), False)[-1])
        view.load_uri(url)
        win.present()

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
    ap.add_argument("--dest", default=os.path.join(HERE, "scaricate"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    a = ProvinoApp(args)
    # Ctrl+C nel terminale chiude la finestra in modo pulito (saluta la fotocamera)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: (a.quit(), True)[1])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (a.quit(), True)[1])
    sys.exit(a.run([sys.argv[0]]))


if __name__ == "__main__":
    main()
