# Recherche: MAENTUM-Kühlboxen per Bluetooth an Home Assistant

Stand: 25.09.2026. Jede Aussage ist einer Quelle zugeordnet und nach Belastbarkeit eingestuft.

| Stufe | Bedeutung |
|---|---|
| **belegt** | steht so in Quellcode oder Mitschnitt einer Quelle |
| **berichtet** | Nutzerbericht, nicht selbst nachgeprüft |
| **abgeleitet** | eigene Schlussfolgerung aus belegten Daten |
| **unbekannt** | keine verlässliche Quelle gefunden |

## 1. Hersteller und Modelle

| Aussage | Stufe | Quelle |
|---|---|---|
| Plug-In Festivals heißt jetzt MAENTUM | belegt | [maentum.de](https://maentum.de/) |
| Aktuelle Kühlboxen: IceCube (40 L), IceCube DUAL (zwei Zonen), IceCube X (50 L) | belegt | [maentum.de Kühlboxen-Vergleich](https://maentum.de/pages/kuehlboxen-vergleich) |
| Die IceCubeX lässt sich per Bluetooth über die „MAENTUM App“ steuern (Temperatur, minimale Spannung) | belegt | [techtest.org Test der IceCubeX](https://techtest.org/maentum-icecubex-die-effizienteste-kompressor-kuehlbox-im-test/) |
| Die App „MAENTUM IceCubeX“ stammt von der Plug-in Festivals GmbH, Paket `com.maentum`, v1.0 vom 11.11.2024, v1.0.4 vom 16.09.2025 | belegt | [App Store](https://apps.apple.com/de/app/maentum-icecubex/id6737261611), [Google Play](https://play.google.com/store/apps/details?id=com.maentum) |
| Die IceCubeX spricht das Alpicool-Protokoll: Name `A1-…`, Dienst 0x1234 mit 0x1235 (Write Without Response) und 0x1236 (Notify); Query `FEFE03010200` wird mit einem 48-Byte-Statusrahmen beantwortet (Prüfsumme korrekt) | **belegt an einem Gerät** | eigener Test mit nRF Connect an einer ICECUBE X 50, 25.09.2026 (Abschnitt 5) |

## 2. Hinweise, dass (ältere) Plug-In-Festivals-Boxen das Alpicool-Protokoll sprechen

| Aussage | Stufe | Quelle |
|---|---|---|
| Pekaway-Forum: Nutzer „moe.camp“ vermutet dasselbe Protokoll wie Alpicool/Vevor, empfiehlt Test mit der App „Car Fridge Freezer“ und nutzt ein MQTT-Bridge-Skript auf Basis von BrassMonkeyFridgeMonitor. Er berichtet, dass die Bluetooth-Verbindung „öfter mal stirbt“ (per systemd-Neustart abgefangen). Genaues Modell wird nicht genannt. | berichtet | [Pekaway-Forum, Thread 2302](https://forum.pekaway.de/t/maentum-pluginfestival-kuhlboxen-per-bluetooth-einbinden-und-steuern/2302) |
| smarthomeundmore.de bindet eine ältere Plug-In-Festivals-Box per ESPHome mit der Komponente `neftaly/esphome-alpicool` ein; Dual-Zone laut Autor noch ungetestet | berichtet | [smarthomeundmore.de](https://smarthomeundmore.de/home-assistant-kuehlbox-smart-bluetooth-esphome/) |

Hinweis: Das Pekaway-Forum war aus der Recherche-Umgebung nur über eine Zusammenfassung lesbar, nicht im Wortlaut. Die Angaben oben stammen aus gezielten Rückfragen an diese Zusammenfassung.

**Fazit (abgeleitet):** Für ältere Plug-In-Festivals-Boxen gibt es zwei unabhängige Nutzerberichte für das Alpicool-Protokoll. Für die IceCubeX gibt es keinen. Das Prüfskript `tools/maentum_probe.py` klärt das in einer Minute am Gerät.

## 3. Das Protokoll

Vollständig in [PROTOKOLL.md](PROTOKOLL.md). Hauptquellen:

| Quelle | Lizenz | Inhalt |
|---|---|---|
| [klightspeed/BrassMonkeyFridgeMonitor](https://github.com/klightspeed/BrassMonkeyFridgeMonitor) | MIT | Rekonstruiert aus Mitschnitt und JavaScript der Alpicool-App „CAR FRIDGE FREEZER“ v2.0.0. UUIDs, Rahmenformat, Befehle, Feldtabellen, Mitschnitte |
| [neftaly/esphome-alpicool](https://github.com/neftaly/esphome-alpicool) `docs/protocol.md` | keine Lizenzdatei | Testvektoren, Fragmentierung, abweichende Prüfsummen bei einem A1-4X |
| [Gruni22/alpicool_ha_ble](https://github.com/Gruni22/alpicool_ha_ble) | keine Lizenzdatei | Praxis: SET-Echo und Status kommen in einer Notification, Write mit Response nötig |

## 4. Bestehende Projekte

| Projekt | Art | Stand | Lizenz | Bewertung |
|---|---|---|---|---|
| [Gruni22/alpicool_ha_ble](https://github.com/Gruni22/alpicool_ha_ble) | HACS-Integration | aktiv, letzter Commit 25.09.2026, 52 Commits | **keine** | vollständigste HA-Lösung, siehe [Review](REVIEW_alpicool_ha_ble.md) |
| [neftaly/esphome-alpicool](https://github.com/neftaly/esphome-alpicool) | ESPHome-Komponente | letzter Commit 24.02.2026 | **keine** | Klima, Sensoren, Schalter, Selects; getestet an CX40 |
| [klightspeed/BrassMonkeyFridgeMonitor](https://github.com/klightspeed/BrassMonkeyFridgeMonitor) | Python-CLI + MQTT | letzter Commit 12.07.2026 | MIT | Referenz für das Protokoll |
| [jakub-hajek/alpicool-esp32-mqtt](https://github.com/jakub-hajek/alpicool-esp32-mqtt) | ESP32 → MQTT (PlatformIO) | letzter Commit 01.08.2025 | MIT | Alternative ohne ESPHome |
| [johnelliott/alpicoold](https://github.com/johnelliott/alpicoold) | Go, HomeKit | 2021 | nicht geprüft | älteres Projekt |
| [danfulton72/amps_fridge_ble_ha](https://github.com/danfulton72/amps_fridge_ble_ha) | HA-Komponente (AMPS) | nicht geprüft | nicht geprüft | nur gefunden, nicht ausgewertet |
| [esphome/feature-requests #1375](https://github.com/esphome/feature-requests/issues/1375) | Feature-Wunsch | offen | – | keine offizielle ESPHome-Unterstützung |

## 5. Was offen ist

1. **Protokoll der IceCubeX** (Sebastians Modell): **geklärt** am 25.09.2026 mit nRF Connect. Antwort auf Query (drei Notifications, 20 + 20 + 8 Byte):
   ```
   FEFE2D01000101020414EC020000FDFD00000564
   0E06000000000000000080000A00000000000000
   0000000000000635
   ```
   Entschlüsselt: an, Sperre aus, Eco, Batterieschutz hoch, Soll 4 °C, Ist 5 °C, Bereich −20..20 °C, Hysterese 2, °C, Akku 100 %, 14,6 V. Nutzdaten sind 42 statt 18/28 Byte; die Temperatur der zweiten Zone ist 0x80 (−128), *abgeleitet*: keine zweite Zone. Die Bytes 28–41 sind unbekannt. Offen: ob SET (Sollwert setzen) wie bei Alpicool funktioniert.
2. Gültige Wertebereiche für Hysterese und Startverzögerung: in keiner Quelle dokumentiert.
3. Bedeutung des Bytes `running_status` (Dual-Zone, Offset 0x1B): laut BrassMonkey unbekannt.
4. Zweck der zusätzlichen Characteristic `0xFFF1`: laut neftaly unbekannt; das Abonnieren kann bei manchen Firmwares die Verbindung trennen.
