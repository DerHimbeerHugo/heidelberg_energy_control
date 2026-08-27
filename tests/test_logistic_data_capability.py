"""Tests for Connect-series logistic strings."""

from custom_components.amperfied_connect_modbus.const import DATA_SW_VERSION
from custom_components.amperfied_connect_modbus.core.capabilities.logistic_data import (
    LogisticDataCapability,
    decode_ascii_registers,
)


def _encode_ascii(value: str, count: int = 41) -> dict[int, int]:
    payload = value.encode("ascii") + b"\x00"
    payload = payload.ljust(count * 2, b"\x00")
    return {
        1250 + offset: int.from_bytes(payload[offset * 2 : offset * 2 + 2], "big")
        for offset in range(count)
    }


def test_decode_ascii_registers_stops_at_nul_padding():
    registers = _encode_ascii("V2.4.1")
    assert decode_ascii_registers(registers, 1250, 41) == "V2.4.1"


def test_logistic_data_overrides_internal_software_revision():
    capability = LogisticDataCapability()
    assert capability.decode_static(_encode_ascii("V2.4.1")) == {
        DATA_SW_VERSION: "V2.4.1"
    }


def test_empty_firmware_string_does_not_override_fallback():
    capability = LogisticDataCapability()
    assert capability.decode_static(_encode_ascii("")) == {}
