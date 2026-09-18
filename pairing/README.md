# App-free camera pairing (optional, unofficial)

Pairs a new X5 / Z-IOT CAM camera to your account entirely from a computer —
no vendor app, no phone — using this Mac/PC's own Bluetooth radio.

**This is unofficial and reverse-engineered**, the same way
[`token-refresh/`](../token-refresh/) is: recovered from a live capture of
the real app's Bluetooth traffic during an actual pairing session
(via Android's Bluetooth HCI snoop log, pulled with `adb bugreport`), not
from any published protocol documentation. It is not affiliated with,
endorsed by, or supported by the camera vendor, and the vendor can change
this at any time without notice. Verified working against real hardware,
but treat every run as a test.

**Heads-up on privacy**: the camera's own BLE pairing protocol sends your
WiFi SSID and password to the camera in plain text over Bluetooth — no
encryption at the application layer, and standard BLE pairing (no bonding)
at the link layer either. That's true of the vendor's own app too; this
tool doesn't add or remove that exposure, just replaces who's sending it.

## What it does

1. **BLE**: scans for the camera's own Bluetooth advertisement
   (`ZIOTA_<uid>`), connects, and writes your WiFi SSID/password plus the
   vendor's signaling-server address to the camera's custom GATT
   characteristic — the same bytes the vendor app itself would send.
2. **Cloud HTTP**: logs into a guest account (see
   [`token-refresh/README.md`](../token-refresh/README.md) for how to get
   one) and binds the camera's UID to that account via `POST
   /v1/family/add-ipc`, so it shows up in your device list.

The camera reliably drops the BLE connection right around the last write
(observed: consistently after receiving the checksummed payload,
apparently while it pivots its radio to associate with WiFi) — the script
treats that as expected rather than a failure, and falls back to reading
the UID from the BLE advertised name if the notification response wasn't
fully received in time.

See [`ble_ap_packet.py`](ble_ap_packet.py)'s module docstring for the full
byte-level frame layout this was reverse-engineered to.

## Prerequisites

- Python 3.10+ with [`bleak`](https://pypi.org/project/bleak/) installed
  (`pip install bleak`). On macOS this needs to build `pyobjc-core`, which
  failed under an old system Python in testing — a recent Python (3.12+)
  avoided the issue.
- A guest account already paired to at least one camera (see
  [`token-refresh/`](../token-refresh/)) — this only automates *adding*
  another camera, not creating the account from scratch.
- The camera in Bluetooth pairing mode (see its manual for the button
  sequence — this varies by camera, and a factory reset may be needed if
  it was previously paired, since pairing mode alone may not clear
  previously-saved WiFi credentials).

## Usage

```bash
python3 pair_camera.py \
  --guest-username guest_XXXXXXXXXXXXX \
  --guest-password-md5 <md5 of "666666">
```

It prompts for your WiFi SSID and password (hidden input, with
confirmation) rather than taking them as arguments, so they don't end up
in your shell history.
