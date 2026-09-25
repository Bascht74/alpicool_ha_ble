# Alpicool-BLE-Protokoll (Zusammenfassung mit Quellen)

Kürzel: **BM** = [BrassMonkeyFridgeMonitor](https://github.com/klightspeed/BrassMonkeyFridgeMonitor) (README „Technical“ und `fridge.py`, MIT), **NE** = [neftaly/esphome-alpicool](https://github.com/neftaly/esphome-alpicool) `docs/protocol.md`, **GR** = [Gruni22/alpicool_ha_ble](https://github.com/Gruni22/alpicool_ha_ble) README. Eigene Schlussfolgerungen sind als *abgeleitet* markiert.

Der Code dazu ist [`tools/alpicool_protocol.py`](../../tools/alpicool_protocol.py), getestet in [`tests/test_tools_protocol.py`](../../tests/test_tools_protocol.py) mit den Mitschnitten aus BM und NE.

## GATT

| Rolle | UUID | Quelle |
|---|---|---|
| Service | `0x1234` = `00001234-0000-1000-8000-00805f9b34fb` | BM |
| Befehle (Write) | `0x1235` = `00001235-0000-1000-8000-00805f9b34fb` | BM |
| Antworten (Notify) | `0x1236` = `00001236-0000-1000-8000-00805f9b34fb` | BM |

- Keine Authentifizierung, kein Pairing, keine PIN (BM).
- Eine Verbindung sperrt alle anderen Clients; die Box sendet dann keine Advertisements (BM). Home Assistant und Handy-App schließen sich also gegenseitig aus.
- Bekannte Gerätenamen: `WT-0001`, Präfixe `A1-`, `AK1-`, `AK2-`, `AK3-` (BM). smarthomeundmore.de nennt `W1001` für eine Plug-In-Festivals-Box (berichtet).
- Der Zustand lässt sich nicht passiv aus Advertisements lesen, man muss verbinden und abfragen (NE).

## Rahmen

```
FE FE <len> <cmd> <daten ...> <summe_hi> <summe_lo>
```

- `len` zählt alle Bytes nach sich selbst: Befehl + Daten + 2 Prüfsummenbytes (BM, `create_packet`).
- Prüfsumme: 16-Bit-Summe aller vorherigen Bytes inkl. Header, Big Endian (BM).
- Manche Firmwares senden die doppelte Summe; BM und NE akzeptieren beides.
- Bei einem A1-4X passten die letzten zwei Bytes zu keiner Variante; NE prüft deshalb nur Header und Länge (NE, Hinweis 1). Unser Code akzeptiert solche Rahmen und protokolliert sie.
- Antworten über 20 Byte kommen bei Standard-MTU in Stücken (z. B. 20 + 4) und müssen zusammengesetzt werden (NE). Ein SET-Echo und der neue Status können in einer Notification stecken (GR).
- *Abgeleitet*: Der BM-Mitschnitt `fe fe 03 05 ec 02 f1` (Solltemperatur −20) hat vermutlich einen Tippfehler im Längenbyte. Die Prüfsumme `02 f1` passt nur zu `04`, und BMs eigener Code erzeugt `04`. NE bestätigt das Muster mit `FE FE 04 05 EE 02 F3` für −18.

## Befehle

| Code | Name | Daten | Antwort | Quelle |
|---|---|---|---|---|
| `0x00` | Bind | – | Box zeigt „APP“, antwortet nach Tastendruck | BM |
| `0x01` | Query | – | Status (siehe unten) | BM |
| `0x02` | Set | alle Einstellungen, 14 Byte (1 Zone) / 25 Byte (2 Zonen) | Status mit cmd `0x02` | BM |
| `0x04` | Reset | – | Status | BM |
| `0x05` | Soll Zone 1 | int8 in der Einheit der Box | Echo | BM |
| `0x06` | Soll Zone 2 | int8 | Echo | BM |

Bind ist optional, die Box nimmt Befehle auch ohne an (BM).

Set überträgt immer alle Werte; die App füllt unveränderte Werte aus dem letzten Status (BM, Mitschnitt).

## Status (Nutzdaten nach dem Befehlsbyte)

Alle Temperaturen sind int8 in der eingestellten Einheit (BM).

| Offset | Feld | Bedeutung |
|---|---|---|
| 0x00 | locked | Tastensperre 0/1 |
| 0x01 | poweredOn | Ein/Aus |
| 0x02 | runMode | 0 = Max, 1 = Eco |
| 0x03 | batSaver | Unterspannungsschutz 0 = niedrig, 1 = mittel, 2 = hoch |
| 0x04 | leftTarget | Soll Zone 1 |
| 0x05 | tempMax | höchster wählbarer Sollwert |
| 0x06 | tempMin | niedrigster wählbarer Sollwert |
| 0x07 | leftRetDiff | Hysterese Zone 1 |
| 0x08 | startDelay | Startverzögerung in Minuten |
| 0x09 | unit | 0 = °C, 1 = °F |
| 0x0A–0x0D | leftTC* | Temperaturkorrekturen Zone 1 |
| 0x0E | leftCurrent | Ist Zone 1 |
| 0x0F | batPercent | Akku in %, `0x7F` = unbekannt |
| 0x10 | batVolInt | Spannung, ganze Volt |
| 0x11 | batVolDec | Spannung, Zehntel |
| 0x12 | rightTarget | Soll Zone 2 (nur Dual-Zone) |
| 0x15 | rightRetDiff | Hysterese Zone 2 |
| 0x16–0x19 | rightTC* | Korrekturen Zone 2 |
| 0x1A | rightCurrent | Ist Zone 2 |
| 0x1B | runningStatus | Bedeutung unbekannt (BM) |

Dual-Zone erkennt man an einer Nutzlast ab 28 Byte (NE).

## Testvektoren (aus den Quellen)

```
Query           fe fe 03 01 02 00                                   (BM, NE)
Bind            fe fe 03 00 01 ff                                   (BM)
Bind-Antwort    fe fe 04 00 01 02 01                                (BM)
Status          fe fe 15 01 00 01 00 00 f1 14 ec 02 00 00 00 00 00 00 f3 64 0c 03 05 6c   (BM, NE)
                → an, Max, Soll −15, Bereich −20..20, Ist −13, 100 %, 12,3 V
Soll −18        fe fe 04 05 ee 02 f3                                (NE)
Set (Schutz hoch) fe fe 11 02 00 01 00 02 ec 14 ec 02 00 00 00 00 00 00 04 00          (BM)
```
