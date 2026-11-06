# Provino

**Scegli dal computer le foto della tua Fujifilm X-Pro3 o X100VI e scarica solo quelle.**
Via Wi-Fi o con il cavo USB, su Mac e Linux. Provino legge soltanto: non tocca mai la scheda.

**Pick photos from your Fujifilm X-Pro3 or X100VI on your computer and download only those.**
Over Wi-Fi or USB cable, on Mac and Linux. Provino is read-only: it never touches your card.

> Progetto indipendente, non affiliato a FUJIFILM Corporation.
> Independent project, not affiliated with FUJIFILM Corporation.

**Stato / Status:** versione di prova `1.0.0-rc`, la 1.0 arriverà come app da installare (`.dmg` per Mac, AppImage per Linux).
Release candidate `1.0.0-rc`; 1.0 will ship as installable apps (`.dmg` for Mac, AppImage for Linux).

[Italiano](#italiano) · [English](#english)

---

## Italiano

### Cosa fa
- Miniature di tutti gli scatti, con RAW+JPG raggruppati in un solo provino.
- Scegli con le etichette **JPG** / **RAF**, Maiusc+clic, riquadro o «Tutti i …».
- Filtri per tipo di file e per simulazione pellicola.
- Foto grande accanto alla griglia o a tutto schermo, zoom al 100%.
- Pannello **META**: la ricetta completa (pellicola, grana, Color Chrome, bilanciamento del bianco, gamma dinamica…) e i dati di scatto; «Copia ricetta» la copia come testo.
- Download in cartelle per data e/o per tipo (RAF, JPG, VIDEO).
- Se un file c'è già, chiede cosa fare. Se il collegamento cade, nessun file resta a metà e quelli mancanti tornano selezionati.

### Collegamenti
| | X-Pro3 | X100VI | Cosa vedi |
|---|---|---|---|
| **Cavo USB** | sì | sì | JPG, RAF e video, entrambe le schede |
| **Wi-Fi di casa** | sì | no | JPG e RAF |
| **Wi-Fi diretto** | sì | no | solo JPG, solo scheda 1 (limite della fotocamera) |

**Cavo:** sulla fotocamera imposta prima la modalità LETTORE SCHEDA USB, poi collega il cavo. Sulla X100VI l'alimentazione USB va su AUTO.
**Wi-Fi di casa**, la prima volta: MENU/OK › chiave › IMPOSTAZIONI CONNESSIONE › IMP. SALV.AUT. PC › IMPOSTAZIONE MANUALE › SELEZ. LISTA RETI. Provino registra il computer da solo. Per scaricare: PLAY › MENU/OK › menu riproduzione › SALVAT. AUTOM. PC.
**Wi-Fi diretto:** PLAY › MENU/OK › COMUNIC. WIRELESS, poi collega il computer alla rete `FUJIFILM-…`.

### Avvio (versione di prova)
Serve Python 3, senza pacchetti aggiuntivi.

**Mac:** doppio clic su `Provino.command`; si apre il browser. Per il cavo servono gli strumenti da riga di comando di Apple (`xcode-select --install`).
**Linux:** in un terminale nella cartella, `sh avvia-linux.sh` (nel browser) oppure `python3 provino_finestra.py` (finestra GNOME). Il cavo usa libgphoto2, già presente nei desktop GNOME; la finestra usa GTK 4, WebKitGTK 6 e libadwaita.

### Sicurezza
Provino non cancella, non modifica e non formatta mai nulla sulla scheda. Non sovrascrive file sul computer senza chiederlo. Nella cartella `log` c'è un file per ogni avvio, utile se qualcosa non va.

---

## English

### What it does
- Thumbnails of every shot, RAW+JPG grouped into a single frame.
- Pick with the **JPG** / **RAF** labels, Shift+click, drag box or "All …".
- Filters by file type and by film simulation.
- Large photo next to the grid or full screen, 100% zoom.
- **META** panel: the full recipe (film, grain, Color Chrome, white balance, dynamic range…) and shooting data; "Copy recipe" copies it as text.
- Downloads into folders by date and/or type (RAF, JPG, VIDEO).
- Asks what to do when a file already exists. If the connection drops, no half-written files are left and the missing ones are selected again.

### Connections
| | X-Pro3 | X100VI | What you see |
|---|---|---|---|
| **USB cable** | yes | yes | JPG, RAF and video, both cards |
| **Home Wi-Fi** | yes | no | JPG and RAF |
| **Direct Wi-Fi** | yes | no | JPG only, card 1 only (camera limit) |

**Cable:** on the camera set USB CARD READER mode first, then plug in the cable. On the X100VI set USB power supply to AUTO.
**Home Wi-Fi**, first time: MENU/OK › wrench › CONNECTION SETTING › PC AUTO SAVE SETTING › MANUAL SETUP › SELECT FROM NETWORK LIST. Provino registers the computer by itself. To download: PLAY › MENU/OK › playback menu › PC AUTO SAVE.
**Direct Wi-Fi:** PLAY › MENU/OK › WIRELESS COMMUNICATION, then join the `FUJIFILM-…` network.

### Running (release candidate)
Needs Python 3, no extra packages.

**Mac:** double-click `Provino.command`; your browser opens. The cable needs Apple's command line tools (`xcode-select --install`).
**Linux:** in a terminal in the folder, `sh avvia-linux.sh` (in the browser) or `python3 provino_finestra.py` (GNOME window). The cable uses libgphoto2, already present on GNOME desktops; the window uses GTK 4, WebKitGTK 6 and libadwaita.

### Safety
Provino never deletes, changes or formats anything on the card. It never overwrites files on your computer without asking. The `log` folder has one file per run, useful if something goes wrong.

---

Protocollo Wi-Fi basato sul lavoro open source di [libfuji](https://github.com/petabyt/libfuji) (petabyt), licenza MIT.
Wi-Fi protocol based on the open-source work of [libfuji](https://github.com/petabyt/libfuji) (petabyt), MIT license.

Licenza / License: [MIT](LICENSE)
