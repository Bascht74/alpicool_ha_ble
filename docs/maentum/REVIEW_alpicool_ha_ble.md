# Review: Gruni22/alpicool_ha_ble

Stand: Commit `5e0cc2e` („Add tests“, 25.09.2026), Version 3.1.10 laut `manifest.json`.
Geprüft: Quelltext aller Dateien in `custom_components/alpicool_ble/`, Testsuite (79 Tests, alle grün unter Home Assistant 2026.2.3 / Python 3.13), Abgleich mit dem Protokoll aus [PROTOKOLL.md](PROTOKOLL.md).

Die Integration funktioniert im Kern und deckt das Protokoll vollständig ab. Die folgenden Punkte sind Vorschläge für Pull Requests, sobald eine Lizenz vorliegt. Jeder Befund nennt die Stelle im Code.

## Fehler (Verhalten falsch)

| # | Befund | Stelle | Folge | Vorschlag |
|---|---|---|---|---|
| F1 | Akkustand `0x7F` wird als 127 % angezeigt | `api.py` `_decode_status` (`bat_percent`), `sensor.py` | Bei Boxen ohne Akku-Messung (z. B. Netzbetrieb) steht 127 % | `0x7F` als `None` (unbekannt) liefern; Quelle BM/NE |
| F2 | Tastensperre, Batterieschutz und Number-Entitäten fragen nach dem Schreiben keinen Status ab | `switch.py`, `select.py`, `number.py`: nur `async_set_values`, kein `update_status` | UI zeigt bis zum nächsten Poll (30 s) den alten Wert | nach jedem Schreiben Status abfragen, wie `climate.py` es tut, oder die Status-Antwort auf SET auswerten (F3) |
| F3 | Die Status-Antwort auf SET (cmd `0x02`, 18/28 Byte) wird verworfen | `api.py` `_notification_handler`: „Ignoring echo for SET command“ | Unnötige Verzögerung, ein zusätzlicher Query | SET-Rahmen mit 18 oder ≥ 28 Byte Nutzlast als Status auswerten, 14/25 Byte (Echo) verwerfen |
| F4 | Entitätsnamen enthalten den Gerätenamen doppelt | `sensor.py`, `switch.py`, `number.py`: `_attr_name = f"{entry.data['name']} …"` bei `_attr_has_entity_name = True` | Anzeige z. B. „Kühlbox Kühlbox Battery“ | nur den Namensteil setzen, besser `translation_key` |
| F5 | Klima-Entität unterstützt `climate.turn_on`/`turn_off` nicht | `climate.py`: `ClimateEntityFeature.TURN_ON`/`TURN_OFF` fehlen | Diese Dienste sind für die Entität nicht verfügbar, obwohl `HVACMode.OFF` angeboten wird | beide Flags setzen und `async_turn_on/off` implementieren |

## Robustheit

| # | Befund | Stelle | Vorschlag |
|---|---|---|---|
| R1 | Service-UUID `0000fff0-…` als Discovery-Matcher | `manifest.json` | `FFF0` nutzen viele billige BLE-Module; führt vermutlich zu Fehlerkennungen. Ohne Beleg streichen und durch `local_name`-Matcher (`WT-*`, `A1-*`, `AK1-*`, `AK2-*`, `AK3-*`, Quelle BM) ersetzen |
| R2 | Bind beim Setup wartet bis zu 20 s | `api.py` `connect()`, `timeout=20` | Laut BM ist Bind nicht nötig. Bind optional machen (Button-Entität oder Option), Setup nicht blockieren |
| R3 | Config-Flow prüft die Verbindung nicht | `config_flow.py` | Vor dem Anlegen einmal verbinden und abfragen, Fehler „cannot_connect“/„not_supported“ anzeigen |
| R4 | Manuelle MAC-Eingabe statt Geräteliste | `config_flow.py` `async_step_user` | Liste aus `async_discovered_service_info` anbieten, bekannte Namen zuerst |
| R5 | Wertebereiche Hysterese 1–10, Startverzögerung 0–10 ohne Quelle | `number.py` | Quelle nennen oder Bereich aus Beobachtung dokumentieren |
| R6 | README veraltet: Single-Zone-Boxen bekommen laut README eine dauerhaft nicht verfügbare rechte Zone, der Code legt sie aber nur bei Dual-Zone an | `README.md` vs. `climate.py` | README anpassen |

## Architektur (Home-Assistant-Standards)

| # | Befund | Vorschlag |
|---|---|---|
| A1 | `hass.data[DOMAIN]` statt `entry.runtime_data` | typisiertes `ConfigEntry[...]` mit `runtime_data` |
| A2 | Eigene Poll-Schleife mit Dispatcher statt `DataUpdateCoordinator` | Coordinator: einheitliches Verfügbarkeits- und Fehlerverhalten, weniger Code |
| A3 | Keine `diagnostics.py` | Diagnose mit Rohdaten des letzten Rahmens, hilft bei neuen Modellen wie der IceCubeX |
| A4 | Fehlertexte und Namen hart kodiert (Englisch) | `translation_key`, `exceptions` in `strings.json` |
| A5 | CI prüft nur HACS, nicht `hassfest` und nicht die eigenen Tests | Workflow um `hassfest` und `pytest` ergänzen |
