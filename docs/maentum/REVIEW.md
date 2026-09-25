# Review: Gruni22/alpicool_ha_ble

As of: commit `5e0cc2e` ("Add tests", 2026-09-25), version 3.1.10 according to `manifest.json`.
Checked: source code of all files in `custom_components/alpicool_ble/`, test suite (79 tests, all green under Home Assistant 2026.2.3 / Python 3.13), comparison with the protocol from [PROTOCOL.md](PROTOCOL.md).

The integration works at its core and covers the protocol completely. The following points are suggestions for pull requests once a license is in place. Each finding names the location in the code.

## Bugs (incorrect behavior)

| # | Finding | Location | Consequence | Suggestion |
|---|---|---|---|---|
| F1 | Battery level `0x7F` is shown as 127 % | `api.py` `_decode_status` (`bat_percent`), `sensor.py` | Boxes without battery measurement (e.g. on mains power) show 127 % | return `0x7F` as `None` (unknown); source BM/NE |
| F2 | Button lock, battery protection and number entities do not query the status after writing | `switch.py`, `select.py`, `number.py`: only `async_set_values`, no `update_status` | UI shows the old value until the next poll (30 s) | query the status after every write, as `climate.py` does, or evaluate the status response to SET (F3) |
| F3 | The status response to SET (cmd `0x02`, 18/28 bytes) is discarded | `api.py` `_notification_handler`: "Ignoring echo for SET command" | Unnecessary delay, an additional query | evaluate SET frames with an 18 or ≥ 28 byte payload as status, discard 14/25 bytes (echo) |
| F4 | Entity names contain the device name twice | `sensor.py`, `switch.py`, `number.py`: `_attr_name = f"{entry.data['name']} …"` with `_attr_has_entity_name = True` | Display e.g. "Cooler box Cooler box Battery" | set only the name part, better `translation_key` |
| F5 | Climate entity does not support `climate.turn_on`/`turn_off` | `climate.py`: `ClimateEntityFeature.TURN_ON`/`TURN_OFF` missing | These services are not available for the entity, although `HVACMode.OFF` is offered | set both flags and implement `async_turn_on/off` |

## Robustness

| # | Finding | Location | Suggestion |
|---|---|---|---|
| R1 | Service UUID `0000fff0-…` as discovery matcher | `manifest.json` | `FFF0` is used by many cheap BLE modules; probably leads to false detections. Remove without evidence and replace with `local_name` matchers (`WT-*`, `A1-*`, `AK1-*`, `AK2-*`, `AK3-*`, source BM) |
| R2 | Bind during setup waits up to 20 s | `api.py` `connect()`, `timeout=20` | According to BM, bind is not needed. Make bind optional (button entity or option), do not block setup |
| R3 | Config flow does not check the connection | `config_flow.py` | Connect and query once before creating the entry, show errors "cannot_connect"/"not_supported" |
| R4 | Manual MAC entry instead of a device list | `config_flow.py` `async_step_user` | Offer a list from `async_discovered_service_info`, known names first |
| R5 | Value ranges hysteresis 1–10, start delay 0–10 without a source | `number.py` | Name the source or document the range from observation |
| R6 | README outdated: according to the README, single-zone boxes get a permanently unavailable right zone, but the code only creates it for dual zone | `README.md` vs. `climate.py` | Update the README |

## Architecture (Home Assistant standards)

| # | Finding | Suggestion |
|---|---|---|
| A1 | `hass.data[DOMAIN]` instead of `entry.runtime_data` | typed `ConfigEntry[...]` with `runtime_data` |
| A2 | Own poll loop with dispatcher instead of `DataUpdateCoordinator` | Coordinator: consistent availability and error behavior, less code |
| A3 | No `diagnostics.py` | Diagnostics with raw data of the last frame, helps with new models such as the IceCubeX |
| A4 | Error texts and names hard-coded (English) | `translation_key`, `exceptions` in `strings.json` |
| A5 | CI only checks HACS, not `hassfest` and not the own tests | Extend the workflow with `hassfest` and `pytest` |
