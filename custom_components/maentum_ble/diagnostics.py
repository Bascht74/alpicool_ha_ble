"""Diagnostics: decoded status and the last raw frame, useful for new models."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .coordinator import MaentumConfigEntry

TO_REDACT = {CONF_ADDRESS, "address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MaentumConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    status = coordinator.data
    frame = coordinator.client.last_frame
    status_dict: dict[str, Any] | None = None
    if status is not None:
        status_dict = asdict(status)
        status_dict["raw"] = status.raw.hex(" ")
    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options)}, TO_REDACT
        ),
        "connected": coordinator.client.is_connected,
        "last_update_success": coordinator.last_update_success,
        "status": status_dict,
        "last_frame": None
        if frame is None
        else {
            "command": frame.command,
            "raw": frame.raw.hex(" "),
            "checksum": frame.checksum.name,
        },
    }
