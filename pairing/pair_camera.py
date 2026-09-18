#!/usr/bin/env python3
"""Pair a new Z-IOT CAM / TXW817 camera without the vendor app.

Two independent steps, both reverse-engineered from a live capture of the
real app pairing a camera (see ble_ap_packet.py for the wire-format
derivation):

  1. BLE: connect to the camera's own BLE advertisement, push it your WiFi
     SSID/password and the vendor's signaling-server address, and read back
     its device UID from the notification it sends in response.
  2. Cloud HTTP: log into the guest account (same one refresh_ziot_token.sh
     already uses) and bind the camera's UID to that account via
     POST /v1/family/add-ipc, so it shows up in your device list.

Needs `bleak` (pip install bleak) and network access for step 2. Run under
Python 3.12+ -- this project's system Python 3.9 could not build bleak's
pyobjc dependency.

This has been validated ONLY at the packet-encoding level (round-tripped
against two real captures) -- the live BLE connect/write/notify path has
NOT been exercised end-to-end yet. Treat the first run as a test.

Usage:
    python3 pair_camera.py --ssid 'YourWiFi' --password 'yourpassword' \\
        --guest-username guest_XXXXXXXXXXXXX --guest-password-md5 <md5 of "666666">
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import getpass
import json
import re
import sys
import urllib.error
import urllib.request

from ble_ap_packet import (
    BLE_WRITE_CHUNK,
    NOTIFY_CHAR_UUID,
    WRITE_CHAR_UUID,
    build_ap_info_packet,
    chunk_for_ble,
)

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    sys.exit("bleak is required: run '~/.pyenv/versions/3.12.14/bin/python3 -m pip install bleak' "
             "then re-run this script with that same interpreter")

BASE_URL = "https://ipc.gps555.net/api"
SIGNALING_SERVER = "sig.gps555.net:8882"
BLE_NAME_PREFIX = "ZIOTA_"


async def find_camera(timeout: float = 15.0):
    print(f"Scanning for a BLE device advertising as {BLE_NAME_PREFIX}... ({timeout:.0f}s)")
    devices = await BleakScanner.discover(timeout=timeout)
    candidates = [d for d in devices if d.name and d.name.startswith(BLE_NAME_PREFIX)]
    if not candidates:
        names = sorted({d.name for d in devices if d.name})
        print("No ZIOTA_* device found. Devices seen:", ", ".join(names) or "(none)")
        return None
    for d in candidates:
        print(f"  found {d.name}  [{d.address}]")
    return candidates[0]


def extract_uid(response: bytes) -> str | None:
    """Best-effort UID extraction: the response frame's exact tag/length
    layout was not fully modelled (see ble_ap_packet module docstring), so
    this just looks for the longest run of ASCII digits, which is how the
    UID appeared in the one captured example.
    """
    digit_runs = re.findall(rb"[0-9]{8,15}", response)
    if not digit_runs:
        return None
    return max(digit_runs, key=len).decode("ascii")


async def push_wifi_and_get_uid(address: str, ssid: str, password: str) -> str | None:
    packet = build_ap_info_packet(ssid, password, SIGNALING_SERVER)
    print(f"Built a {len(packet)}-byte provisioning packet")

    responses = bytearray()
    got_notification = asyncio.Event()

    def on_notify(_char, data: bytearray):
        responses.extend(data)
        got_notification.set()

    bytes_sent = 0
    dropped_after_checksum = False
    try:
        async with BleakClient(address) as client:
            print("Connected. Subscribing to notifications...")
            await client.start_notify(NOTIFY_CHAR_UUID, on_notify)

            # The camera drops the BLE link on a fixed budget (observed:
            # always right after the 3rd write, regardless of that write's
            # size) rather than after a fixed byte count -- so the fix is
            # fewer, larger writes, using whatever MTU this connection
            # actually negotiated instead of the phone's 20-byte chunks.
            negotiated = getattr(client, "mtu_size", 23) or 23
            chunk_size = max(BLE_WRITE_CHUNK, negotiated - 3)
            chunks = chunk_for_ble(packet, chunk_size=chunk_size)
            print(f"Negotiated MTU {negotiated} -- sending in {len(chunks)} "
                  f"write(s) of up to {chunk_size} bytes")

            await asyncio.sleep(0.2)  # let the peripheral's BLE stack settle

            print("Writing provisioning packet...")
            for i, chunk in enumerate(chunks):
                await client.write_gatt_char(WRITE_CHAR_UUID, chunk, response=True)
                bytes_sent += len(chunk)
                print(f"  wrote chunk {i + 1}/{len(chunks)} ({len(chunk)} bytes)")

            try:
                await asyncio.wait_for(got_notification.wait(), timeout=10.0)
                await asyncio.sleep(1.5)  # let any follow-up chunks arrive too
            except asyncio.TimeoutError:
                print("No notification received within 10s.")

            await client.stop_notify(NOTIFY_CHAR_UUID)
    except Exception as e:
        # Observed live: the camera drops the BLE link right after the
        # checksum byte, apparently while it pivots its radio to associate
        # with WiFi -- everything up to and including the checksum (all but
        # the final 1-byte terminator chunk) is enough for it to act on.
        # Confirmed by checking the account's device list: the camera came
        # online immediately after a disconnect at exactly this point.
        if bytes_sent >= len(packet) - 1:
            dropped_after_checksum = True
            print(f"BLE link dropped after {bytes_sent}/{len(packet)} bytes "
                  f"({e!r}) -- this matches the point where the camera "
                  "pivots to join WiFi, not a failure. Treating as sent; "
                  "no UID notification will be available this run.")
        else:
            raise

    print(f"Raw response ({len(responses)} bytes): {responses.hex()}")
    return extract_uid(bytes(responses))


def md5_json_get(path: str, token: str, **params) -> dict:
    url = BASE_URL + path
    if params:
        import urllib.parse
        url += "?" + urllib.parse.urlencode({k: str(v) for k, v in params.items()})
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "language": "en",
        "User-Agent": "Dart/3.10 (dart:io)",
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def json_post(path: str, token: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE_URL + path, data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "language": "en",
            "User-Agent": "Dart/3.10 (dart:io)",
            "Content-Type": "application/json",
        })
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def guest_login(username: str, password_md5: str) -> str:
    req = urllib.request.Request(
        BASE_URL + "/v1/login",
        data=json.dumps({
            "username": username, "password": password_md5,
            "loginType": "2", "pushFunc": "1", "pushKey": "", "lang": "en",
        }).encode(),
        headers={"User-Agent": "Dart/3.10 (dart:io)", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        body = json.loads(r.read())
    token = body.get("token") or body.get("data", {}).get("token")
    if not token:
        raise RuntimeError(f"login did not return a token: {body}")
    return token


def bind_camera(token: str, uid: str, reg_code: int = 0) -> dict:
    return json_post("/v1/family/add-ipc", token, {"uid": uid, "force": False, "regCode": reg_code})


async def main_async(args) -> int:
    device = await find_camera()
    if device is None:
        return 1

    uid = await push_wifi_and_get_uid(device.address, args.ssid, args.password)
    if not uid and device.name and device.name.startswith(BLE_NAME_PREFIX):
        # More reliable than the notification anyway: the advertised BLE
        # name is "ZIOTA_<uid>", and the camera routinely drops the BLE
        # link (to join WiFi) before sending a notification back at all.
        uid = device.name[len(BLE_NAME_PREFIX):]
        print(f"No UID from the notification; using the advertised device name instead: {uid}")
    if not uid:
        print("Could not determine a UID from either the notification or "
              "the device name. Check the raw hex above.")
        return 1
    print(f"Camera UID: {uid}")

    print("Logging into the guest account...")
    token = guest_login(args.guest_username, args.guest_password_md5)
    print("Binding camera to account...")
    try:
        result = bind_camera(token, uid)
    except urllib.error.HTTPError as e:
        print(f"add-ipc failed: HTTP {e.code} {e.read()!r}")
        return 1
    print("add-ipc response:", result)
    print("Done. The camera should now be joining your WiFi and will appear "
          "in the device list once online -- check with "
          "`python3 ziot_bridge/ziot_rtp_bridge.py --list-cameras`.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ssid", default=None, help="omit to be prompted")
    ap.add_argument("--password", default=None, help="omit to be prompted (hidden input)")
    ap.add_argument("--guest-username", required=True)
    ap.add_argument("--guest-password-md5", required=True)
    args = ap.parse_args()
    if not args.ssid:
        args.ssid = input("WiFi SSID: ")
    if not args.password:
        while True:
            args.password = getpass.getpass("WiFi password (hidden): ")
            confirm = getpass.getpass("Confirm WiFi password: ")
            if args.password == confirm:
                break
            print("Passwords did not match -- try again.")
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
