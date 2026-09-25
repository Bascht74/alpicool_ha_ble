# MAENTUM-Kühlboxen mit dieser Integration

Anleitung, Recherche und Werkzeuge, um MAENTUM-Kühlboxen (früher „Plug In Festivals“) per Bluetooth Low Energy in Home Assistant einzubinden.

> **Stand 25.09.2026, bitte lesen:** Für ältere Plug-In-Festivals-Boxen gibt es Nutzerberichte, dass sie das offene **Alpicool-Protokoll** sprechen. Für die **IceCube X 50** ist es seit dem 25.09.2026 an einem Gerät belegt: Sie bietet Dienst 0x1234 an und beantwortet die Statusabfrage im Alpicool-Format (siehe [RECHERCHE.md](RECHERCHE.md), Abschnitt 5). Auch das Setzen der Solltemperatur (Befehl 0x05) funktioniert. Die übrigen Einstellungen (Befehl 0x02) sind noch nicht an der Box getestet. Andere Modelle prüfst du zuerst mit Schritt 1. Nicht mit MAENTUM verbunden oder von MAENTUM unterstützt.

## Inhalt

| Pfad | Inhalt |
|---|---|
| [`tools/maentum_probe.py`](../../tools/maentum_probe.py) | Prüfskript: findet die Box, listet ihre GATT-Dienste, liest und decodiert den Status |
| [`tools/alpicool_protocol.py`](../../tools/alpicool_protocol.py) | Protokoll-Codec ohne Abhängigkeiten, getestet mit echten Mitschnitten |
| [`RECHERCHE.md`](RECHERCHE.md) | alle Quellen, jeweils mit Belastbarkeit (belegt / berichtet / unbekannt) |
| [`PROTOKOLL.md`](PROTOKOLL.md) | das Protokoll mit Quellenangabe je Detail |
| [`VERGLEICH_HACS_ESPHOME.md`](VERGLEICH_HACS_ESPHOME.md) | Vor- und Nachteile HACS-Integration vs. ESPHome |
| [`REVIEW_alpicool_ha_ble.md`](REVIEW_alpicool_ha_ble.md) | Code-Review dieser Integration mit Verbesserungsvorschlägen |
| [`esphome/kuehlbox.yaml`](esphome/kuehlbox.yaml) | Beispielkonfiguration für den ESPHome-Weg |

## Schritt 1: Spricht meine Box das Alpicool-Protokoll?

**Variante A, ohne Computer (1 Minute):**

1. MAENTUM-App auf dem Handy schließen (die Box erlaubt nur **eine** Verbindung).
2. App **nRF Connect for Mobile** (Nordic Semiconductor) installieren und scannen.
3. Die Box in der Liste suchen (direkt daneben stehen, nach Signalstärke filtern; oder Box kurz ausschalten und schauen, welches Gerät verschwindet), Namen notieren, **Connect** tippen. Android zeigt auch die MAC-Adresse, das iPhone nicht.
4. Taucht ein Dienst **`0x1234`** mit den Characteristics **`0x1235`** und **`0x1236`** auf, spricht die Box das Protokoll. Weiter mit Schritt 2.

**Variante B, mit dem Prüfskript** (Linux, macOS oder Windows mit Bluetooth, Python ≥ 3.11):

```bash
git clone https://github.com/Bascht74/alpicool_ha_ble.git && cd alpicool_ha_ble
python3 -m venv .venv && . .venv/bin/activate
pip install bleak

python tools/maentum_probe.py scan               # Boxen in der Nähe, bekannte mit „fridge?“
python tools/maentum_probe.py scan --all         # alle BLE-Geräte, falls der Name unbekannt ist
python tools/maentum_probe.py services AA:BB:CC:DD:EE:FF   # GATT-Dienste auflisten (nur lesen)
python tools/maentum_probe.py query AA:BB:CC:DD:EE:FF      # Status lesen und decodieren (nur lesen)
python tools/maentum_probe.py -v query AA:BB:CC:DD:EE:FF --loop 10   # mit Rohdaten, alle 10 s
```

`query` gibt den Status als JSON aus (Soll/Ist, Spannung, Modus …). Stimmen die Werte mit dem Display der Box überein, ist die Box kompatibel. `set-target --temp 4` ändert testweise die Solltemperatur; das ist der einzige schreibende Befehl und muss ausdrücklich aufgerufen werden.

**Wenn `0x1234` fehlt:** Die Box nutzt ein anderes Protokoll. Dann bitte die Ausgabe von `services` (oder einen Screenshot aus nRF Connect) in einem Issue posten. Für die weitere Analyse braucht es einen Bluetooth-Mitschnitt der MAENTUM-App (Android: Entwickleroptionen → „Bluetooth-HCI-Snoop-Protokoll aktivieren“).

## Schritt 2: Integration installieren

Voraussetzung: Home Assistant mit Bluetooth, entweder ein Adapter am HA-Rechner in Reichweite der Box oder ein [ESPHome-Bluetooth-Proxy](https://esphome.io/components/bluetooth_proxy/) in der Nähe der Box.

1. [HACS](https://hacs.xyz/) öffnen → Menü oben rechts → **Benutzerdefinierte Repositories**.
2. Repository `https://github.com/Gruni22/alpicool_ha_ble`, Typ **Integration**, hinzufügen.
3. „Alpicool BLE“ suchen, installieren, Home Assistant neu starten.
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen → „Alpicool BLE“**.
5. MAC-Adresse der Box aus Schritt 1 eintragen, Namen vergeben. Zeigt die Box „APP“ im Display, kurz die Taste an der Box drücken.

Danach gibt es eine Klima-Entität (Ein/Aus, Solltemperatur, Max/Eco), Sensoren für Akku und Spannung, eine Tastensperre, Batterieschutz sowie Hysterese und Startverzögerung.

## Bekannte Einschränkungen

- Solange Home Assistant verbunden ist, kann sich die Handy-App nicht verbinden, und umgekehrt (Eigenschaft der Box, BrassMonkeyFridgeMonitor).
- Im Pekaway-Forum wird von gelegentlichen Verbindungsabbrüchen berichtet. Ein Bluetooth-Proxy nahe der Box hilft meist.
- Offene Punkte der Integration stehen im [Review](REVIEW_alpicool_ha_ble.md), z. B. 127 % Akku bei Boxen ohne Akku-Messung.

## Fehlersuche

| Symptom | Ursache / Abhilfe |
|---|---|
| Box wird nicht gefunden | Handy-App schließen; Box ein; Abstand verringern; `scan --all` |
| `services` meldet „NOT present“ | anderes Protokoll, siehe Schritt 1 |
| `query` bekommt keine Antwort | Box aus- und einschalten; mit `--bind` versuchen und Taste an der Box drücken |
| Werte in HA veralten | Logs der Integration auf Debug stellen (`logger: logs: custom_components.alpicool_ble: debug`) |

## Tests des Prüfskripts

```bash
pip install -r requirements-test.txt
pytest -q tests/test_tools_protocol.py tests/test_tools_probe.py
```

## Quellen und Dank

- Protokoll: [klightspeed/BrassMonkeyFridgeMonitor](https://github.com/klightspeed/BrassMonkeyFridgeMonitor) (MIT)
- Testvektoren und Praxisdetails: [neftaly/esphome-alpicool](https://github.com/neftaly/esphome-alpicool)
- Home-Assistant-Integration: [Gruni22/alpicool_ha_ble](https://github.com/Gruni22/alpicool_ha_ble)
- Anlass: [Pekaway-Forum](https://forum.pekaway.de/t/maentum-pluginfestival-kuhlboxen-per-bluetooth-einbinden-und-steuern/2302), [smarthomeundmore.de](https://smarthomeundmore.de/home-assistant-kuehlbox-smart-bluetooth-esphome/)

Von den Projekten ohne Lizenzdatei wurde kein Code übernommen, nur dokumentierte Fakten, jeweils mit Quellenangabe.
