"""Tests for the BLE client against a fake Bleak client."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
import pytest

from custom_components.maentum_ble import client as client_mod
from custom_components.maentum_ble.client import (
    MaentumClient,
    MaentumConnectionError,
    MaentumNotSupportedError,
    MaentumTimeoutError,
)
from custom_components.maentum_ble.const import NOTIFY_UUID, WRITE_UUID
from custom_components.maentum_ble.protocol import build_frame, parse_status

from .conftest import ADDRESS, DUAL_PAYLOAD, SINGLE_PAYLOAD

STATUS_FRAME = build_frame(0x01, SINGLE_PAYLOAD)


class FakeBleak:
    """Minimal stand-in for BleakClientWithServiceCache."""

    def __init__(
        self,
        responder: Callable[[bytes], list[bytes]] | None = None,
        *,
        properties: tuple[str, ...] = ("write", "write-without-response"),
        has_chars: bool = True,
        mtu: int = 23,
    ) -> None:
        self.responder = responder or (lambda _pkt: [STATUS_FRAME])
        self.connected = True
        self.writes: list[tuple[bytes, bool]] = []
        self.notify_cb: Callable[[Any, bytearray], None] | None = None
        self.disconnected_callback: Callable[[Any], None] | None = None
        self.mtu_size = mtu
        self._buffer = bytearray()
        chars = {
            WRITE_UUID: SimpleNamespace(uuid=WRITE_UUID, properties=list(properties)),
            NOTIFY_UUID: SimpleNamespace(uuid=NOTIFY_UUID, properties=["notify"]),
        }
        self.services = SimpleNamespace(
            get_characteristic=lambda uuid: chars.get(uuid) if has_chars else None
        )

    @property
    def is_connected(self) -> bool:
        return self.connected

    async def start_notify(self, _char: Any, callback: Callable) -> None:
        self.notify_cb = callback

    async def write_gatt_char(self, _uuid: str, data: bytes, response: bool) -> None:
        self.writes.append((bytes(data), response))
        self._buffer.extend(data)
        # A packet is complete once its length byte is satisfied.
        if len(self._buffer) >= 3 and len(self._buffer) >= 3 + self._buffer[2]:
            packet, self._buffer = bytes(self._buffer), bytearray()
            for answer in self.responder(packet):
                # Deliver in 20 byte notifications like a real box at default MTU.
                for i in range(0, len(answer), 20):
                    asyncio.get_running_loop().call_soon(
                        self.notify_cb, None, bytearray(answer[i : i + 20])
                    )

    async def disconnect(self) -> None:
        self.connected = False
        if self.disconnected_callback:
            self.disconnected_callback(self)


def _patch(fake: FakeBleak):
    async def _establish(_cls, _device, _name, disconnected_callback=None, **_kw):
        fake.disconnected_callback = disconnected_callback
        return fake

    return patch.object(client_mod, "establish_connection", _establish)


def _client(**kwargs: Any) -> MaentumClient:
    device = BLEDevice(ADDRESS, "WT-0001", {})
    return MaentumClient(ADDRESS, lambda: device, **kwargs)


async def test_query_reassembles_fragments() -> None:
    """A 24 byte status split into 20 + 4 is decoded."""
    fake = FakeBleak()
    client = _client()
    with _patch(fake):
        status = await client.async_query()
    assert status == parse_status(SINGLE_PAYLOAD)
    assert fake.writes == [(bytes.fromhex("fefe03010200"), True)]
    assert client.is_connected


async def test_keep_connected_false_disconnects() -> None:
    """Without keep_connected the link is closed after each query."""
    fake = FakeBleak()
    client = _client(keep_connected=False)
    with _patch(fake):
        await client.async_query()
    assert not client.is_connected


async def test_not_in_range() -> None:
    """No BLEDevice means no connection attempt."""
    client = MaentumClient(ADDRESS, lambda: None)
    with pytest.raises(MaentumConnectionError):
        await client.async_query()


async def test_connect_error() -> None:
    """Bleak errors while connecting become MaentumConnectionError."""

    async def _fail(*_a: Any, **_kw: Any) -> None:
        raise BleakError("nope")

    with (
        patch.object(client_mod, "establish_connection", _fail),
        pytest.raises(MaentumConnectionError),
    ):
        await _client().async_query()


async def test_not_supported() -> None:
    """A device without 0x1235/0x1236 is rejected and disconnected."""
    fake = FakeBleak(has_chars=False)
    with _patch(fake), pytest.raises(MaentumNotSupportedError):
        await _client().async_query()
    assert not fake.connected


async def test_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """No answer raises MaentumTimeoutError."""
    monkeypatch.setattr(client_mod, "RESPONSE_TIMEOUT", 0.05)
    fake = FakeBleak(lambda _pkt: [])
    client = _client()
    with _patch(fake), pytest.raises(MaentumTimeoutError):
        await client._query()


async def test_write_without_response_only() -> None:
    """Characteristics without 'write' use write-without-response."""
    fake = FakeBleak(properties=("write-without-response",))
    with _patch(fake):
        await _client().async_query()
    assert fake.writes[0][1] is False


async def test_set_target_then_query() -> None:
    """Set target waits for the echo and then reads the status."""
    seen: list[bytes] = []

    def responder(packet: bytes) -> list[bytes]:
        seen.append(packet)
        if packet[3] == 0x05:
            return [packet]  # echo
        return [STATUS_FRAME]

    fake = FakeBleak(responder)
    with _patch(fake):
        await _client().async_set_target(1, -18)
    assert seen == [bytes.fromhex("fefe0405ee02f3"), bytes.fromhex("fefe03010200")]


async def test_set_splits_long_packets_and_ignores_echo() -> None:
    """A dual-zone Set (31 bytes) is written in chunks; the echo is not taken as status."""
    dual_status = parse_status(DUAL_PAYLOAD)
    dual_frame = build_frame(0x01, DUAL_PAYLOAD)
    set_answer = build_frame(0x02, DUAL_PAYLOAD)

    def responder(packet: bytes) -> list[bytes]:
        if packet[3] == 0x02:
            return [packet + set_answer]  # echo and status in one go
        return [dual_frame]

    fake = FakeBleak(responder)
    with _patch(fake):
        result = await _client().async_set(dual_status, powered_on=False)
    assert result == dual_status
    set_chunks = [w for w, _ in fake.writes if w[:2] == b"\xfe\xfe" and w[3] == 0x02]
    assert len(set_chunks) == 1
    assert len(fake.writes[0][0]) == 20
    assert len(fake.writes[1][0]) == 11


async def test_uses_larger_mtu() -> None:
    """A negotiated MTU avoids splitting."""
    dual_status = parse_status(DUAL_PAYLOAD)
    fake = FakeBleak(lambda p: [build_frame(p[3], DUAL_PAYLOAD)], mtu=185)
    with _patch(fake):
        await _client().async_set(dual_status, locked=True)
    assert len(fake.writes[0][0]) == 31


async def test_disconnect_fails_pending_request() -> None:
    """A drop while waiting raises MaentumConnectionError instead of hanging."""
    fake = FakeBleak(lambda _pkt: [])
    client = _client()
    with _patch(fake):
        await client._ensure_connected()
        task = asyncio.create_task(client._query())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        fake.connected = False
        fake.disconnected_callback(fake)
        with pytest.raises(MaentumConnectionError):
            await task
    assert not client.is_connected


async def test_write_error_disconnects() -> None:
    """A failing write closes the link and raises."""
    fake = FakeBleak()

    async def _boom(*_a: Any, **_kw: Any) -> None:
        raise BleakError("write failed")

    fake.write_gatt_char = _boom  # type: ignore[method-assign]
    client = _client()
    with _patch(fake), pytest.raises(MaentumConnectionError):
        await client.async_query()
    assert not client.is_connected


async def test_reconnects_after_drop() -> None:
    """After a disconnect the next query connects again."""
    fake = FakeBleak()
    client = _client()
    with _patch(fake):
        await client.async_query()
        await fake.disconnect()
        assert not client.is_connected
        fake.connected = True
        await client.async_query()
    assert client.is_connected
