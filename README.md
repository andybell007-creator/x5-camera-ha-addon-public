# Home Assistant add-ons for X5 / Z-IOT (gps555.net) IP cameras

Two HAOS Supervisor add-ons that let a cheap TXW817-chip IP camera (sold under
names like "X5", app "Z-IOT CAM", cloud domain `gps555.net`) stream locally
into Home Assistant without the vendor's cloud app in the loop for day-to-day
viewing:

- **`ziot_bridge`** — wraps [`ziot-rtp-bridge`](https://github.com/mauriciobc/ziot-rtp-bridge),
  which logs into the camera's cloud API and re-exposes its video/audio as
  local HTTP/MJPEG streams.
- **`go2rtc`** — takes those local streams and republishes them as RTSP/WebRTC
  for Home Assistant's Generic Camera integration (and Frigate, if used).

This is **not** a generic camera integration — it's specific to this family
of cheap cloud-cam hardware, which has no local RTSP of its own and instead
requires a cloud login to unlock streaming, including a JWT token that
expires roughly every 15 days (see [`token-refresh/`](token-refresh/) for an
optional way to automate that).

## Installing

1. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**,
   add: `https://github.com/andybell007-creator/x5-camera-ha-addon-public`
2. Install **ZIOT RTP Bridge**, open its Configuration tab and set:
   - `token` — a JWT from the camera's cloud API (get this once from the
     vendor app; see [`token-refresh/`](token-refresh/) to automate renewing
     it afterwards)
   - `cameras` — optional filter list, leave empty for all bound cameras
   - `host_network` is already enabled in the add-on manifest
3. Install **go2rtc for ZIOT bridge**, open its Configuration tab and set:
   - `camera_uid` — your camera's device UID (found in the vendor app,
     looks like `052150090450`)
   - `haos_host_ip` — the LAN IP of the machine running Home Assistant OS
     (used as the WebRTC ICE candidate address)
4. Start both add-ons.
5. In Home Assistant, add a **Generic Camera** pointing at the go2rtc
   RTSP stream (`rtsp://<haos-ip>:8554/camera_<your-camera-uid>`) or use its
   WebRTC output directly.

Nothing needs editing or forking — both add-ons render their config from the
options you set in the Home Assistant UI.

## Token refresh

The vendor's JWT token expires roughly every 15 days; the default is to
refresh it by opening the vendor app. [`token-refresh/`](token-refresh/)
documents an optional, unofficial way to automate that via direct API calls
instead, reverse-engineered from the app. It comes with a clear caveat: it's
unofficial and can break if the vendor changes their API.
