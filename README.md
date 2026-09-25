# MAENTUM Kühlbox (BLE) – eigenständige Integration (Vorlage)

Dieser Branch enthält eine vollständige Home-Assistant-Integration für Kühlboxen mit dem Alpicool-BLE-Protokoll. Sie ist **nicht** der empfohlene Installationsweg, sondern Vorlage für Beiträge an [Gruni22/alpicool_ha_ble](https://github.com/Gruni22/alpicool_ha_ble). Anleitung, Recherche und Review stehen im Branch [`claude/maentum-doku-pruefskript`](https://github.com/Bascht74/alpicool_ha_ble/tree/claude/maentum-doku-pruefskript/docs/maentum).

**Nicht an echter Hardware getestet.** Die Tests laufen gegen Mitschnitte aus den Quellen und einen simulierten BLE-Client.

## Aufbau

| Datei | Aufgabe |
|---|---|
| `protocol.py` | Codec ohne HA-Abhängigkeit: Rahmen bauen, Status decodieren, Notifications zusammensetzen |
| `client.py` | BLE-Verbindung über `bleak-retry-connector`, eine Transaktion pro Lock, Write in MTU-Stücken |
| `coordinator.py` | `DataUpdateCoordinator`, Befehle veröffentlichen den neuen Status sofort |
| `config_flow.py` | Bluetooth-Discovery, Geräteliste, Verbindungsprüfung, Optionen (Intervall, Verbindung halten) |
| `climate.py` | je Zone: Ein/Aus, Solltemperatur, Presets Max/Eco |
| `sensor.py` | Ist-Temperaturen, Spannung, Akku (0x7F → unbekannt) |
| `switch.py`, `select.py` | Tastensperre, Batterieschutz |
| `diagnostics.py` | Status und letzter Rohrahmen, Adresse geschwärzt |

## Tests

```bash
pip install -r requirements_test.txt   # zieht Home Assistant 2026.2 für die Tests
pytest -q                              # 97 Tests
```

## Lizenz

MIT
