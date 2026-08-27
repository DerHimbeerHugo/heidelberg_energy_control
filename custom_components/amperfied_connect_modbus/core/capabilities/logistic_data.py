"""Static logistic data exposed by Connect-series register layouts."""

from __future__ import annotations

from typing import Any

from ...const import DATA_SW_VERSION
from ..registers import RegisterDefinition, RegisterType
from .base import Capability

REG_FIRMWARE_VERSION_START = 1250
REG_FIRMWARE_VERSION_COUNT = 41


def decode_ascii_registers(
    registers: dict[int, int], start: int, count: int
) -> str:
    """Decode two big-endian ASCII characters per Modbus register."""
    payload = bytearray()
    for address in range(start, start + count):
        payload.extend(int(registers[address]).to_bytes(2, byteorder="big"))

    # Logistic strings are NUL-terminated and the remaining registers are
    # padded with 0x0000.
    return payload.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()


class LogisticDataCapability(Capability):
    """Read the real wallbox firmware string on layout v2.0.0 and newer."""

    key = "logistic_data"
    min_layout_version = "2.0.0"

    static_definitions: tuple[RegisterDefinition, ...] = (
        RegisterDefinition(
            REG_FIRMWARE_VERSION_START,
            REG_FIRMWARE_VERSION_COUNT,
            RegisterType.INPUT,
        ),
    )

    def decode_static(self, registers: dict[int, int]) -> dict[str, Any]:
        firmware = decode_ascii_registers(
            registers, REG_FIRMWARE_VERSION_START, REG_FIRMWARE_VERSION_COUNT
        )
        return {DATA_SW_VERSION: firmware} if firmware else {}
