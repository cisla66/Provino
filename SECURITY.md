# Sicurezza / Security

## Italiano

### Come Provino protegge le tue foto
- **Sola lettura sulla fotocamera e sulla scheda.** Provino non cancella, non modifica e non formatta mai nulla. Usa solo comandi di lettura (PTP/IP via Wi-Fi, PTP via cavo, file system della scheda).
- **Nessun file sovrascritto senza chiedere.** Se una foto esiste già nella cartella di destinazione, Provino chiede cosa fare.
- **Niente rete esterna.** L'interfaccia parla solo con un piccolo server locale su `127.0.0.1`, che rifiuta le richieste con un `Host` o un'`Origin` diversi da `127.0.0.1`/`localhost` (contro gli attacchi dal browser e il DNS rebinding). L'unica connessione verso internet è il controllo degli aggiornamenti su GitHub, che si può disattivare.
- **Wi-Fi.** Durante l'attesa della fotocamera Provino ascolta sulla rete locale le porte del protocollo Fujifilm (TCP 51541 e 51542, UDP 51541, 51542 e 51562), poi le chiude.
- **Nomi dei file ripuliti.** I nomi che arrivano dalla fotocamera o dalla scheda perdono percorsi, `..` e punti iniziali prima di essere salvati.
- **Testi mai interpretati come codice.** Nomi, metadati e messaggi di errore vengono mostrati come testo, non come HTML.
- **Python incluso nell'app per Mac** da [python-build-standalone](https://github.com/astral-sh/python-build-standalone), scaricato al momento della costruzione e controllato con l'impronta SHA-256 pubblicata dal progetto.

### Controlli fatti per la 1.0 (novembre 2026)
- Analisi statica del codice (bandit, semgrep con le regole Python e JavaScript): nessun problema aperto; le segnalazioni rimaste sono attese (per esempio l'ascolto sulla rete locale per il Wi-Fi della fotocamera).
- Fuzzing dei lettori di metadati e di file (EXIF, MakerNote Fujifilm, RAF, HEIF, JPEG e lettura delle scelte dai PDF): 6000 foto e 3000 PDF alterati, nessun blocco.
- Prove sul server locale: richieste da altre origini rifiutate.
- Cronologia del repository controllata: nessuna foto personale, numero di serie o credenziale.

### Limiti noti
- L'app per Mac non è firmata né notarizzata da Apple: al primo avvio macOS chiede di confermare («Apri comunque») e, dopo ogni aggiornamento, chiede di nuovo il permesso per le schede.
- L'AppImage non è firmato: scaricalo solo dalla [pagina dei rilasci](https://github.com/cisla66/Provino/releases).

### Segnalare un problema di sicurezza
Usa **Report a vulnerability** nella scheda *Security* del repository, oppure apri una issue senza dettagli tecnici e ti contatterò.

## English

### How Provino keeps your photos safe
- **Read-only on the camera and the card.** Provino never deletes, modifies or formats anything. It only uses read commands (PTP/IP over Wi-Fi, PTP over cable, the card's file system).
- **No file is overwritten without asking.**
- **No outside network.** The interface only talks to a small local server on `127.0.0.1`, which rejects requests whose `Host` or `Origin` is not `127.0.0.1`/`localhost` (against browser attacks and DNS rebinding). The only internet connection is the update check on GitHub, which can be turned off.
- **Wi-Fi.** While waiting for the camera, Provino listens on the local network on the Fujifilm protocol ports (TCP 51541 and 51542, UDP 51541, 51542 and 51562), then closes them.
- **Sanitized file names** and **text never rendered as code** (names, metadata and error messages are shown as text, never as HTML).
- **Bundled Python on Mac** from python-build-standalone, verified against the project's published SHA-256 hashes at build time.

### Checks done for 1.0 (November 2026)
Static analysis (bandit, semgrep Python and JavaScript rules), fuzzing of the metadata and file parsers (6000 mutated photos and 3000 mutated PDFs, no crashes), local-server origin tests, repository history review (no personal photos, serial numbers or credentials).

### Known limits
The Mac app is not signed or notarized by Apple; the AppImage is not signed. Download only from the releases page.

### Reporting a security issue
Use **Report a vulnerability** in the repository's *Security* tab, or open an issue without technical details and I'll get in touch.
