"""Constants for the MAENTUM BLE integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "maentum_ble"

# GATT service 0x1234 with command characteristic 0x1235 and notify
# characteristic 0x1236 (BrassMonkeyFridgeMonitor README, "Technical").
SERVICE_UUID: Final = "00001234-0000-1000-8000-00805f9b34fb"
WRITE_UUID: Final = "00001235-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID: Final = "00001236-0000-1000-8000-00805f9b34fb"

# Name prefixes the Alpicool app looks for (same source).
KNOWN_NAME_PREFIXES: Final = ("WT-", "A1-", "AK1-", "AK2-", "AK3-")

CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_KEEP_CONNECTED: Final = "keep_connected"

# The original app polls every 2 s, the Pekaway bridge every 10 s. A longer
# default is kinder to the box and to Bluetooth proxies.
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 600
DEFAULT_KEEP_CONNECTED: Final = True

# Seconds to wait for the answer to a command.
RESPONSE_TIMEOUT: Final = 5.0

# Usable ATT payload at the default MTU of 23 bytes.
DEFAULT_WRITE_CHUNK: Final = 20
# Pause between the chunks of a split write.
WRITE_CHUNK_DELAY: Final = 0.15
