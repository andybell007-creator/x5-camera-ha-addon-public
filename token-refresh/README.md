# Automated token refresh (optional, unofficial)

`ziot_bridge` needs a JWT token from the camera vendor's cloud API, and that
token expires roughly every 15 days. The normal way to get a new one is to
open the Z-IOT CAM app and let it log in. This script does that same login
automatically, so you don't have to.

**This is unofficial and reverse-engineered.** It calls an undocumented
vendor API endpoint (found via static decompilation of the app, not from any
published documentation), using the same fixed guest password the app itself
uses. It is not affiliated with, endorsed by, or supported by the camera
vendor. The vendor can change or break this at any time without notice — if
it stops working, fall back to refreshing via the app. Use at your own risk.

## Prerequisites

1. **Pair the camera normally first**, using the vendor app, at least once.
   This creates a guest account (`guest_XXXXXXXXXXXXX`) bound to your camera.
   There isn't a documented way to mint a new guest account and bind a
   camera to it without the app, so this script only *refreshes* an
   existing pairing — it doesn't replace initial setup.
2. **Find your `GUEST_USERNAME`.** The app doesn't display this directly in
   its UI. The most reliable way is a one-time traffic capture while the app
   logs in (e.g. with `mitmproxy` on a WireGuard tunnel, or any HTTPS proxy
   you route the phone through) — look for the `username` field in the
   `POST /api/v1/login` request body, format `guest_<digits>`.
3. **SSH access to Home Assistant OS.** Install the official "Terminal &
   SSH" add-on, add your public key to its `authorized_keys` option, and
   confirm you can `ssh root@<your-haos-ip>` non-interactively.
4. **Find your `ADDON_SLUG`.** Run `ha addons list` (or `ha store apps list
   --raw-json`) over SSH on HAOS and look for the `ziot_bridge` add-on —
   its slug is prefixed with a repository hash, e.g.
   `a1b2c3d4_ziot_bridge`.

## Usage

```bash
HAOS_HOST=192.168.1.50 \
ADDON_SLUG=a1b2c3d4_ziot_bridge \
GUEST_USERNAME=guest_XXXXXXXXXXXXX \
./refresh_ziot_token.sh
```

Run it a couple of days before the current token expires (decode the token's
`exp` claim, or just re-run every ~10-12 days). On Linux/macOS you can
schedule it with `cron`; there's nothing HAOS-specific about the script
itself besides the SSH/Supervisor push step at the end.

**Caution:** each add-on restart briefly disrupts the camera's active
session. Avoid restarting the add-on more than a single refresh needs —
don't loop it.
