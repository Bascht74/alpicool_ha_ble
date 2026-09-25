"""BLE client for Alpicool-compatible cooler boxes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from .const import (
    DEFAULT_WRITE_CHUNK,
    NOTIFY_UUID,
    RESPONSE_TIMEOUT,
    WRITE_CHUNK_DELAY,
    WRITE_UUID,
)
from .protocol import (
    Command,
    Frame,
    FrameReader,
    FridgeStatus,
    build_query,
    build_set,
    build_set_target,
    is_status_frame,
    parse_status,
)

_LOGGER = logging.getLogger(__name__)


class MaentumError(Exception):
    """Base error."""


class MaentumConnectionError(MaentumError):
    """The box could not be reached or the link dropped."""


class MaentumTimeoutError(MaentumError):
    """The box did not answer in time."""


class MaentumNotSupportedError(MaentumError):
    """The device does not offer the expected GATT characteristics."""


def _is_query_status(frame: Frame) -> bool:
    return frame.command == Command.QUERY and is_status_frame(frame)


class MaentumClient:
    """Talk to one box.

    Every public method runs as one transaction under a lock, so that a poll
    and a user command never interleave on the link.
    """

    def __init__(
        self,
        address: str,
        ble_device_callback: Callable[[], BLEDevice | None],
        *,
        keep_connected: bool = True,
    ) -> None:
        """Initialise the client. Nothing is connected yet."""
        self.address = address
        self._ble_device_callback = ble_device_callback
        self.keep_connected = keep_connected
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._reader = FrameReader()
        self._waiters: list[tuple[Callable[[Frame], bool], asyncio.Future[Frame]]] = []
        self._write_with_response = True
        self._write_chunk = DEFAULT_WRITE_CHUNK
        self.last_frame: Frame | None = None

    @property
    def is_connected(self) -> bool:
        """Return True while a link is up."""
        return self._client is not None and self._client.is_connected

    # --- connection -----------------------------------------------------

    def _on_disconnect(self, client: BleakClientWithServiceCache) -> None:
        if client is not self._client:
            return
        _LOGGER.debug("%s: disconnected", self.address)
        self._client = None
        self._reader.reset()
        for _, future in self._waiters:
            if not future.done():
                future.set_exception(MaentumConnectionError("disconnected"))

    async def _ensure_connected(self) -> BleakClientWithServiceCache:
        if self._client is not None and self._client.is_connected:
            return self._client
        device = self._ble_device_callback()
        if device is None:
            raise MaentumConnectionError(
                f"{self.address} is not in range of any Bluetooth adapter or proxy"
            )
        _LOGGER.debug("%s: connecting", self.address)
        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                device,
                device.name or self.address,
                disconnected_callback=self._on_disconnect,
                ble_device_callback=lambda: self._ble_device_callback() or device,
            )
        except (BleakError, TimeoutError) as err:
            raise MaentumConnectionError(str(err)) from err

        write_char = client.services.get_characteristic(WRITE_UUID)
        notify_char = client.services.get_characteristic(NOTIFY_UUID)
        if write_char is None or notify_char is None:
            await client.disconnect()
            raise MaentumNotSupportedError(f"{self.address} has no characteristics 0x1235/0x1236")
        # Prefer acknowledged writes: some boxes are reported to drop longer
        # unacknowledged writes (finding from Gruni22/alpicool_ha_ble).
        self._write_with_response = "write" in write_char.properties
        mtu = getattr(client, "mtu_size", None)
        self._write_chunk = (
            mtu - 3
            if isinstance(mtu, int) and mtu > DEFAULT_WRITE_CHUNK + 3
            else DEFAULT_WRITE_CHUNK
        )
        self._reader.reset()
        self._client = client
        try:
            await client.start_notify(notify_char, self._on_notify)
        except (BleakError, TimeoutError) as err:
            await self._disconnect()
            raise MaentumConnectionError(str(err)) from err
        _LOGGER.debug(
            "%s: connected (write response=%s, chunk=%d)",
            self.address,
            self._write_with_response,
            self._write_chunk,
        )
        return client

    async def _disconnect(self) -> None:
        client, self._client = self._client, None
        self._reader.reset()
        if client is not None:
            try:
                await client.disconnect()
            except (BleakError, TimeoutError) as err:
                _LOGGER.debug("%s: error on disconnect: %s", self.address, err)

    async def disconnect(self) -> None:
        """Close the link."""
        async with self._lock:
            await self._disconnect()

    # --- frames ---------------------------------------------------------

    def _on_notify(self, _sender: object, data: bytearray) -> None:
        for frame in self._reader.feed(bytes(data)):
            _LOGGER.debug("%s: <- %s", self.address, frame.raw.hex(" "))
            self.last_frame = frame
            for predicate, future in self._waiters:
                if not future.done() and predicate(frame):
                    future.set_result(frame)

    async def _write(self, packet: bytes) -> None:
        assert self._client is not None
        _LOGGER.debug("%s: -> %s", self.address, packet.hex(" "))
        try:
            for start in range(0, len(packet), self._write_chunk):
                if start:
                    await asyncio.sleep(WRITE_CHUNK_DELAY)
                await self._client.write_gatt_char(
                    WRITE_UUID,
                    packet[start : start + self._write_chunk],
                    response=self._write_with_response,
                )
        except (BleakError, TimeoutError) as err:
            await self._disconnect()
            raise MaentumConnectionError(str(err)) from err

    async def _request(
        self,
        packet: bytes,
        predicate: Callable[[Frame], bool],
        timeout: float | None = None,
    ) -> Frame:
        future: asyncio.Future[Frame] = asyncio.get_running_loop().create_future()
        waiter = (predicate, future)
        self._waiters.append(waiter)
        try:
            await self._write(packet)
            async with asyncio.timeout(timeout or RESPONSE_TIMEOUT):
                return await future
        except TimeoutError as err:
            raise MaentumTimeoutError(f"{self.address} did not answer") from err
        finally:
            self._waiters.remove(waiter)

    async def _query(self) -> FridgeStatus:
        await self._ensure_connected()
        frame = await self._request(build_query(), _is_query_status)
        return parse_status(frame.payload)

    async def _finish(self) -> None:
        if not self.keep_connected:
            await self._disconnect()

    # --- public API -------------------------------------------------------

    async def async_query(self) -> FridgeStatus:
        """Read the current status."""
        async with self._lock:
            try:
                return await self._query()
            finally:
                await self._finish()

    async def async_set_target(self, zone: int, temperature: int) -> FridgeStatus:
        """Set the target temperature of a zone and return the new status."""
        packet = build_set_target(zone, temperature)
        command = packet[3]
        async with self._lock:
            try:
                await self._ensure_connected()
                try:
                    await self._request(packet, lambda f: f.command == command)
                except MaentumTimeoutError:
                    # The echo is only a confirmation; the query below decides.
                    _LOGGER.debug("%s: no echo for set target", self.address)
                return await self._query()
            finally:
                await self._finish()

    async def async_set(
        self,
        status: FridgeStatus,
        *,
        locked: bool | None = None,
        powered_on: bool | None = None,
        run_mode: int | None = None,
        battery_saver: int | None = None,
    ) -> FridgeStatus:
        """Change settings and return the new status.

        ``status`` provides every value that is not changed, see
        :func:`protocol.build_set`.
        """
        packet = build_set(
            status,
            locked=locked,
            powered_on=powered_on,
            run_mode=run_mode,
            battery_saver=battery_saver,
        )
        async with self._lock:
            try:
                await self._ensure_connected()
                try:
                    await self._request(
                        packet, lambda f: f.command == Command.SET and is_status_frame(f)
                    )
                except MaentumTimeoutError:
                    _LOGGER.debug("%s: no status answer for set", self.address)
                return await self._query()
            finally:
                await self._finish()
