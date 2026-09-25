# HACS-Integration oder ESPHome?

Beide Wege sprechen dasselbe Protokoll mit der Box. Der Unterschied ist, **wer** die Bluetooth-Verbindung hält.

- **HACS-Integration** (z. B. [Gruni22/alpicool_ha_ble](https://github.com/Gruni22/alpicool_ha_ble)): Home Assistant verbindet sich selbst, über den eingebauten Bluetooth-Adapter oder über einen ESPHome-Bluetooth-Proxy.
- **ESPHome** (z. B. [neftaly/esphome-alpicool](https://github.com/neftaly/esphome-alpicool)): Ein ESP32 neben der Box verbindet sich und meldet die Werte per ESPHome-API oder WLAN an Home Assistant.

## Gegenüberstellung

| Kriterium | HACS-Integration | ESPHome-Firmware |
|---|---|---|
| Zusatz-Hardware | keine, wenn der HA-Rechner Bluetooth hat und in Reichweite ist; sonst ein ESP32 als Bluetooth-Proxy | ein ESP32 pro Box (oder mehrere Boxen an einem ESP32) |
| Reichweite | BLE-Reichweite zum HA-Rechner oder Proxy | ESP32 steht direkt an der Box, nur WLAN muss reichen |
| Einrichtung | HACS installieren, Integration hinzufügen, Box auswählen | YAML schreiben, ESP32 flashen, in HA übernehmen |
| Updates | über HACS mit einem Klick | ESP32 neu kompilieren und flashen |
| Logik und Fehlersuche | in Python, Logs und Diagnose direkt in HA | in C++, Logs im ESPHome-Dashboard |
| Stabilität der Verbindung | abhängig vom BLE-Stack des HA-Rechners; über Proxys etwas mehr Latenz | ESP32 hält eine Verbindung, typischerweise stabil; bei WLAN-Ausfall keine Daten |
| Camper ohne dauerhaft laufenden HA-Server | nur, wenn HA im Fahrzeug läuft | ESP32 kann unabhängig laufen, braucht aber Empfänger (HA oder MQTT) |
| Stromverbrauch im Fahrzeug | keiner zusätzlich | ESP32 zieht dauerhaft Strom (Größenordnung unter 1 W, nicht gemessen) |
| Handy-App parallel | nein, solange HA verbunden ist (Box erlaubt nur einen Client); Gruni22 hält die Verbindung dauerhaft | nein, solange der ESP32 verbunden ist |
| Lizenzlage heute | Gruni22: keine Lizenzdatei (Nutzung okay, Weitergabe/Änderung unklar) | neftaly: keine Lizenzdatei (gleiche Lage) |
| Reife | 52 Commits, Tests, aktiv gepflegt | laut README an einer CX40 getestet, weniger Aktivität |

## Empfehlung

1. **HACS-Integration von Gruni22** als Standardweg. Sie kommt ohne eigene Firmware aus, lässt sich per HACS aktualisieren und funktioniert auch über einen vorhandenen ESPHome-Bluetooth-Proxy. Das ist der Weg, zu dem wir beitragen.
2. **ESPHome nur dann**, wenn die Box außerhalb der Bluetooth-Reichweite von Home Assistant steht und dort ohnehin ein ESP32 läuft, oder wenn die Verbindung über den Proxy nicht stabil wird. Ein Beispiel liegt unter [`esphome/kuehlbox.yaml`](esphome/kuehlbox.yaml).

Ein eigener ESPHome-Bluetooth-Proxy ist ein guter Mittelweg: Der ESP32 steht bei der Box, die Logik bleibt aber in der HACS-Integration.

Die **IceCubeX** spricht dieses Protokoll (Statusabfrage am 25.09.2026 an einem Gerät belegt, siehe [RECHERCHE.md](RECHERCHE.md), Abschnitt 5).
