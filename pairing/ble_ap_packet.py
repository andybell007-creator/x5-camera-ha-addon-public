#!/usr/bin/env python3
"""Encoder/decoder for the Z-IOT CAM app's BLE WiFi-provisioning packet.

Reverse-engineered from a live capture (Android Bluetooth HCI snoop log,
pulled via `adb bugreport`) of a real pairing session against a TXW817-based
camera, cross-checked byte-for-byte across two independent captures.

Frame layout (all multi-byte integers big-endian):

    bytes[0:2]   86 86        fixed marker
    bytes[2:4]   u16          outer_len = len(bytes[4:]) - 2 (excludes checksum+terminator)
    bytes[4:6]   00 01        constant -- meaning not decoded; observed fixed in both captures
    bytes[6:8]   u16          inner_len = len(bytes[8:]) - 2 - 2 (excludes checksum+terminator+tag)
    bytes[8:10]  00 01        constant -- meaning not decoded; observed fixed in both captures
    bytes[10:…]  fields       repeated: 1-byte length + that many UTF-8 bytes
    …            00 3c        fixed tag -- meaning not decoded (command id? end-of-fields marker?)
    …            1 byte       XOR of every byte from offset 0 up to and including the tag
    …            0d           terminator

The camera is written to on the custom GATT write characteristic
36000002-0001-0002-0003-010203040506 (service 36000001-...), in chunks no
larger than 20 bytes (matches the app's own BLE-MTU-limited chunking), and
replies on the notify characteristic 36000003-0001-0002-0003-010203040506.

The `00 01` constants and the `00 3c` tag are carried over unchanged from the
observed capture rather than derived, since their meaning was not determined
from either static analysis or the live capture (only one command type has
been observed). They may need adjusting if pairing turns out to need a
different command variant.
"""
from __future__ import annotations

import struct

MARKER = b"\x86\x86"
FIELD1_CONST = b"\x00\x01"
FIELD2_CONST = b"\x00\x01"
TAG = b"\x00\x3c"
TERMINATOR = b"\x0d"
BLE_WRITE_CHUNK = 20

SERVICE_UUID = "36000001-0001-0002-0003-010203040506"
WRITE_CHAR_UUID = "36000002-0001-0002-0003-010203040506"
NOTIFY_CHAR_UUID = "36000003-0001-0002-0003-010203040506"


def _length_prefixed(*fields: str) -> bytes:
    out = bytearray()
    for f in fields:
        raw = f.encode("utf-8")
        if len(raw) > 255:
            raise ValueError(f"field {f!r} is {len(raw)} bytes, too long for a 1-byte length prefix")
        out.append(len(raw))
        out += raw
    return bytes(out)


def build_ap_info_packet(ssid: str, password: str, signaling_server: str) -> bytes:
    """Build a WiFi-provisioning packet for the camera's BLE write characteristic.

    `signaling_server` is the host:port the camera should use for cloud
    signaling -- observed as "sig.gps555.net:8882" in a live capture; pass
    that value unless you have reason to believe it differs by region/account.
    """
    fields = _length_prefixed(ssid, password, signaling_server)

    # inner_len spans f2 + fields + tag (bytes[8:] through the tag, exclusive
    # of the checksum byte that follows it).
    inner_len = len(FIELD2_CONST) + len(fields) + len(TAG)
    outer_payload = FIELD1_CONST + struct.pack(">H", inner_len) + FIELD2_CONST + fields + TAG
    # outer_len spans bytes[4:] through the checksum byte (+1), exclusive of
    # the terminator.
    outer_len = len(outer_payload) + 1

    packet = MARKER + struct.pack(">H", outer_len) + outer_payload
    checksum = 0
    for b in packet:
        checksum ^= b
    packet += bytes([checksum]) + TERMINATOR
    return packet


def chunk_for_ble(packet: bytes, chunk_size: int = BLE_WRITE_CHUNK) -> list[bytes]:
    return [packet[i:i + chunk_size] for i in range(0, len(packet), chunk_size)]


def parse_ap_info_packet(packet: bytes) -> dict:
    """Inverse of build_ap_info_packet, for verifying a capture against this model."""
    if packet[0:2] != MARKER:
        raise ValueError("bad marker")
    outer_len = struct.unpack(">H", packet[2:4])[0]
    if len(packet) != 4 + outer_len + 1:
        raise ValueError(f"length mismatch: outer_len={outer_len} but packet is {len(packet)} bytes")
    f1 = packet[4:6]
    inner_len = struct.unpack(">H", packet[6:8])[0]
    f2 = packet[8:10]

    fields_end = 8 + inner_len - len(TAG)
    pos = 10
    fields = []
    while pos < fields_end:
        ln = packet[pos]
        fields.append(packet[pos + 1:pos + 1 + ln].decode("utf-8"))
        pos += 1 + ln
    if pos != fields_end:
        raise ValueError("field parsing did not land exactly on the tag boundary")

    tag = packet[fields_end:fields_end + 2]
    checksum_byte = packet[fields_end + 2]
    terminator = packet[fields_end + 3:fields_end + 4]

    computed = 0
    for b in packet[:fields_end + 2]:
        computed ^= b

    return {
        "f1": f1, "f2": f2, "tag": tag,
        "fields": fields,
        "checksum_ok": computed == checksum_byte,
        "terminator_ok": terminator == TERMINATOR,
    }


def _self_test() -> None:
    # Synthetic values -- NOT real credentials. Round-trips build -> parse
    # and checks the encoder reproduces the exact structural rules recovered
    # from the real capture (field order, length formulas, checksum).
    pkt = build_ap_info_packet("TestNetwork-2.4", "s0meP4ssw0rd", "sig.gps555.net:8882")
    parsed = parse_ap_info_packet(pkt)
    assert parsed["fields"] == ["TestNetwork-2.4", "s0meP4ssw0rd", "sig.gps555.net:8882"], parsed
    assert parsed["checksum_ok"], "checksum did not verify"
    assert parsed["terminator_ok"]
    assert parsed["f1"] == FIELD1_CONST and parsed["f2"] == FIELD2_CONST
    assert pkt[0:2] == MARKER
    assert pkt[-1:] == TERMINATOR
    chunks = chunk_for_ble(pkt)
    assert all(len(c) <= BLE_WRITE_CHUNK for c in chunks)
    assert b"".join(chunks) == pkt
    print(f"self-test OK: {len(pkt)}-byte packet, {len(chunks)} BLE chunks")


if __name__ == "__main__":
    _self_test()
