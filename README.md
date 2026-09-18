# Home Assistant add-ons for X5 / Z-IOT (gps555.net) IP cameras

Two HAOS Supervisor add-ons that let a cheap TXW817-chip IP camera (sold under
names like "X5", app "Z-IOT CAM", cloud domain `gps555.net`) stream locally
into Home Assistant without the vendor's cloud/app in the loop:

- **`ziot_bridge`** — wraps [`ziot-rtp-bridge`](https://github.com/mauriciobc/ziot-rtp-bridge),
  which logs into the camera's cloud API and re-exposes its video/audio as
  local HTTP/MJPEG streams.
- **`go2rtc`** — takes those local streams and republishes them as RTSP/WebRTC
  for Home Assistant's Generic Camera integration (and Frigate, if used).

This is **not** a generic camera integration — it's specific to this family
of cheap cloud-cam hardware, which has no local RTSP of its own and instead
requires a cloud login to unlock streaming, including a JWT token that
expires roughly every 15 days.

This is the `main` branch: a genericised template with placeholders instead
of any real network details. My own working configuration (with real IPs
and camera ID filled in) lives on the [`my-setup`](../../tree/my-setup)
branch and is not meant to be reused directly by anyone else.

## Values you MUST change for your own setup

| File | Placeholder | Replace with |
|---|---|---|
| `repository.yaml` | `YOUR_GIT_SERVER_IP` | The address HAOS should pull this repo from (e.g. a LAN `git://` daemon, or a real GitHub URL if you host it there instead) |
| `go2rtc/go2rtc.yaml` | `YOUR_HAOS_HOST_IP` | The LAN IP of the machine running Home Assistant OS, used as the WebRTC ICE candidate address |
| `go2rtc/go2rtc.yaml` | `YOUR_CAMERA_UID` (×4) | Your camera's device UID (found in the vendor app, e.g. `052150090450`) |

Not in this repo, and set instead via the Supervisor add-on's **Configuration**
tab in the Home Assistant UI after installing:

- `token` — a JWT obtained by logging into the camera's cloud API (see the
  reverse-engineered guest-login flow if you want to automate refreshing it
  yourself rather than using the vendor app)
- `port` — local port the bridge listens on (default `8085`)
- `cameras` — optional camera filter list

## Installing

1. Fork or copy this repo, fill in the placeholders above.
2. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**,
   add the URL from your edited `repository.yaml`.
3. Install `ZIOT RTP Bridge` and `go2rtc`, set the bridge's `token`/`cameras`
   options, enable `host_network`, start both.
4. Add a Generic Camera in Home Assistant pointing at the go2rtc RTSP/WebRTC
   stream.
