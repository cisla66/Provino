// Provino per macOS: finestra nativa AppKit (menu, barra degli strumenti, fogli, Impostazioni).
// La griglia dei provini e' la stessa pagina della versione GNOME, dentro una WKWebView;
// il motore (download, fotocamera, scheda) e' provino.py, con il Python incluso nell'app.
// Compilazione: vedi build-app.sh. Licenza MIT.

import AppKit
import WebKit

// MARK: - testi

let TXT: [String: [String: String]] = [
    "it": [
        "download": "Scarica", "change": "Cambia fotocamera…", "changeShort": "Cambia fotocamera", "camera": "Fotocamera e collegamento",
        "panel": "Foto grande e informazioni", "about": "Informazioni su Provino", "quit": "Esci da Provino",
        "hide": "Nascondi Provino", "hideOthers": "Nascondi altri", "showAll": "Mostra tutti",
        "settings": "Impostazioni…", "file": "Archivio", "edit": "Modifica", "view": "Vista", "window": "Finestra",
        "help": "Aiuto", "guide": "Guida di Provino", "issues": "Segnala un problema", "openFolder": "Apri la cartella dei download",
        "copy": "Copia", "cut": "Taglia", "paste": "Incolla", "undo": "Annulla", "selectAll": "Seleziona tutto", "deselect": "Deseleziona tutto", "minimize": "Contrai",
        "zoom": "Ridimensiona", "front": "Porta tutto in primo piano", "fullscreen": "Entra in modalità a tutto schermo",
        "show": "Mostra", "all": "Tutto", "video": "Video", "films_all": "Tutte le pellicole", "pick": "Seleziona",
        "pick_none": "Nessun file scelto", "sel_jpg": "Tutti i JPG", "sel_raf": "Tutti i RAF",
        "sel_both": "Tutti i JPG e i RAF", "sel_heif": "Tutti gli HEIF", "sel_video": "Tutti i video",
        "sel_fresh": "Solo quelli non ancora scaricati", "sel_visible": "Tutto quello che vedi",
        "by_type": "Seleziona per tipo, su tutta la scheda", "films": "Pellicole", "langNote": "Alcune voci dei menu di macOS (Modifica, Vista, Finestra) cambiano lingua al prossimo avvio di Provino.",
        "dl_title": "Scarica {n} file", "folder": "Cartella:", "choose": "Cambia…",
        "event": "Una cartella per l'evento", "event_hint": "Gli spazi diventano _ .", "event_empty": "Scrivi il nome dell'evento.",
        "sel_bydate": "Per data…", "show_all": "Mostra tutti",
        "in_event": "Cartella di un evento: le foto vanno qui dentro.", "nested_warn": "Attenzione: così crei una cartella nuova dentro l'evento «{n}».",
        "by_date": "Una cartella per ogni giorno di scatto", "by_date_one": "Tutte le foto scelte sono del {d}.",
        "by_date_n": "Le foto scelte sono di {n} giorni: {n} cartelle.", "split": "Separa per tipo",
        "split_sub": "Sottocartelle {k}.", "where": "Dove finiscono (in grassetto le cartelle nuove):", "cancel": "Annulla",
        "choose_title": "Scegli la cartella", "and": "e", "transfers": "Download",
        "general": "Generale", "settingsTitle": "Impostazioni", "p_dl_sub": "Valgono come proposta: prima di ogni download puoi cambiarle.",
        "p_lang": "Lingua:", "p_theme": "Aspetto:", "system": "Automatico", "light": "Chiaro", "dark": "Scuro",
        "p_safe": "Provino legge soltanto: non cancella, non modifica e non formatta mai nulla sulla scheda.",
        "comments": "Progetto indipendente, non affiliato a FUJIFILM Corporation.",
        "starting": "Avvio di Provino…", "noPython": "Non trovo il motore di Provino dentro l'app.",
        "crash": "Il motore di Provino si è chiuso. Il registro è nella cartella log.",
        "openLog": "Apri il registro", "checkUpd": "Controlla aggiornamenti…", "pdfSel": "Crea PDF delle foto scelte…", "pdfVis": "Crea PDF di quello che vedi…", "pdfMenu": "Crea PDF…", "pdfRead": "Leggi le scelte da un PDF…", "updNew": "È disponibile Provino {v}",
        "updInfo": "Hai la versione {c}.", "updGet": "Scarica e installa", "updLater": "Più tardi",
        "updDl": "Scarico Provino {v}", "updDlOf": "{a} di {b} MB", "updDlCheck": "Controllo il file…", "updDlPrep": "Preparo la nuova versione…",
        "updDlFail": "Non riesco a installare l'aggiornamento da qui", "updDlFailInfo": "Apro la pagina dei download: puoi installarlo a mano.",
        "updReady": "Provino {v} è pronto", "updReadyInfo": "Provino si chiude e si riapre con la nuova versione. Impostazioni e foto restano come sono.",
        "updRestart": "Installa e riavvia", "updNone": "Provino è aggiornato",
        "updNoneInfo": "Hai la versione più recente ({c}).", "updErr": "Non riesco a controllare gli aggiornamenti",
        "updErrInfo": "Controlla la connessione e riprova più tardi.", "autoUpd": "Controlla gli aggiornamenti all'avvio",
        "panelOn": "Mostra foto grande e informazioni",
    ],
    "en": [
        "download": "Download", "change": "Change Camera…", "changeShort": "Change Camera", "camera": "Camera and connection",
        "panel": "Large photo and info", "about": "About Provino", "quit": "Quit Provino",
        "hide": "Hide Provino", "hideOthers": "Hide Others", "showAll": "Show All",
        "settings": "Settings…", "file": "File", "edit": "Edit", "view": "View", "window": "Window",
        "help": "Help", "guide": "Provino Guide", "issues": "Report a Problem", "openFolder": "Open Downloads Folder",
        "copy": "Copy", "cut": "Cut", "paste": "Paste", "undo": "Undo", "selectAll": "Select All", "deselect": "Deselect All", "minimize": "Minimize",
        "zoom": "Zoom", "front": "Bring All to Front", "fullscreen": "Enter Full Screen",
        "show": "Show", "all": "All", "video": "Video", "films_all": "All film simulations", "pick": "Select",
        "pick_none": "No files picked", "sel_jpg": "All JPGs", "sel_raf": "All RAFs",
        "sel_both": "All JPGs and RAFs", "sel_heif": "All HEIFs", "sel_video": "All videos",
        "sel_fresh": "Only not downloaded yet", "sel_visible": "Everything you see",
        "by_type": "Select by type, across the card", "films": "Film simulations", "langNote": "Some macOS menu items (Edit, View, Window) switch language the next time you open Provino.",
        "dl_title": "Download {n} files", "folder": "Folder:", "choose": "Change…",
        "event": "One folder for the event", "event_hint": "Spaces become _ .", "event_empty": "Type the event name.",
        "sel_bydate": "By date…", "show_all": "Show all",
        "in_event": "This is an event folder: photos go right inside it.", "nested_warn": "Careful: this creates a new folder inside the event “{n}”.",
        "by_date": "One folder per shooting day", "by_date_one": "All picked photos are from {d}.",
        "by_date_n": "The picked photos span {n} days: {n} folders.", "split": "Split by type",
        "split_sub": "Subfolders {k}.", "where": "Where they go (new folders in bold):", "cancel": "Cancel",
        "choose_title": "Choose the folder", "and": "and", "transfers": "Downloads",
        "general": "General", "settingsTitle": "Settings", "p_dl_sub": "These are suggestions: you can change them before each download.",
        "p_lang": "Language:", "p_theme": "Appearance:", "system": "Automatic", "light": "Light", "dark": "Dark",
        "p_safe": "Provino only reads: it never deletes, changes or formats anything on the card.",
        "comments": "Independent project, not affiliated with FUJIFILM Corporation.",
        "starting": "Starting Provino…", "noPython": "Provino's engine is missing from the app.",
        "crash": "Provino's engine has quit. The log is in the log folder.",
        "openLog": "Open the Log", "checkUpd": "Check for Updates…", "pdfSel": "Create PDF of Picked Photos…", "pdfVis": "Create PDF of What You See…", "pdfMenu": "Create PDF…", "pdfRead": "Read Choices from a PDF…", "updNew": "Provino {v} is available",
        "updInfo": "You have version {c}.", "updGet": "Download and Install", "updLater": "Later",
        "updDl": "Downloading Provino {v}", "updDlOf": "{a} of {b} MB", "updDlCheck": "Checking the file…", "updDlPrep": "Preparing the new version…",
        "updDlFail": "Can't install the update from here", "updDlFailInfo": "Opening the downloads page: you can install it by hand.",
        "updReady": "Provino {v} is ready", "updReadyInfo": "Provino will quit and reopen with the new version. Settings and photos stay as they are.",
        "updRestart": "Install and Restart", "updNone": "Provino is up to date",
        "updNoneInfo": "You have the latest version ({c}).", "updErr": "Can't check for updates",
        "updErrInfo": "Check your connection and try again later.", "autoUpd": "Check for updates at launch",
        "panelOn": "Show Large Photo and Info",
    ],
]

var LANG: String = {
    let pref = Locale.preferredLanguages.first ?? "en"
    return pref.hasPrefix("it") ? "it" : "en"
}()

func T(_ k: String) -> String { TXT[LANG]?[k] ?? TXT["en"]?[k] ?? k }
func T(_ k: String, _ subs: [String: String]) -> String {
    var s = T(k)
    for (a, b) in subs { s = s.replacingOccurrences(of: "{\(a)}", with: b) }
    return s
}

func nice(_ path: String) -> String {
    let home = NSHomeDirectory()
    return path.hasPrefix(home) ? "~" + path.dropFirst(home.count) : path
}

func label(_ s: String, size: CGFloat = NSFont.systemFontSize, weight: NSFont.Weight = .regular,
           color: NSColor = .labelColor, wrap: Bool = false) -> NSTextField {
    let l = wrap ? NSTextField(wrappingLabelWithString: s) : NSTextField(labelWithString: s)
    l.font = .systemFont(ofSize: size, weight: weight)
    l.textColor = color
    if wrap { l.preferredMaxLayoutWidth = 460 }
    return l
}

let DATA: URL = {
    if let d = ProcessInfo.processInfo.environment["PROVINO_DATA"] { return URL(fileURLWithPath: d) }
    let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
    return base.appendingPathComponent("Provino")
}()

// MARK: - motore (provino.py)

final class Engine {
    var proc: Process?
    var port: Int = 0
    var onExit: (() -> Void)?
    var quitting = false

    func start(_ done: @escaping (Int?) -> Void) {
        let fm = FileManager.default
        try? fm.createDirectory(at: DATA.appendingPathComponent("log"), withIntermediateDirectories: true)
        let res = Bundle.main.resourceURL!
        #if arch(arm64)
        let arch = "arm64"
        #else
        let arch = "x86_64"
        #endif
        var py = res.appendingPathComponent("python-\(arch)/bin/python3").path
        if !fm.isExecutableFile(atPath: py) { py = "/usr/bin/python3" }   // prove senza Python incluso
        var script = res.appendingPathComponent("app/provino.py").path
        if let dev = ProcessInfo.processInfo.environment["PROVINO_SRC"] { script = dev + "/provino.py" }
        guard fm.fileExists(atPath: script), fm.isExecutableFile(atPath: py) else { done(nil); return }
        let portFile = DATA.appendingPathComponent(".port-\(getpid())")
        try? fm.removeItem(at: portFile)

        let p = Process()
        p.executableURL = URL(fileURLWithPath: py)
        p.arguments = ["-B", script, "--no-browser"]
        var env = ProcessInfo.processInfo.environment
        env["PROVINO_DATA"] = DATA.path
        env["PROVINO_PORT_FILE"] = portFile.path
        env["PROVINO_APP"] = "mac"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        let helper = res.appendingPathComponent("bin/provino-usb").path
        if fm.isExecutableFile(atPath: helper) { env["PROVINO_USB_HELPER"] = helper }
        if env["LANG"] == nil { env["LANG"] = (LANG == "it" ? "it_IT" : "en_US") + ".UTF-8" }
        p.environment = env
        let out = DATA.appendingPathComponent("log/motore.txt")
        fm.createFile(atPath: out.path, contents: nil)
        if let h = try? FileHandle(forWritingTo: out) { p.standardOutput = h; p.standardError = h }
        p.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async { if !(self?.quitting ?? true) { self?.onExit?() } }
        }
        do { try p.run() } catch { done(nil); return }
        proc = p
        // la porta arriva in un file appena il server locale e' pronto
        var tries = 0
        Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { t in
            tries += 1
            if let s = try? String(contentsOf: portFile, encoding: .utf8), let n = Int(s.trimmingCharacters(in: .whitespacesAndNewlines)) {
                t.invalidate()
                try? fm.removeItem(at: portFile)
                self.port = n
                done(n)
            } else if tries > 300 || !(self.proc?.isRunning ?? false) {
                t.invalidate()
                done(nil)
            }
        }
    }

    func stop() {
        quitting = true
        guard let p = proc, p.isRunning else { return }
        p.terminate()   // SIGTERM: provino.py saluta la fotocamera e chiude il registro
        let deadline = Date().addingTimeInterval(4)
        while p.isRunning && Date() < deadline { usleep(50_000) }
        if p.isRunning { kill(p.processIdentifier, SIGKILL) }
    }

    func post(_ path: String, _ body: [String: Any], _ done: (([String: Any]) -> Void)? = nil) {
        guard port > 0, let url = URL(string: "http://127.0.0.1:\(port)\(path)") else { return }
        var r = URLRequest(url: url)
        r.httpMethod = "POST"
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        r.setValue("http://127.0.0.1:\(port)", forHTTPHeaderField: "Origin")
        r.httpBody = try? JSONSerialization.data(withJSONObject: body)
        URLSession.shared.dataTask(with: r) { d, _, _ in
            let o = (d.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]) ?? [:]
            DispatchQueue.main.async { done?(o) }
        }.resume()
    }

    func get(_ path: String, _ done: @escaping ([String: Any]) -> Void) {
        guard port > 0, let url = URL(string: "http://127.0.0.1:\(port)\(path)") else { return }
        URLSession.shared.dataTask(with: url) { d, _, _ in
            let o = (d.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]) ?? [:]
            DispatchQueue.main.async { done(o) }
        }.resume()
    }
}

// MARK: - barra degli strumenti

extension NSToolbarItem.Identifier {
    static let camera = NSToolbarItem.Identifier("camera")
    static let show = NSToolbarItem.Identifier("show")
    static let films = NSToolbarItem.Identifier("films")
    static let pick = NSToolbarItem.Identifier("pick")
    static let transfer = NSToolbarItem.Identifier("transfer")
    static let go = NSToolbarItem.Identifier("go")
    static let panel = NSToolbarItem.Identifier("panel")
}

let FILTERS = ["both", "JPG", "RAF", "HIF", "VIDEO"]

// MARK: - finestra principale

final class MainWindow: NSWindowController, NSToolbarDelegate, WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate, NSWindowDelegate {
    let engine: Engine
    var web: WKWebView!
    var state: [String: Any] = [:]
    var tr: [String: Any] = ["mode": "none"]

    // pezzi della barra
    let showSeg = NSSegmentedControl(labels: ["", "JPG", "RAF", "HEIF", ""], trackingMode: .selectOne, target: nil, action: nil)
    let filmPop = NSPopUpButton(frame: .zero, pullsDown: false)
    var filmLabels: [String] = []
    var filmValues: [String] = []
    let pickItem = NSMenuToolbarItem(itemIdentifier: .pick)
    let camItem = NSMenuToolbarItem(itemIdentifier: .camera)
    var camLabelShown: String? = "?"
    let goBtn = NSButton(title: "", target: nil, action: nil)
    let panelBtn = NSButton(image: NSImage(systemSymbolName: "sidebar.right", accessibilityDescription: nil)!, target: nil, action: nil)
    let ring = RingView()
    let ringBtn = NSButton(title: "", target: nil, action: nil)
    let ringBox = NSView()
    var trPopover: NSPopover?
    let sumLbl = label("", size: 12, color: .secondaryLabelColor)
    var startLbl: NSTextField?

    // fogli
    var destSheet: DestSheet?
    var confSheet: ConflictSheet?

    init(engine: Engine) {
        self.engine = engine
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1240, height: 820),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                         backing: .buffered, defer: false)
        w.title = "Provino"
        w.minSize = NSSize(width: 760, height: 520)
        w.tabbingMode = .disallowed
        w.setFrameAutosaveName("Provino")
        if !w.setFrameUsingName("Provino") { w.center() }
        super.init(window: w)
        w.delegate = self

        let tb = NSToolbar(identifier: "provino")
        tb.delegate = self
        tb.displayMode = .iconOnly
        tb.allowsUserCustomization = false
        w.toolbar = tb
        w.toolbarStyle = .unified
        w.titleVisibility = .visible

        // pagina
        let cfg = WKWebViewConfiguration()
        let ucc = WKUserContentController()
        ucc.add(self, name: "provino")
        ucc.addUserScript(WKUserScript(source: "document.documentElement.classList.add('native','mac');",
                                       injectionTime: .atDocumentStart, forMainFrameOnly: true))
        cfg.userContentController = ucc
        if #available(macOS 12.3, *) { cfg.preferences.isElementFullscreenEnabled = true }
        web = WKWebView(frame: .zero, configuration: cfg)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.setValue(false, forKey: "drawsBackground")
        if #available(macOS 13.3, *) { web.isInspectable = ProcessInfo.processInfo.environment["PROVINO_INSPECT"] != nil }

        let content = NSView()
        web.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(web)
        let start = label(T("starting"), size: 13, color: .secondaryLabelColor)
        start.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(start)
        startLbl = start
        NSLayoutConstraint.activate([
            web.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            web.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            web.topAnchor.constraint(equalTo: content.safeAreaLayoutGuide.topAnchor),
            web.bottomAnchor.constraint(equalTo: content.bottomAnchor),
            start.centerXAnchor.constraint(equalTo: content.centerXAnchor),
            start.centerYAnchor.constraint(equalTo: content.centerYAnchor),
        ])
        w.contentView = content
        web.isHidden = true

        buildBarPieces()
        applyState([:])
    }

    required init?(coder: NSCoder) { fatalError() }

    override func windowDidLoad() { super.windowDidLoad() }

    func load(port: Int) {
        setHidden(.transfer, true)
        web.load(URLRequest(url: URL(string: "http://127.0.0.1:\(port)/")!))
    }

    // MARK: pezzi della barra
    func buildBarPieces() {
        showSeg.target = self
        showSeg.action = #selector(onShow(_:))
        showSeg.segmentStyle = .automatic
        showSeg.selectedSegment = 0
        relabel()

        filmPop.target = self
        filmPop.action = #selector(onFilm(_:))
        filmPop.controlSize = .regular

        goBtn.bezelStyle = .rounded
        goBtn.keyEquivalent = "\r"          // pulsante principale: blu, come in tutte le app del Mac
        goBtn.target = self
        goBtn.action = #selector(onGo)

        panelBtn.bezelStyle = .texturedRounded
        panelBtn.setButtonType(.pushOnPushOff)
        panelBtn.target = self
        panelBtn.action = #selector(onPanel)

        ring.translatesAutoresizingMaskIntoConstraints = false
        ringBtn.isBordered = false
        ringBtn.title = ""
        ringBtn.target = self
        ringBtn.action = #selector(onRing)
        ringBtn.imagePosition = .imageOnly
        ringBtn.translatesAutoresizingMaskIntoConstraints = false
        ringBox.translatesAutoresizingMaskIntoConstraints = false
        ringBox.addSubview(ring)
        ringBox.addSubview(ringBtn)
        NSLayoutConstraint.activate([
            ringBox.widthAnchor.constraint(equalToConstant: 28), ringBox.heightAnchor.constraint(equalToConstant: 28),
            ring.centerXAnchor.constraint(equalTo: ringBox.centerXAnchor), ring.centerYAnchor.constraint(equalTo: ringBox.centerYAnchor),
            ring.widthAnchor.constraint(equalToConstant: 20), ring.heightAnchor.constraint(equalToConstant: 20),
            ringBtn.leadingAnchor.constraint(equalTo: ringBox.leadingAnchor), ringBtn.trailingAnchor.constraint(equalTo: ringBox.trailingAnchor),
            ringBtn.topAnchor.constraint(equalTo: ringBox.topAnchor), ringBtn.bottomAnchor.constraint(equalTo: ringBox.bottomAnchor),
        ])

        camItem.image = cameraSwitchImage()
        camItem.showsIndicator = true
        pickItem.showsIndicator = true
    }

    func relabel() {
        showSeg.setLabel(T("all"), forSegment: 0)
        showSeg.setLabel(T("video"), forSegment: 4)
        for i in 0..<5 { showSeg.setWidth(0, forSegment: i) }
        camItem.label = T("camera")
        camItem.toolTip = T("camera")
        let cm = NSMenu()
        cm.addItem(withTitle: T("change"), action: #selector(AppDelegate.changeCamera(_:)), keyEquivalent: "")
        camItem.menu = cm
        panelBtn.toolTip = T("panel")
        ringBtn.toolTip = T("transfers")
        window?.toolbar?.items.forEach { item in
            if item.itemIdentifier == .show { item.label = T("show") }
            if item.itemIdentifier == .films { item.label = T("films") }
            if item.itemIdentifier == .panel { item.label = T("panel") }
        }
    }

    func toolbarAllowedItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        [.camera, .show, .films, .flexibleSpace, .pick, .transfer, .go, .panel, .space]
    }

    func toolbarDefaultItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        [.camera, .show, .films, .flexibleSpace, .pick, .transfer, .go, .panel]
    }

    func toolbar(_ toolbar: NSToolbar, itemForItemIdentifier id: NSToolbarItem.Identifier, willBeInsertedIntoToolbar flag: Bool) -> NSToolbarItem? {
        switch id {
        case .camera: return camItem
        case .pick: pickItem.label = T("pick"); return pickItem
        default: break
        }
        let item = NSToolbarItem(itemIdentifier: id)
        switch id {
        case .show: item.view = showSeg; item.label = T("show")
        case .films: item.view = filmPop; item.label = T("films")
        case .transfer: item.view = ringBox; item.label = T("transfers")
        case .go: item.view = goBtn; item.label = T("download")
        case .panel: item.view = panelBtn; item.label = T("panel")
        default: return nil
        }
        return item
    }

    func item(_ id: NSToolbarItem.Identifier) -> NSToolbarItem? {
        window?.toolbar?.items.first { $0.itemIdentifier == id }
    }

    /// Nasconde davvero una voce della barra (da macOS 15 anche il suo fondo "vetro").
    func setHidden(_ id: NSToolbarItem.Identifier, _ hidden: Bool) {
        guard let it = item(id) else { return }
        if #available(macOS 15.0, *) { it.isHidden = hidden }
        it.view?.isHidden = hidden
    }

    // MARK: dalla pagina alla finestra
    func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let s = message.body as? String, let d = s.data(using: .utf8),
              let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return }
        switch (o["type"] as? String) ?? "state" {
        case "askDest": askDest(o)
        case "conflicts": askConflicts(o)
        case "transfer": onTransfer(o)
        case "pdfAsk": askPdf(o)
        case "pdfDone": pdfDone(o)
        case "toast":
            if let w = window {
                let a = NSAlert(); a.messageText = (o["text"] as? String) ?? ""
                a.beginSheetModal(for: w, completionHandler: nil)
            }
        case "error": showError((o["text"] as? String) ?? "")
        default: applyState(o)
        }
    }

    func js(_ cmd: String, _ arg: Any? = nil) {
        var a = "null"
        if let arg = arg {
            if let d = try? JSONSerialization.data(withJSONObject: [arg], options: [.fragmentsAllowed]),
               let s = String(data: d, encoding: .utf8) { a = String(s.dropFirst().dropLast()) }
        }
        let code = "window.provinoNative && window.provinoNative(\(jsonString(cmd)), \(a))"
        web.evaluateJavaScript(code, completionHandler: nil)
    }

    func jsonString(_ s: String) -> String {
        let d = try! JSONSerialization.data(withJSONObject: [s])
        return String(String(data: d, encoding: .utf8)!.dropFirst().dropLast())
    }

    func applyState(_ st: [String: Any]) {
        state = st
        let ready = (st["ready"] as? Bool) ?? false
        let title = (st["title"] as? String) ?? "Provino"
        window?.title = title.isEmpty ? "Provino" : title
        window?.subtitle = (st["subtitle"] as? String) ?? ""
        if let l = st["lang"] as? String, l != LANG, TXT[l] != nil {
            LANG = l
            relabel()
            let ad = NSApp.delegate as? AppDelegate
            ad?.buildMenu()
            // voci aggiunte da macOS (Modifica, Vista, Finestra): seguono la lingua dell'app al prossimo avvio
            UserDefaults.standard.set([l], forKey: "AppleLanguages")
            // la finestra Impostazioni si ricostruisce nella nuova lingua
            if let sw = ad?.settings {
                let wasOpen = sw.window?.isVisible ?? false
                sw.close()
                ad?.settings = nil
                if wasOpen { ad?.openSettings() }
            }
        }
        let go = (st["go"] as? [String: Any]) ?? [:]
        goBtn.title = (go["label"] as? String) ?? T("download")
        goBtn.toolTip = go["small"] as? String
        goBtn.isEnabled = (go["enabled"] as? Bool) ?? false
        panelBtn.state = ((st["split"] as? Bool) ?? false) ? .on : .off
        camItem.isEnabled = (st["canChange"] as? Bool) ?? false
        // prima di entrare: icona + "Cambia fotocamera", cosi' si impara il simbolo; dentro solo l'icona
        // nella scelta iniziale non c'e' niente da cambiare: il pulsante sparisce
        let canChange = (st["canChange"] as? Bool) ?? false
        let camLabel: String? = !canChange ? "-" : (ready ? nil : T("changeShort"))
        if camLabel != camLabelShown {
            camLabelShown = camLabel
            if #available(macOS 15.0, *) {
                camItem.isHidden = !canChange
                if canChange { camItem.image = cameraSwitchImage(label: camLabel) }
            } else {
                camItem.image = canChange ? cameraSwitchImage(label: camLabel) : NSImage(size: NSSize(width: 1, height: 1))
                camItem.showsIndicator = canChange
            }
        }
        for id: NSToolbarItem.Identifier in [.show, .films, .pick, .go, .panel] {
            setHidden(id, !ready)
            item(id)?.isEnabled = ready
        }
        pickItem.isEnabled = ready
        if !ready { pickItem.title = ""; pickItem.image = nil }
        guard ready else { return }
        let c = (st["counts"] as? [String: Int]) ?? [:]
        showSeg.setEnabled((c["HIF"] ?? 0) > 0, forSegment: 3)
        showSeg.setEnabled((c["VIDEO"] ?? 0) > 0, forSegment: 4)
        let f = (st["filter"] as? String) ?? "both"
        if let i = FILTERS.firstIndex(of: f), showSeg.selectedSegment != i { showSeg.selectedSegment = i }
        let films = (st["films"] as? [[String]]) ?? []
        let vals = films.map { $0.first ?? "" }
        let labels = films.map { $0.count > 1 ? $0[1] : $0[0] }
        // anche le etichette: cambiando lingua "Tutte le pellicole" diventa "All film simulations"
        if vals != filmValues || labels != filmLabels {
            filmValues = vals
            filmLabels = labels
            let sel = filmPop.indexOfSelectedItem
            filmPop.removeAllItems()
            filmPop.addItems(withTitles: labels)
            if sel >= 0 && sel < labels.count { filmPop.selectItem(at: sel) }
        }
        setHidden(.films, films.count <= 1)
        let cur = (st["film"] as? String) ?? ""
        if let i = filmValues.firstIndex(of: cur), filmPop.indexOfSelectedItem != i { filmPop.selectItem(at: i) }
        let n = (st["picked"] as? Int) ?? 0
        pickItem.title = T("pick")   // il numero e' gia' sul pulsante Scarica
        pickItem.toolTip = n > 0 ? ((st["sum"] as? String) ?? "") : T("pick_none")
        let m = NSMenu()
        let h = NSMenuItem(title: T("by_type"), action: nil, keyEquivalent: "")
        h.isEnabled = false
        m.addItem(h)
        for (key, lab) in [("JPG", "sel_jpg"), ("RAF", "sel_raf"), ("both", "sel_both"), ("HIF", "sel_heif"), ("VIDEO", "sel_video")] {
            if let v = c[key], v > 0 { m.addItem(sel("\(T(lab))  (\(v))", key)) }
        }
        m.addItem(.separator())
        m.addItem(sel("\(T("sel_fresh"))  (\(c["fresh"] ?? 0))", "fresh"))
        m.addItem(sel(T("sel_visible"), "visible"))
        m.addItem(sel(T("sel_bydate"), "bydate"))
        m.addItem(.separator())
        m.addItem(sel(T("deselect"), "none"))
        m.addItem(.separator())
        let pi = NSMenuItem(title: n > 0 ? T("pdfSel") : T("pdfVis"), action: #selector(onPdf), keyEquivalent: "")
        pi.target = self
        m.addItem(pi)
        let pr = NSMenuItem(title: T("pdfRead"), action: #selector(readPdf), keyEquivalent: "")
        pr.target = self
        m.addItem(pr)
        if n > 0, let sum = st["sum"] as? String, !sum.isEmpty {
            m.addItem(.separator())
            let s = NSMenuItem(title: sum, action: nil, keyEquivalent: "")
            s.isEnabled = false
            m.addItem(s)
        }
        pickItem.menu = m
    }

    func sel(_ title: String, _ key: String) -> NSMenuItem {
        let i = NSMenuItem(title: title, action: #selector(onSelect(_:)), keyEquivalent: "")
        i.target = self
        i.representedObject = key
        return i
    }

    @objc func onSelect(_ s: NSMenuItem) { js("select", s.representedObject as? String ?? "none") }
    @objc func onShow(_ s: NSSegmentedControl) { js("filter", FILTERS[max(0, s.selectedSegment)]) }
    @objc func onFilm(_ s: NSPopUpButton) {
        let i = s.indexOfSelectedItem
        js("film", i >= 0 && i < filmValues.count ? filmValues[i] : "")
    }
    @objc func onGo() { js("download") }
    @objc func onPdf() { js("pdf") }
    @objc func readPdf() {
        guard let w = window else { return }
        let p = NSOpenPanel()
        p.allowedFileTypes = ["pdf"]
        p.canChooseDirectories = false
        p.beginSheetModal(for: w) { r in
            if r == .OK, let u = p.url { self.js("pdfRead", u.path) }
        }
    }
    @objc func onPanel() { js("split") }

    func showError(_ text: String) {
        guard let w = window, !text.isEmpty else { return }
        let a = NSAlert()
        a.messageText = text
        a.alertStyle = .warning
        a.beginSheetModal(for: w, completionHandler: nil)
    }

    // MARK: foglio Scarica
    func askDest(_ req: [String: Any]) {
        guard let w = window else { return }
        let s = DestSheet(req: req, owner: self)
        destSheet = s
        w.beginSheet(s.window) { _ in self.destSheet = nil }
    }

    func askConflicts(_ req: [String: Any]) {
        guard let w = window else { return }
        let s = ConflictSheet(req: req, owner: self)
        confSheet = s
        if let d = destSheet?.window, d.isVisible { w.endSheet(d) }
        w.beginSheet(s.window) { _ in self.confSheet = nil }
    }

    // MARK: PDF (titolo, poi dove salvarlo)
    func askPdf(_ req: [String: Any]) {
        guard let w = window else { return }
        let L = (req["labels"] as? [String: String]) ?? [:]
        let a = NSAlert()
        a.messageText = L["head"] ?? ""
        a.informativeText = L["body"] ?? ""
        let field = NSTextField(string: (req["title"] as? String) ?? "")
        field.frame = NSRect(x: 0, y: 0, width: 300, height: 24)
        field.placeholderString = L["title"]
        a.accessoryView = field
        a.addButton(withTitle: L["ok"] ?? "PDF")
        a.addButton(withTitle: L["cancel"] ?? T("cancel"))
        a.window.initialFirstResponder = field
        a.beginSheetModal(for: w) { resp in
            guard resp == .alertFirstButtonReturn else { return }
            var title = field.stringValue.trimmingCharacters(in: .whitespaces)
            if title.isEmpty { title = (req["title"] as? String) ?? "Provino" }
            let safe = title.components(separatedBy: CharacterSet(charactersIn: "/\\:*?\"<>|")).joined(separator: "-")
            let p = NSSavePanel()
            p.nameFieldStringValue = safe + ".pdf"
            p.allowedFileTypes = ["pdf"]
            p.canCreateDirectories = true
            DispatchQueue.main.async {
                p.beginSheetModal(for: w) { r in
                    if r == .OK, let u = p.url { self.js("pdfGo", ["title": title, "path": u.path]) }
                }
            }
        }
    }

    func pdfDone(_ o: [String: Any]) {
        guard let path = o["path"] as? String else { return }
        let u = URL(fileURLWithPath: path)
        NSWorkspace.shared.activateFileViewerSelecting([u])   // il PDF nel Finder
        NSWorkspace.shared.open(u)                            // e aperto in Anteprima per controllarlo
    }

    // MARK: avanzamento
    func onTransfer(_ st: [String: Any]) {
        let mode = (st["mode"] as? String) ?? "none"
        let prev = tr["mode"] as? String, prevN = tr["n"] as? Int
        tr = st
        let pct = (st["pct"] as? Double) ?? Double((st["pct"] as? Int) ?? 0)
        if mode == "none" {
            setHidden(.transfer, true)
            trPopover?.close()
            return
        }
        setHidden(.transfer, false)
        switch mode {
        case "run":
            ring.isHidden = false
            ringBtn.image = nil
            ring.progress = CGFloat(max(3, pct)) / 100
        case "ok":
            ring.isHidden = true
            ringBtn.image = NSImage(systemSymbolName: "checkmark.circle.fill", accessibilityDescription: nil)?
                .withSymbolConfiguration(.init(pointSize: 17, weight: .regular))
            ringBtn.contentTintColor = .systemGreen
        default:
            ring.isHidden = true
            ringBtn.image = NSImage(systemSymbolName: "exclamationmark.circle.fill", accessibilityDescription: nil)?
                .withSymbolConfiguration(.init(pointSize: 17, weight: .regular))
            ringBtn.contentTintColor = .systemOrange
        }
        ringBtn.toolTip = (st["name"] as? String) ?? T("transfers")
        if let p = trPopover, p.isShown, let vc = p.contentViewController as? TransferPop { vc.update(st) }
        // a fine download il riquadro si apre da solo, come i download di Safari
        if (mode == "ok" || mode == "warn") && (prev != mode || prevN != (st["n"] as? Int)) && prev != nil && prev != "none" {
            showTransfer()
            if !NSApp.isActive { NSApp.requestUserAttention(.informationalRequest) }
        }
    }

    @objc func onRing() {
        if let p = trPopover, p.isShown { p.close(); return }
        showTransfer()
    }

    func showTransfer() {
        let vc = TransferPop(owner: self)
        let p = NSPopover()
        p.behavior = .transient
        p.contentViewController = vc
        p.delegate = vc
        vc.update(tr)
        trPopover?.close()
        trPopover = p
        p.show(relativeTo: ringBox.bounds, of: ringBox, preferredEdge: .minY)
    }

    // MARK: pagina
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        startLbl?.isHidden = true
        web.isHidden = false
        js("theme", AppDelegate.theme == "system" ? "" : AppDelegate.theme)
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if url.host == "127.0.0.1" || url.scheme == "about" { decisionHandler(.allow); return }
        NSWorkspace.shared.open(url)   // link esterni nel browser
        decisionHandler(.cancel)
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url { NSWorkspace.shared.open(url) }
        return nil
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }

    func windowWillClose(_ notification: Notification) { NSApp.terminate(nil) }
}

// MARK: - anello dell'avanzamento (colore principale del sistema, ben visibile mentre scarica)

final class RingView: NSView {
    private let track = CAShapeLayer()
    private let bar = CAShapeLayer()
    var progress: CGFloat = 0 { didSet { bar.strokeEnd = max(0, min(1, progress)) } }

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        for l in [track, bar] {
            l.fillColor = NSColor.clear.cgColor
            l.lineWidth = 3
            l.lineCap = .round
            layer?.addSublayer(l)
        }
        bar.strokeEnd = 0
    }
    required init?(coder: NSCoder) { fatalError() }

    override func layout() {
        super.layout()
        let r = bounds.insetBy(dx: 2, dy: 2)
        // parte da mezzogiorno e gira in senso orario
        let path = CGMutablePath()
        let c = CGPoint(x: r.midX, y: r.midY), rad = r.width / 2
        path.addArc(center: c, radius: rad, startAngle: .pi / 2, endAngle: .pi / 2 - 2 * .pi, clockwise: true)
        for l in [track, bar] { l.frame = bounds; l.path = path }
        updateColors()
    }

    override func viewDidChangeEffectiveAppearance() { super.viewDidChangeEffectiveAppearance(); updateColors() }

    func updateColors() {
        effectiveAppearance.performAsCurrentDrawingAppearance {
            self.track.strokeColor = NSColor.controlAccentColor.withAlphaComponent(0.22).cgColor
            self.bar.strokeColor = NSColor.controlAccentColor.cgColor
        }
    }
}

// MARK: - riquadro dell'avanzamento

final class TransferPop: NSViewController, NSPopoverDelegate {
    weak var owner: MainWindow?
    let name = label("", size: 13, weight: .semibold)
    let info = label("", size: 11, color: .secondaryLabelColor, wrap: true)
    let bar = NSProgressIndicator()
    let action = NSButton(title: "", target: nil, action: nil)
    let all = NSButton(title: "", target: nil, action: nil)

    init(owner: MainWindow) { self.owner = owner; super.init(nibName: nil, bundle: nil) }
    required init?(coder: NSCoder) { fatalError() }

    override func loadView() {
        bar.style = .bar
        bar.isIndeterminate = false
        bar.minValue = 0
        bar.maxValue = 100
        action.bezelStyle = .rounded
        action.target = self
        action.action = #selector(onAction)
        info.preferredMaxLayoutWidth = 280
        name.lineBreakMode = .byTruncatingMiddle
        all.bezelStyle = .rounded
        all.target = self
        all.action = #selector(onAll)
        let row = NSStackView(views: [all, NSView(), action])
        row.distribution = .fill
        let st = NSStackView(views: [name, info, bar, row])
        st.orientation = .vertical
        st.alignment = .leading
        st.spacing = 6
        st.edgeInsets = NSEdgeInsets(top: 14, left: 16, bottom: 14, right: 16)
        bar.translatesAutoresizingMaskIntoConstraints = false
        row.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            st.widthAnchor.constraint(equalToConstant: 320),
            bar.widthAnchor.constraint(equalTo: st.widthAnchor, constant: -32),
            row.widthAnchor.constraint(equalTo: st.widthAnchor, constant: -32),
        ])
        view = st
    }

    func update(_ st: [String: Any]) {
        _ = view
        let mode = (st["mode"] as? String) ?? "none"
        name.stringValue = (st["name"] as? String) ?? ""
        info.stringValue = (st["info"] as? String) ?? ""
        info.isHidden = info.stringValue.isEmpty
        bar.isHidden = mode != "run"
        bar.doubleValue = (st["pct"] as? Double) ?? Double((st["pct"] as? Int) ?? 0)
        action.title = mode == "run" ? ((st["cancel"] as? String) ?? T("cancel")) : ((st["open"] as? String) ?? "")
        action.isHidden = action.title.isEmpty
        action.keyEquivalent = mode == "run" ? "" : "\r"
        all.title = (st["all"] as? String) ?? ""
        all.isHidden = all.title.isEmpty
    }

    @objc func onAll() { owner?.js("queue"); owner?.trPopover?.close() }

    @objc func onAction() {
        guard let o = owner else { return }
        if (o.tr["mode"] as? String) == "run" { o.js("cancelDownload") } else { o.js("openFolder"); o.trPopover?.close() }
    }

    func popoverDidClose(_ notification: Notification) {
        guard let o = owner, let m = o.tr["mode"] as? String, m == "ok" || m == "warn" else { return }
        o.js("trayClosed")
    }
}

// MARK: - aggiornamento dentro l'app (1.1.2)

/// Scarica il .dmg con il motore (barra di avanzamento e impronta controllata), copia la nuova Provino.app
/// accanto a quella in uso e, alla conferma, un piccolo script le scambia quando Provino si e' chiuso e lo riapre.
/// Se un passo non riesce, si apre la pagina dei download come prima.
final class SelfUpdate: NSObject {
    static var bundlePath: String { Bundle.main.bundlePath }
    static var possible: Bool {
        let p = bundlePath
        if !p.hasSuffix(".app") || p.contains("/AppTranslocation/") || p.hasPrefix("/Volumes/") { return false }
        return FileManager.default.isWritableFile(atPath: (p as NSString).deletingLastPathComponent)
    }

    weak var app: AppDelegate?
    let version: String
    let page: String
    let force: Bool
    let window: NSWindow
    let title = label("", size: 13, weight: .semibold)
    let info = label("", size: 11, color: .secondaryLabelColor)
    let bar = NSProgressIndicator()
    let cancelBtn = NSButton(title: T("cancel"), target: nil, action: nil)
    var timer: Timer?
    var done = false

    init(app: AppDelegate, version: String, page: String, force: Bool) {
        self.app = app
        self.version = version
        self.page = page
        self.force = force
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 380, height: 120), styleMask: [.titled], backing: .buffered, defer: false)
        super.init()
        title.stringValue = T("updDl", ["v": version])
        info.stringValue = " "
        bar.style = .bar
        bar.isIndeterminate = true
        bar.minValue = 0
        bar.maxValue = 1
        bar.startAnimation(nil)
        cancelBtn.target = self
        cancelBtn.action = #selector(onCancel)
        cancelBtn.keyEquivalent = "\u{1b}"
        let row = NSStackView(views: [NSView(), cancelBtn])
        let st = NSStackView(views: [title, bar, info, row])
        st.orientation = .vertical
        st.alignment = .leading
        st.spacing = 8
        st.edgeInsets = NSEdgeInsets(top: 18, left: 20, bottom: 16, right: 20)
        for v in [bar, row] as [NSView] {
            v.translatesAutoresizingMaskIntoConstraints = false
            v.widthAnchor.constraint(equalTo: st.widthAnchor, constant: -40).isActive = true
        }
        st.translatesAutoresizingMaskIntoConstraints = false
        st.widthAnchor.constraint(equalToConstant: 380).isActive = true
        window.contentView = st
    }

    func start() {
        guard let app = app, let w = app.main.window else { return }
        w.beginSheet(window, completionHandler: nil)
        // il controllo dello stato parte solo quando il motore ha azzerato lo stato del download precedente
        app.engine.post("/api/update/start", ["platform": "mac", "force": force]) { [weak self] _ in
            guard let s = self, !s.done else { return }
            s.timer = Timer.scheduledTimer(withTimeInterval: 0.3, repeats: true) { [weak self] _ in self?.tick() }
        }
    }

    func mb(_ n: Double) -> String {
        let s = String(format: "%.1f", n / 1_048_576)
        return LANG == "it" ? s.replacingOccurrences(of: ".", with: ",") : s
    }

    func tick() {
        guard !done, let app = app else { return }
        app.engine.get("/api/update/state") { [weak self] st in
            guard let s = self, !s.done else { return }
            let status = (st["status"] as? String) ?? ""
            let got = (st["got"] as? Double) ?? Double((st["got"] as? Int) ?? 0)
            let total = (st["total"] as? Double) ?? Double((st["total"] as? Int) ?? 0)
            switch status {
            case "downloading":
                if total > 0 {
                    s.bar.isIndeterminate = false
                    s.bar.doubleValue = min(1, got / total)
                    s.info.stringValue = T("updDlOf", ["a": s.mb(got), "b": s.mb(total)])
                }
            case "verifying":
                s.info.stringValue = T("updDlCheck")
            case "ready":
                s.done = true
                s.timer?.invalidate()
                s.prepare((st["path"] as? String) ?? "")
            case "error", "idle":
                s.fail((st["error"] as? String) ?? status)
            default: break
            }
        }
    }

    @discardableResult
    func run(_ tool: String, _ args: [String]) -> Bool {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: tool)
        p.arguments = args
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return false }
        p.waitUntilExit()
        return p.terminationStatus == 0
    }

    /// Apre il .dmg senza mostrarlo e copia Provino.app in "<app>.new", accanto a quella in uso.
    func prepare(_ dmg: String) {
        bar.isIndeterminate = true
        bar.startAnimation(nil)
        info.stringValue = T("updDlPrep")
        cancelBtn.isEnabled = false
        let appPath = SelfUpdate.bundlePath
        let staged = appPath + ".new"
        DispatchQueue.global(qos: .userInitiated).async {
            let fm = FileManager.default
            let mnt = NSTemporaryDirectory() + "provino-upd-\(ProcessInfo.processInfo.processIdentifier)"
            try? fm.removeItem(atPath: staged)
            try? fm.createDirectory(atPath: mnt, withIntermediateDirectories: true)
            var ok = !dmg.isEmpty && self.run("/usr/bin/hdiutil", ["attach", dmg, "-nobrowse", "-readonly", "-mountpoint", mnt])
            if ok {
                let src = mnt + "/Provino.app"
                ok = fm.fileExists(atPath: src + "/Contents/MacOS/Provino") && self.run("/usr/bin/ditto", [src, staged])
                self.run("/usr/bin/hdiutil", ["detach", mnt, "-force"])
            }
            try? fm.removeItem(atPath: mnt)
            ok = ok && fm.fileExists(atPath: staged + "/Contents/MacOS/Provino")
            DispatchQueue.main.async {
                if ok { self.confirm(dmg: dmg, appPath: appPath, staged: staged) }
                else { try? fm.removeItem(atPath: staged); self.fail("prepare") }
            }
        }
    }

    func close() {
        timer?.invalidate()
        window.sheetParent?.endSheet(window)
    }

    func confirm(dmg: String, appPath: String, staged: String) {
        close()
        let a = NSAlert()
        a.messageText = T("updReady", ["v": version])
        a.informativeText = T("updReadyInfo")
        a.addButton(withTitle: T("updRestart"))
        a.addButton(withTitle: T("updLater"))
        let go: (NSApplication.ModalResponse) -> Void = { resp in
            if resp == .alertFirstButtonReturn {
                self.swapAndRestart(dmg: dmg, appPath: appPath, staged: staged)
            } else {
                _ = try? FileManager.default.removeItem(atPath: staged)
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
            if let w = self.app?.main.window { a.beginSheetModal(for: w, completionHandler: go) } else { go(a.runModal()) }
        }
    }

    /// Lo scambio avviene quando Provino si e' chiuso: se non riesce, la versione in uso torna al suo posto.
    func swapAndRestart(dmg: String, appPath: String, staged: String) {
        let script = """
        APP="$1"; NEW="$2"; PID="$3"; DMG="$4"
        i=0; while kill -0 "$PID" 2>/dev/null && [ $i -lt 150 ]; do sleep 0.2; i=$((i+1)); done
        OLD="$APP.old"; rm -rf "$OLD"
        if mv "$APP" "$OLD"; then
          if mv "$NEW" "$APP"; then rm -rf "$OLD"; else mv "$OLD" "$APP"; fi
        fi
        rm -rf "$NEW"; rm -f "$DMG"
        open "$APP"
        """
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/sh")
        p.arguments = ["-c", script, "provino-update", appPath, staged, "\(ProcessInfo.processInfo.processIdentifier)", dmg]
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { fail("script"); return }
        NSApp.terminate(nil)
    }

    func fail(_ why: String) {
        done = true
        close()
        NSLog("Provino: aggiornamento non riuscito (%@)", why)
        if why == "idle" { return }   // annullato
        let page = self.page
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
            self.app?.alert(T("updDlFail"), T("updDlFailInfo"))
            if let url = URL(string: page) { NSWorkspace.shared.open(url) }
        }
    }

    @objc func onCancel() {
        done = true
        app?.engine.post("/api/update/cancel", [:]) { _ in }
        close()
    }
}

// MARK: - foglio "Scarica N file"

/// Riquadro dell'anteprima delle cartelle: i colori si ricalcolano col tema (chiaro/scuro),
/// altrimenti in scuro restava bianco con il testo bianco (visto il 9 nov 2026).
final class PreviewBox: NSView {
    override init(frame: NSRect) { super.init(frame: frame); wantsLayer = true }
    required init?(coder: NSCoder) { super.init(coder: coder); wantsLayer = true }
    override var wantsUpdateLayer: Bool { true }
    override func updateLayer() {
        layer?.cornerRadius = 6
        layer?.borderWidth = 1
        layer?.borderColor = NSColor.separatorColor.cgColor
        layer?.backgroundColor = NSColor.textBackgroundColor.cgColor
    }
}

final class DestSheet: NSObject, NSTextFieldDelegate {
    let window: NSWindow
    let req: [String: Any]
    weak var owner: MainWindow?
    var path: String
    let pathLbl = label("", size: 13)
    let byDate = NSButton(checkboxWithTitle: T("by_date"), target: nil, action: nil)
    let split = NSButton(checkboxWithTitle: T("split"), target: nil, action: nil)
    let preview = NSTextField(wrappingLabelWithString: "")
    // 1.1: cartella dell'evento (2026_10_30_Nome), al posto delle cartelle per giorno
    let evCheck = NSButton(checkboxWithTitle: T("event"), target: nil, action: nil)
    let evField = NSTextField(string: "")
    let evNote = label(T("event_hint"), size: 11, color: .secondaryLabelColor)
    // 1.1.1: cartella scelta che e' gia' una cartella evento (AAAA_MM_GG_...): niente cartelle nuove dentro
    let inEvent = label("", size: 11, color: .secondaryLabelColor)
    let nestWarn = label("", size: 12, color: .systemOrange, wrap: true)
    func isEventFolder(_ p: String) -> Bool {
        let n = (p as NSString).lastPathComponent
        return n.range(of: "^[0-9]{4}_[0-9]{2}_[0-9]{2}_", options: .regularExpression) != nil
    }
    func eventFolderPicked() {
        if isEventFolder(path) { byDate.state = .off; evCheck.state = .off }
    }

    init(req: [String: Any], owner: MainWindow) {
        self.req = req
        self.owner = owner
        path = (req["dest"] as? String) ?? NSHomeDirectory() + "/Pictures/Provino"
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 520, height: 300), styleMask: [.titled], backing: .buffered, defer: false)
        super.init()
        let n = "\((req["n"] as? Int) ?? 0)"
        let title = label(T("dl_title", ["n": n]), size: 15, weight: .bold)
        let kinds = (req["kinds"] as? [String: Int]) ?? [:]
        let summary = kinds.sorted { $0.key < $1.key }.map { "\($0.value) \($0.key)" }.joined(separator: ", ") + " · " + ((req["size"] as? String) ?? "")
        let sub = label(summary, size: 12, color: .secondaryLabelColor)

        let fl = label(T("folder"), size: 13)
        pathLbl.lineBreakMode = .byTruncatingMiddle
        pathLbl.isSelectable = true
        let ch = NSButton(title: T("choose"), target: self, action: #selector(pick))
        ch.bezelStyle = .rounded
        let frow = NSStackView(views: [fl, pathLbl, ch])
        frow.spacing = 8
        pathLbl.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        byDate.state = ((req["by_date"] as? Bool) ?? false) ? .on : .off
        split.state = ((req["split_type"] as? Bool) ?? false) ? .on : .off
        byDate.target = self; byDate.action = #selector(onByDate)
        split.target = self; split.action = #selector(refresh)
        evCheck.state = ((req["event_mode"] as? Bool) ?? false) ? .on : .off
        if evCheck.state == .on { byDate.state = .off }
        eventFolderPicked()
        evCheck.target = self; evCheck.action = #selector(onEvent)
        evField.stringValue = (req["event"] as? String) ?? ""
        evField.font = NSFont.monospacedSystemFont(ofSize: 13, weight: .regular)
        evField.delegate = self
        evField.translatesAutoresizingMaskIntoConstraints = false
        evField.widthAnchor.constraint(equalToConstant: 380).isActive = true
        let days = (req["days"] as? [String]) ?? []
        var dateNote = ""
        if days.count == 1, let d = days.first, d.count >= 8 {
            let a = Array(d)
            dateNote = T("by_date_one", ["d": "\(String(a[0..<4]))-\(String(a[4..<6]))-\(String(a[6..<8]))"])
        } else if days.count > 1 { dateNote = T("by_date_n", ["n": "\(days.count)"]) }
        let ks = ["RAF", "JPG", "HEIF", "VIDEO"].filter { kinds[$0] != nil }
        let kj = ks.count > 1 ? ks.dropLast().joined(separator: ", ") + " " + T("and") + " " + ks.last! : (ks.first ?? "")
        let dn = label(dateNote, size: 11, color: .secondaryLabelColor)
        let sn = label(T("split_sub", ["k": kj]), size: 11, color: .secondaryLabelColor)

        let wl = label(T("where"), size: 12, color: .secondaryLabelColor)
        nestWarn.preferredMaxLayoutWidth = 470
        preview.isSelectable = true
        preview.preferredMaxLayoutWidth = 470
        let box = PreviewBox()
        preview.translatesAutoresizingMaskIntoConstraints = false
        box.addSubview(preview)
        NSLayoutConstraint.activate([
            preview.leadingAnchor.constraint(equalTo: box.leadingAnchor, constant: 10),
            preview.trailingAnchor.constraint(lessThanOrEqualTo: box.trailingAnchor, constant: -10),
            preview.topAnchor.constraint(equalTo: box.topAnchor, constant: 8),
            preview.bottomAnchor.constraint(equalTo: box.bottomAnchor, constant: -8),
        ])

        let cancel = NSButton(title: T("cancel"), target: self, action: #selector(onCancel))
        cancel.keyEquivalent = "\u{1b}"
        let go = NSButton(title: T("download"), target: self, action: #selector(onGo))
        go.keyEquivalent = "\r"
        let buttons = NSStackView(views: [NSView(), cancel, go])
        buttons.spacing = 10

        let indent = { (v: NSView) -> NSView in
            let s = NSStackView(views: [v]); s.edgeInsets = NSEdgeInsets(top: -4, left: 20, bottom: 0, right: 0); return s }
        var rows: [NSView] = [title, sub, frow, inEvent, byDate]
        if !dateNote.isEmpty { rows.append(indent(dn)) }
        evRow = indent(evField)
        evHint = indent(evNote)
        rows += [evCheck, evRow!, evHint!, split, indent(sn), nestWarn, wl, box, buttons]
        let st = NSStackView(views: rows)
        st.orientation = .vertical
        st.alignment = .leading
        st.spacing = 10
        st.setCustomSpacing(4, after: title)
        st.setCustomSpacing(16, after: sub)
        st.setCustomSpacing(16, after: frow)
        st.setCustomSpacing(4, after: wl)
        st.setCustomSpacing(18, after: box)
        st.edgeInsets = NSEdgeInsets(top: 20, left: 20, bottom: 20, right: 20)
        for v in [frow, box, buttons] {
            v.translatesAutoresizingMaskIntoConstraints = false
            v.widthAnchor.constraint(equalTo: st.widthAnchor, constant: -40).isActive = true
        }
        st.translatesAutoresizingMaskIntoConstraints = false
        st.widthAnchor.constraint(equalToConstant: 520).isActive = true
        window.contentView = st
        window.defaultButtonCell = go.cell as? NSButtonCell
        refresh()
    }

    var evRow: NSView?
    var evHint: NSView?

    @objc func onByDate() { if byDate.state == .on { evCheck.state = .off }; refresh() }
    @objc func onEvent() {
        if evCheck.state == .on {
            byDate.state = .off
            window.makeFirstResponder(evField)
            evField.currentEditor()?.selectedRange = NSRange(location: evField.stringValue.count, length: 0)
        }
        refresh()
    }

    /// come safe_event in provino.py: spazi -> _, niente caratteri vietati nei nomi delle cartelle
    func clean(_ s: String) -> String {
        var out = ""
        var lastSpace = false
        for ch in s {
            if "/\\:*?\"<>|".contains(ch) || (ch.asciiValue.map { $0 < 32 } ?? false) { continue }
            if ch.isWhitespace { if !lastSpace { out.append("_") }; lastSpace = true; continue }
            lastSpace = false
            out.append(ch)
        }
        return out
    }

    func controlTextDidChange(_ obj: Notification) {
        let v = evField.stringValue, c = clean(v)
        if c != v {
            let pos = (evField.currentEditor()?.selectedRange.location ?? c.count) - (v.count - c.count)
            evField.stringValue = c
            evField.currentEditor()?.selectedRange = NSRange(location: max(0, min(pos, (c as NSString).length)), length: 0)
        }
        evNote.stringValue = T("event_hint")
        evNote.textColor = .secondaryLabelColor
        refresh()
    }

    func eventName() -> String {
        var n = clean(evField.stringValue)
        while n.hasSuffix("_") || n.hasSuffix(".") { n.removeLast() }
        while n.hasPrefix(".") { n.removeFirst() }
        return n
    }

    @objc func refresh() {
        evRow?.isHidden = evCheck.state != .on
        evHint?.isHidden = evCheck.state != .on
        pathLbl.stringValue = nice(path)
        let ev = isEventFolder(path)
        inEvent.stringValue = T("in_event")
        inEvent.isHidden = !ev
        nestWarn.stringValue = T("nested_warn", ["n": (path as NSString).lastPathComponent])
        nestWarn.isHidden = !(ev && (byDate.state == .on || evCheck.state == .on))
        let base = nice(path)
        var seen = Set<String>()
        let out = NSMutableAttributedString()
        let mono = NSFont.monospacedSystemFont(ofSize: 11.5, weight: .regular)
        let bold = NSFont.monospacedSystemFont(ofSize: 11.5, weight: .bold)
        let files = (req["files"] as? [[String]]) ?? []
        var count = 0
        for f in files where f.count >= 3 {
            let (name, day, k) = (f[0], f[1], f[2])
            var parts: [String] = []
            if evCheck.state == .on {
                parts.append(eventName().isEmpty ? "…" : eventName())
            } else if byDate.state == .on, day.count == 8 {
                let a = Array(day)
                parts.append("\(String(a[0..<4]))-\(String(a[4..<6]))-\(String(a[6..<8]))")
            }
            if split.state == .on { parts.append(k) }
            let key = parts.joined(separator: "/")
            if seen.contains(key) { continue }
            seen.insert(key)
            if count > 0 { out.append(NSAttributedString(string: "\n")) }
            out.append(NSAttributedString(string: base, attributes: [.font: mono, .foregroundColor: NSColor.secondaryLabelColor]))
            for p in parts {
                out.append(NSAttributedString(string: "/", attributes: [.font: mono, .foregroundColor: NSColor.secondaryLabelColor]))
                out.append(NSAttributedString(string: p, attributes: [.font: bold, .foregroundColor: NSColor.labelColor]))
            }
            out.append(NSAttributedString(string: "/" + name, attributes: [.font: mono, .foregroundColor: NSColor.secondaryLabelColor]))
            count += 1
            if count >= 6 { break }
        }
        preview.attributedStringValue = out
    }

    @objc func pick() {
        let p = NSOpenPanel()
        p.canChooseDirectories = true
        p.canChooseFiles = false
        p.canCreateDirectories = true
        p.prompt = T("choose_title")
        p.directoryURL = URL(fileURLWithPath: path)
        p.beginSheetModal(for: window) { r in
            if r == .OK, let u = p.url { self.path = u.path; self.eventFolderPicked(); self.refresh() }
        }
    }

    @objc func onCancel() { window.sheetParent?.endSheet(window) }

    @objc func onGo() {
        let hs = req["hs"] ?? []
        if evCheck.state == .on && eventName().isEmpty {
            NSSound.beep()
            evNote.stringValue = T("event_empty")
            evNote.textColor = .systemRed
            window.makeFirstResponder(evField)
            return
        }
        owner?.js("destConfirmed", ["dest": path, "by_date": byDate.state == .on, "split_type": split.state == .on, "hs": hs,
                                    "event": evCheck.state == .on ? eventName() : ""])
        window.sheetParent?.endSheet(window)
    }
}

// MARK: - foglio "File gia' nella cartella"

final class ConflictSheet: NSObject {
    let window: NSWindow
    let req: [String: Any]
    weak var owner: MainWindow?
    var choices: [Int: (act: String, field: NSTextField?)] = [:]
    var radios: [Int: [String: NSButton]] = [:]
    let okBtn: NSButton
    let others: Int
    var L: [String: String]

    init(req: [String: Any], owner: MainWindow) {
        self.req = req
        self.owner = owner
        L = (req["labels"] as? [String: String]) ?? [:]
        others = (req["others"] as? Int) ?? 0
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 560, height: 420), styleMask: [.titled, .resizable], backing: .buffered, defer: false)
        okBtn = NSButton(title: L["ok"] ?? T("download"), target: nil, action: nil)
        super.init()
        let title = label((req["title"] as? String) ?? "", size: 15, weight: .bold)
        let sub = label((req["sub"] as? String) ?? "", size: 12, color: .secondaryLabelColor, wrap: true)
        let items = (req["items"] as? [[String: Any]]) ?? []

        let list = NSStackView()
        list.orientation = .vertical
        list.alignment = .leading
        list.spacing = 14
        list.edgeInsets = NSEdgeInsets(top: 10, left: 12, bottom: 10, right: 12)
        for it in items {
            guard let h = it["h"] as? Int else { continue }
            let same = (it["same"] as? Bool) ?? false
            let icon = NSImageView(image: NSImage(systemSymbolName: same ? "checkmark.circle" : "exclamationmark.triangle", accessibilityDescription: nil)!)
            icon.contentTintColor = same ? .systemGreen : .systemOrange
            let nm = label((it["name"] as? String) ?? "", size: 13, weight: .semibold)
            let head = NSStackView(views: [icon, nm])
            head.spacing = 6
            let why = label((it["why"] as? String) ?? "", size: 11, color: .secondaryLabelColor, wrap: true)
            why.preferredMaxLayoutWidth = 480
            var opts: [NSView] = []
            var field: NSTextField?
            let def = same ? "skip" : "rename"
            var rs: [String: NSButton] = [:]
            let order: [(String, String)] = same ? [("skip", L["skip"] ?? "Skip"), ("overwrite", L["over"] ?? "Overwrite")]
                                                 : [("rename", L["saveAs"] ?? "Save as"), ("skip", L["skip"] ?? "Skip")]
            for (act, lab) in order {
                let r = NSButton(radioButtonWithTitle: lab, target: self, action: #selector(onRadio(_:)))
                r.tag = h
                r.identifier = NSUserInterfaceItemIdentifier(act)
                r.state = act == def ? .on : .off
                rs[act] = r
                if act == "rename" {
                    let f = NSTextField(string: (it["proposed"] as? String) ?? "")
                    f.placeholderString = L["newName"]
                    f.translatesAutoresizingMaskIntoConstraints = false
                    f.widthAnchor.constraint(equalToConstant: 200).isActive = true
                    field = f
                    opts.append(NSStackView(views: [r, f]))
                } else { opts.append(r) }
            }
            radios[h] = rs
            choices[h] = (def, field)
            let o = NSStackView(views: opts + [NSView()])
            o.spacing = 18
            let block = NSStackView(views: [head, why, o])
            block.orientation = .vertical
            block.alignment = .leading
            block.spacing = 4
            block.setCustomSpacing(8, after: why)
            list.addArrangedSubview(block)
        }

        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.borderType = .bezelBorder
        scroll.drawsBackground = true
        scroll.backgroundColor = .textBackgroundColor
        let flip = FlippedView()
        flip.translatesAutoresizingMaskIntoConstraints = false
        list.translatesAutoresizingMaskIntoConstraints = false
        flip.addSubview(list)
        NSLayoutConstraint.activate([
            list.leadingAnchor.constraint(equalTo: flip.leadingAnchor), list.trailingAnchor.constraint(equalTo: flip.trailingAnchor),
            list.topAnchor.constraint(equalTo: flip.topAnchor), list.bottomAnchor.constraint(equalTo: flip.bottomAnchor),
        ])
        scroll.documentView = flip
        flip.widthAnchor.constraint(equalTo: scroll.contentView.widthAnchor).isActive = true

        var top: [NSView] = [title, sub]
        let nSame = items.filter { ($0["same"] as? Bool) ?? false }.count
        if nSame > 1 {
            let a = NSButton(title: L["skipAll"] ?? "", target: self, action: #selector(bulk(_:)))
            a.identifier = NSUserInterfaceItemIdentifier("skip")
            let b = NSButton(title: L["overAll"] ?? "", target: self, action: #selector(bulk(_:)))
            b.identifier = NSUserInterfaceItemIdentifier("overwrite")
            for x in [a, b] { x.bezelStyle = .rounded; x.controlSize = .small }
            let r = NSStackView(views: [label(L["sameAll"] ?? "", size: 12), a, b])
            r.spacing = 8
            top.append(r)
        }
        let cancel = NSButton(title: L["cancel"] ?? T("cancel"), target: self, action: #selector(onCancel))
        cancel.keyEquivalent = "\u{1b}"
        okBtn.target = self
        okBtn.action = #selector(onOk)
        okBtn.keyEquivalent = "\r"
        let buttons = NSStackView(views: [NSView(), cancel, okBtn])
        buttons.spacing = 10
        let st = NSStackView(views: top + [scroll, buttons])
        st.orientation = .vertical
        st.alignment = .leading
        st.spacing = 10
        st.setCustomSpacing(4, after: title)
        st.edgeInsets = NSEdgeInsets(top: 20, left: 20, bottom: 20, right: 20)
        for v in [scroll, buttons] {
            v.translatesAutoresizingMaskIntoConstraints = false
            v.widthAnchor.constraint(equalTo: st.widthAnchor, constant: -40).isActive = true
        }
        let h = min(CGFloat(items.count) * 92 + 20, 380)
        scroll.heightAnchor.constraint(equalToConstant: max(120, h)).isActive = true
        st.translatesAutoresizingMaskIntoConstraints = false
        st.widthAnchor.constraint(greaterThanOrEqualToConstant: 560).isActive = true
        window.contentView = st
        okLabel()
    }

    @objc func onRadio(_ b: NSButton) {
        let act = b.identifier?.rawValue ?? "skip"
        choices[b.tag]?.act = act
        radios[b.tag]?.forEach { $0.value.state = $0.key == act ? .on : .off }
        okLabel()
    }

    @objc func bulk(_ b: NSButton) {
        let act = b.identifier?.rawValue ?? "skip"
        for (h, rs) in radios where rs[act] != nil {
            choices[h]?.act = act
            rs.forEach { $0.value.state = $0.key == act ? .on : .off }
        }
        okLabel()
    }

    func okLabel() {
        let nothing = others == 0 && choices.values.allSatisfy { $0.act == "skip" }
        okBtn.title = nothing ? (L["nothing"] ?? "OK") : (L["ok"] ?? T("download"))
    }

    @objc func onCancel() { window.sheetParent?.endSheet(window) }

    @objc func onOk() {
        var options: [String: Any] = [:]
        for (h, c) in choices {
            var o: [String: Any] = ["action": c.act]
            if c.act == "rename" { o["name"] = c.field?.stringValue ?? "" }
            options[String(h)] = o
        }
        owner?.js("conflictsDone", ["hs": req["hs"] ?? [], "options": options])
        window.sheetParent?.endSheet(window)
    }
}

final class FlippedView: NSView { override var isFlipped: Bool { true } }

// MARK: - Impostazioni

final class SettingsWindow: NSWindowController {
    weak var mainWin: MainWindow?
    var dest = ""
    let pathLbl = label("", size: 13)
    let byDate = NSButton(checkboxWithTitle: T("by_date"), target: nil, action: nil)
    let split = NSButton(checkboxWithTitle: T("split"), target: nil, action: nil)
    let lang = NSPopUpButton(frame: .zero, pullsDown: false)
    let theme = NSPopUpButton(frame: .zero, pullsDown: false)
    let autoUpd = NSButton(checkboxWithTitle: T("autoUpd"), target: nil, action: nil)

    init(mainWin: MainWindow) {
        self.mainWin = mainWin
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 520, height: 300), styleMask: [.titled, .closable], backing: .buffered, defer: false)
        w.title = T("settingsTitle")
        super.init(window: w)
        build()
        load()
    }
    required init?(coder: NSCoder) { fatalError() }

    func build() {
        pathLbl.lineBreakMode = .byTruncatingMiddle
        let ch = NSButton(title: T("choose"), target: self, action: #selector(pick))
        ch.bezelStyle = .rounded
        let frow = NSStackView(views: [pathLbl, ch])
        frow.spacing = 8
        byDate.target = self; byDate.action = #selector(save)
        split.target = self; split.action = #selector(save)
        let note = label(T("p_dl_sub"), size: 11, color: .secondaryLabelColor, wrap: true)
        note.preferredMaxLayoutWidth = 380
        let dlBox = NSStackView(views: [frow, byDate, split, note])
        dlBox.orientation = .vertical
        dlBox.alignment = .leading
        dlBox.spacing = 8

        lang.addItems(withTitles: ["Italiano", "English"])
        lang.target = self; lang.action = #selector(onLang)
        theme.addItems(withTitles: [T("system"), T("light"), T("dark")])
        theme.target = self; theme.action = #selector(onTheme)
        let langNote = label(T("langNote"), size: 11, color: .secondaryLabelColor, wrap: true)
        langNote.preferredMaxLayoutWidth = 380
        let langBox = NSStackView(views: [lang, langNote])
        langBox.orientation = .vertical
        langBox.alignment = .leading
        langBox.spacing = 6
        let safe = label(T("p_safe"), size: 11, color: .secondaryLabelColor, wrap: true)
        safe.preferredMaxLayoutWidth = 380
        safe.translatesAutoresizingMaskIntoConstraints = false
        safe.widthAnchor.constraint(equalToConstant: 380).isActive = true

        let g = NSGridView(views: [
            [label(T("folder"), size: 13), dlBox],
            [label(T("p_lang"), size: 13), langBox],
            [label(T("p_theme"), size: 13), theme],
            [NSGridCell.emptyContentView, autoUpd],
            [NSGridCell.emptyContentView, safe],
        ])
        g.column(at: 0).xPlacement = .trailing
        g.rowAlignment = .firstBaseline
        g.rowSpacing = 14
        g.columnSpacing = 10
        g.row(at: 4).topPadding = 8
        autoUpd.target = self
        autoUpd.action = #selector(onAutoUpd)
        let d = UserDefaults.standard
        autoUpd.state = (d.object(forKey: "autoUpdate") == nil || d.bool(forKey: "autoUpdate")) ? .on : .off
        g.translatesAutoresizingMaskIntoConstraints = false
        let c = NSView()
        c.addSubview(g)
        NSLayoutConstraint.activate([
            g.leadingAnchor.constraint(equalTo: c.leadingAnchor, constant: 30),
            g.trailingAnchor.constraint(equalTo: c.trailingAnchor, constant: -30),
            g.topAnchor.constraint(equalTo: c.topAnchor, constant: 24),
            g.bottomAnchor.constraint(equalTo: c.bottomAnchor, constant: -24),
            dlBox.widthAnchor.constraint(equalToConstant: 380),
        ])
        window?.contentView = c
    }

    func load() {
        lang.selectItem(at: LANG == "it" ? 0 : 1)
        theme.selectItem(at: ["system", "light", "dark"].firstIndex(of: AppDelegate.theme) ?? 0)
        mainWin?.engine.get("/api/state") { st in
            let s = (st["settings"] as? [String: Any]) ?? [:]
            self.dest = (st["dest"] as? String) ?? (s["dest"] as? String) ?? ""
            self.pathLbl.stringValue = nice(self.dest)
            self.byDate.state = ((s["by_date"] as? Bool) ?? false) ? .on : .off
            self.split.state = ((s["split_type"] as? Bool) ?? false) ? .on : .off
        }
    }

    @objc func save() {
        mainWin?.engine.post("/api/dest-settings", ["dest": dest, "by_date": byDate.state == .on, "split_type": split.state == .on])
    }

    @objc func pick() {
        guard let w = window else { return }
        let p = NSOpenPanel()
        p.canChooseDirectories = true
        p.canChooseFiles = false
        p.canCreateDirectories = true
        p.directoryURL = URL(fileURLWithPath: dest)
        p.beginSheetModal(for: w) { r in
            if r == .OK, let u = p.url { self.dest = u.path; self.pathLbl.stringValue = nice(self.dest); self.save() }
        }
    }

    @objc func onLang() { mainWin?.js("lang", lang.indexOfSelectedItem == 0 ? "it" : "en") }
    @objc func onAutoUpd() { UserDefaults.standard.set(autoUpd.state == .on, forKey: "autoUpdate") }
    @objc func onTheme() { AppDelegate.setTheme(["system", "light", "dark"][max(0, theme.indexOfSelectedItem)]) }
}

// MARK: - applicazione

final class AppDelegate: NSObject, NSApplicationDelegate {
    let engine = Engine()
    var main: MainWindow!
    var settings: SettingsWindow?
    static var theme: String = UserDefaults.standard.string(forKey: "theme") ?? "system"

    static func setTheme(_ t: String) {
        theme = t
        UserDefaults.standard.set(t, forKey: "theme")
        NSApp.appearance = t == "light" ? NSAppearance(named: .aqua) : t == "dark" ? NSAppearance(named: .darkAqua) : nil
        (NSApp.delegate as? AppDelegate)?.main?.js("theme", t == "system" ? "" : t)
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        AppDelegate.setTheme(AppDelegate.theme)
        buildMenu()
        main = MainWindow(engine: engine)
        main.showWindow(nil)
        NSApp.activate(ignoringOtherApps: true)
        engine.onExit = { [weak self] in self?.engineDied() }
        engine.start { port in
            if let p = port {
                self.main.load(port: p)
                self.autoCheckUpdates()
            } else { self.engineDied() }
        }
        if let shots = ProcessInfo.processInfo.environment["PROVINO_SHOTS"] { Shots.run(app: self, dir: shots) }
    }

    func engineDied() {
        guard let w = main.window else { return }
        let a = NSAlert()
        a.messageText = engine.proc == nil ? T("noPython") : T("crash")
        a.addButton(withTitle: T("openLog"))
        a.addButton(withTitle: T("quit"))
        a.beginSheetModal(for: w) { r in
            if r == .alertFirstButtonReturn { NSWorkspace.shared.open(DATA.appendingPathComponent("log")) }
            NSApp.terminate(nil)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ s: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ n: Notification) { engine.stop() }

    func buildMenu() {
        let bar = NSMenu()
        @discardableResult func sub(_ title: String, _ items: [NSMenuItem]) -> NSMenu {
            let m = NSMenu(title: title)
            items.forEach { m.addItem($0) }
            let i = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            i.submenu = m
            bar.addItem(i)
            return m
        }
        func it(_ t: String, _ a: Selector?, _ k: String = "", _ mods: NSEvent.ModifierFlags = .command, target: AnyObject? = nil, tag: Int = 0) -> NSMenuItem {
            let i = NSMenuItem(title: t, action: a, keyEquivalent: k)
            i.keyEquivalentModifierMask = mods
            i.target = target
            i.tag = tag
            return i
        }
        let sep = { NSMenuItem.separator() }
        sub("Provino", [
            it(T("about"), #selector(about), target: self),
            it(T("checkUpd"), #selector(checkUpdatesMenu), target: self), sep(),
            it(T("settings"), #selector(openSettings), ",", target: self), sep(),
            it(T("hide"), #selector(NSApplication.hide(_:)), "h"),
            it(T("hideOthers"), #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            it(T("showAll"), #selector(NSApplication.unhideAllApplications(_:))), sep(),
            it(T("quit"), #selector(NSApplication.terminate(_:)), "q"),
        ])
        sub(T("file"), [
            it(T("download"), #selector(download), "\r", target: self),
            it(T("change"), #selector(changeCamera(_:)), "k", [.command, .shift], target: self), sep(),
            it(T("pdfMenu"), #selector(makePdf), "p", target: self),
            it(T("pdfRead"), #selector(readPdfMenu), "o", [.command, .option], target: self), sep(),
            it(T("openFolder"), #selector(openFolder), "o", [.command, .shift], target: self),
        ])
        sub(T("edit"), [
            it(T("undo"), Selector(("undo:")), "z"), sep(),
            it(T("cut"), #selector(NSText.cut(_:)), "x"),
            it(T("copy"), #selector(NSText.copy(_:)), "c"),
            it(T("paste"), #selector(NSText.paste(_:)), "v"), sep(),
            it(T("selectAll"), #selector(selectAll), "a", target: self),
            it(T("deselect"), #selector(deselect), "d", target: self),
        ])
        var view: [NSMenuItem] = []
        for (i, (k, lab)) in [("both", T("all")), ("JPG", "JPG"), ("RAF", "RAF"), ("HIF", "HEIF"), ("VIDEO", T("video"))].enumerated() {
            let m = it(lab, #selector(showFilter(_:)), "\(i + 1)", target: self, tag: i)
            m.representedObject = k
            view.append(m)
        }
        view += [sep(), it(T("panelOn"), #selector(togglePanel), "i", [.command, .option], target: self), sep(),
                 it(T("fullscreen"), #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control])]
        sub(T("view"), view)
        let wm = sub(T("window"), [
            it(T("minimize"), #selector(NSWindow.performMiniaturize(_:)), "m"),
            it(T("zoom"), #selector(NSWindow.performZoom(_:))), sep(),
            it(T("front"), #selector(NSApplication.arrangeInFront(_:))),
        ])
        NSApp.windowsMenu = wm
        let hm = sub(T("help"), [
            it(T("guide"), #selector(guide), "?", target: self),
            it(T("issues"), #selector(issues), target: self),
        ])
        NSApp.helpMenu = hm
        NSApp.mainMenu = bar
    }

    // MARK: aggiornamenti (chiede a GitHub l'ultima versione pubblicata; scaricare resta una scelta tua)
    @objc func checkUpdatesMenu() { checkUpdates(manual: true) }

    func autoCheckUpdates() {
        let d = UserDefaults.standard
        if d.object(forKey: "autoUpdate") != nil && !d.bool(forKey: "autoUpdate") { return }
        let last = d.double(forKey: "lastUpdateCheck")
        if Date().timeIntervalSince1970 - last < 20 * 3600 { return }   // al massimo una volta al giorno
        DispatchQueue.main.asyncAfter(deadline: .now() + 4) { self.checkUpdates(manual: false) }
    }

    func checkUpdates(manual: Bool) {
        // prova: Opzione + «Controlla aggiornamenti…» ripropone l'ultima versione anche se e' gia' installata
        let force = manual && NSEvent.modifierFlags.contains(.option)
        engine.get("/api/update?mac&lang=\(LANG)" + (force ? "&force" : "")) { r in
            UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: "lastUpdateCheck")
            let ok = (r["ok"] as? Bool) ?? false
            let newer = (r["newer"] as? Bool) ?? false
            let cur = (r["current"] as? String) ?? ""
            if !ok { if manual { self.alert(T("updErr"), T("updErrInfo")) }; return }
            if !newer { if manual { self.alert(T("updNone"), T("updNoneInfo", ["c": cur])) }; return }
            let latest = (r["latest"] as? String) ?? ""
            if !manual && UserDefaults.standard.string(forKey: "skipVersion") == latest { return }
            let a = NSAlert()
            a.messageText = T("updNew", ["v": latest])
            var info = T("updInfo", ["c": cur])
            if let n = r["notes"] as? String, !n.isEmpty { info += "\n\n" + n }
            a.informativeText = info
            a.addButton(withTitle: T("updGet"))
            a.addButton(withTitle: T("updLater"))
            let go = { (resp: NSApplication.ModalResponse) in
                if resp == .alertFirstButtonReturn {
                    let page = (r["url"] as? String) ?? "https://github.com/cisla66/Provino/releases"
                    if (r["download"] as? String) != nil, SelfUpdate.possible {
                        // l'avviso si chiude prima che si apra il foglio dell'avanzamento
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                            self.updater = SelfUpdate(app: self, version: latest, page: page, force: force)
                            self.updater?.start()
                        }
                    } else if let url = URL(string: (r["download"] as? String) ?? page) { NSWorkspace.shared.open(url) }
                } else if !manual {
                    UserDefaults.standard.set(latest, forKey: "skipVersion")   // non lo ripropongo a ogni avvio
                }
            }
            if let w = self.main.window { a.beginSheetModal(for: w, completionHandler: go) } else { go(a.runModal()) }
        }
    }

    var updater: SelfUpdate?

    func alert(_ title: String, _ info: String) {
        let a = NSAlert()
        a.messageText = title
        a.informativeText = info
        if let w = main.window { a.beginSheetModal(for: w, completionHandler: nil) } else { a.runModal() }
    }

    @objc func about() {
        let credits = NSAttributedString(string: "Marco Cislaghi\n" + T("comments"),
                                         attributes: [.font: NSFont.systemFont(ofSize: 11), .foregroundColor: NSColor.secondaryLabelColor])
        NSApp.orderFrontStandardAboutPanel(options: [.credits: credits, .applicationName: "Provino"])
    }
    @objc func openSettings() {
        if settings == nil { settings = SettingsWindow(mainWin: main) } else { settings?.load() }
        settings?.window?.center()
        settings?.showWindow(nil)
    }
    @objc func download() { main.js("download") }
    @objc func changeCamera(_ s: Any?) { main.js("change") }
    @objc func openFolder() { main.js("openFolder") }
    @objc func makePdf() { main.js("pdf") }
    @objc func readPdfMenu() { main.readPdf() }
    @objc func selectAll() {
        if let r = NSApp.keyWindow?.firstResponder, r is NSTextView { NSApp.sendAction(#selector(NSText.selectAll(_:)), to: nil, from: nil); return }
        main.js("select", "visible")
    }
    @objc func deselect() { main.js("select", "none") }
    @objc func showFilter(_ s: NSMenuItem) { main.js("filter", s.representedObject as? String ?? "both") }
    @objc func togglePanel() { main.js("split") }
    @objc func guide() { NSWorkspace.shared.open(URL(string: "https://github.com/cisla66/Provino#readme")!) }
    @objc func issues() { NSWorkspace.shared.open(URL(string: "https://github.com/cisla66/Provino/issues")!) }
}

// MARK: - schermate automatiche (solo per le prove: PROVINO_SHOTS=cartella)

enum Shots {
    static func run(app: AppDelegate, dir: String) {
        try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        var steps: [(Double, () -> Void)] = []
        func at(_ t: Double, _ f: @escaping () -> Void) { steps.append((t, f)) }
        let m = { app.main! }
        func shot(_ name: String) {
            guard let w = m().window else { return }
            snap(w, to: dir + "/" + name + ".png")
            print("shot", name)
        }
        func js(_ code: String) { m().web.evaluateJavaScript(code, completionHandler: nil) }
        if let t = ProcessInfo.processInfo.environment["PROVINO_THEME"] { at(0.5) { AppDelegate.setTheme(t) } }
        at(6) { shot("01-scelta") }
        at(7) { js("document.querySelector('[data-cam=\"Fujifilm\"]').click()") }
        at(8) { shot("02-scelta-lettore") }
        at(9) { js("document.querySelector('#wizGo').click()") }
        at(17) { shot("03-griglia") }
        at(17.5) { js("const k=[...document.querySelectorAll('.kind:not(.meta)')]; k[0]&&k[0].click(); k[3]&&k[3].click(); k[5]&&k[5].click();") }
        at(18) { js("document.querySelectorAll('.frame .photo')[2].click()") }
        at(21) { shot("04-foto-grande") }
        at(22) { js("document.querySelector('#vmetaBtn').click()") }
        at(25) { shot("05-foto-e-meta") }
        at(26) { js("document.querySelector('#vmetaBtn').click()"); m().js("split") }
        at(27) { shot("06-griglia-scelte") }
        at(28) { m().js("download") }
        at(30) { shot("07-foglio-scarica") }
        at(31) { m().destSheet?.onGo() }
        at(36) { shot("08-scaricati") }
        at(37) { m().trPopover?.close() }
        at(38) { // un file cambiato per avere anche il caso "foto diversa"
            if let e = FileManager.default.enumerator(atPath: ProcessInfo.processInfo.environment["PROVINO_DEST"] ?? "") {
                for case let f as String in e where f.uppercased().hasSuffix(".JPG") {
                    let p = (ProcessInfo.processInfo.environment["PROVINO_DEST"] ?? "") + "/" + f
                    if let h = FileHandle(forWritingAtPath: p) { h.seekToEndOfFile(); h.write(Data(repeating: 120, count: 100)); h.closeFile() }
                    break
                }
            }
            m().js("select", "visible")
        }
        at(39) { m().js("download") }
        at(41) { m().destSheet?.onGo() }
        at(43) { shot("09-foglio-gia-presenti") }
        at(44) { m().confSheet?.onOk() }
        at(44.4) { shot("10-avanzamento") }
        at(49) { shot("11-finito") }
        at(50) { m().trPopover?.close(); app.openSettings() }
        at(52) { if let w = app.settings?.window { snap(w, to: dir + "/12-impostazioni.png"); print("shot 12") } }
        at(53) { app.settings?.close(); app.about() }
        at(55) {
            if let w = NSApp.windows.first(where: { $0.isVisible && $0 !== m().window && $0 !== app.settings?.window }) {
                snap(w, to: dir + "/13-informazioni.png"); print("shot 13")
            }
        }
        at(56) { snapScreen(to: dir + "/14-schermo.png") }
        at(58) { NSApp.terminate(nil) }
        for (t, f) in steps { DispatchQueue.main.asyncAfter(deadline: .now() + t, execute: f) }
    }

    // CGWindowListCreateImage non e' piu' nell'SDK di macOS 15: la chiamo per nome (solo prove)
    typealias CreateImage = @convention(c) (CGRect, UInt32, UInt32, UInt32) -> Unmanaged<CGImage>?
    static let create: CreateImage? = {
        guard let h = dlopen(nil, RTLD_NOW), let s = dlsym(h, "CGWindowListCreateImage") else { return nil }
        return unsafeBitCast(s, to: CreateImage.self)
    }()

    static func snap(_ w: NSWindow, to path: String) {
        guard let f = create, let screen = w.screen ?? NSScreen.main else { return }
        // finestra + fogli + riquadri: tutto quello che c'e' sullo schermo nel suo rettangolo (le nostre finestre si vedono sempre)
        var r = w.frame.insetBy(dx: -30, dy: -30)
        let h = screen.frame.height
        r.origin.y = h - r.origin.y - r.height
        guard let img = f(r, 1 /* onScreenOnly */, 0, 0)?.takeRetainedValue() else { print("snap failed"); return }
        write(img, path)
    }

    static func snapScreen(to path: String) {
        guard let f = create, let s = NSScreen.main else { return }
        guard let img = f(s.frame, 1, 0, 0)?.takeRetainedValue() else { return }
        write(img, path)
    }

    static func write(_ img: CGImage, _ path: String) {
        let rep = NSBitmapImageRep(cgImage: img)
        try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: path))
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()

/// Icona "cambia fotocamera" di Provino: fotocamera con due frecce di rotazione ai lati (disegnata, immagine modello).
func cameraSwitchImage(label: String? = nil) -> NSImage {
    let lines: [[(CGFloat, CGFloat)]] = [
[(5.25,16.03), (4.83,15.54), (4.45,15.02), (4.10,14.49), (3.78,13.93), (3.50,13.35), (3.25,12.76), (3.04,12.16), (2.86,11.54), (2.73,10.91), (2.63,10.28), (2.57,9.64), (2.55,9.00), (2.57,8.36), (2.63,7.72), (2.73,7.09), (2.86,6.46), (3.04,5.84), (3.25,5.24), (3.50,4.65), (3.78,4.07), (4.10,3.51), (4.45,2.98), (4.83,2.46), (5.25,1.97)],
[(5.25,1.97), (2.76,2.53)],
[(5.25,1.97), (4.96,4.51)],
[(20.85,1.97), (21.27,2.46), (21.65,2.98), (22.00,3.51), (22.32,4.07), (22.60,4.65), (22.85,5.24), (23.06,5.84), (23.24,6.46), (23.37,7.09), (23.47,7.72), (23.53,8.36), (23.55,9.00), (23.53,9.64), (23.47,10.28), (23.37,10.91), (23.24,11.54), (23.06,12.16), (22.85,12.76), (22.60,13.35), (22.32,13.93), (22.00,14.49), (21.65,15.02), (21.27,15.54), (20.85,16.03)],
[(20.85,16.03), (23.34,15.47)],
[(20.85,16.03), (21.14,13.49)],
[(8.18,5.70), (10.12,5.70), (11.18,4.20), (14.92,4.20), (15.97,5.70), (17.92,5.70), (18.60,6.38), (18.60,11.93), (17.92,12.60), (8.18,12.60), (7.50,11.93), (7.50,6.38), (8.18,5.70)],
[(15.07,9.00), (15.06,9.26), (15.01,9.52), (14.92,9.77), (14.80,10.01), (14.66,10.23), (14.48,10.43), (14.28,10.61), (14.06,10.75), (13.82,10.87), (13.57,10.96), (13.31,11.01), (13.05,11.03), (12.79,11.01), (12.53,10.96), (12.28,10.87), (12.04,10.75), (11.82,10.61), (11.62,10.43), (11.44,10.23), (11.30,10.01), (11.18,9.77), (11.09,9.52), (11.04,9.26), (11.03,9.00), (11.04,8.74), (11.09,8.48), (11.18,8.23), (11.30,7.99), (11.44,7.77), (11.62,7.57), (11.82,7.39), (12.04,7.25), (12.28,7.13), (12.53,7.04), (12.79,6.99), (13.05,6.97), (13.31,6.99), (13.57,7.04), (13.82,7.13), (14.06,7.25), (14.28,7.39), (14.48,7.57), (14.66,7.77), (14.80,7.99), (14.92,8.23), (15.01,8.48), (15.06,8.74), (15.07,9.00)]
]
    let font = NSFont.systemFont(ofSize: NSFont.systemFontSize)
    let text = label.map { NSAttributedString(string: $0, attributes: [.font: font, .foregroundColor: NSColor.black]) }
    let tw = text.map { ceil($0.size().width) + 6 } ?? 0
    let img = NSImage(size: NSSize(width: 26 + tw, height: 18), flipped: true) { _ in
        NSColor.black.setStroke()
        for l in lines {
            let p = NSBezierPath()
            p.lineWidth = 1.35; p.lineCapStyle = .round; p.lineJoinStyle = .round
            p.move(to: NSPoint(x: l[0].0, y: l[0].1))
            for q in l.dropFirst() { p.line(to: NSPoint(x: q.0, y: q.1)) }
            p.stroke()
        }
        if let t = text { t.draw(at: NSPoint(x: 32, y: (18 - t.size().height) / 2)) }
        return true
    }
    img.isTemplate = true
    img.accessibilityDescription = T("camera")
    return img
}
