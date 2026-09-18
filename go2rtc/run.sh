#!/bin/sh
# Renders go2rtc.yaml from the Supervisor add-on options, then starts go2rtc.
set -e

CAMERA_UID=$(grep -o '"camera_uid"[[:space:]]*:[[:space:]]*"[^"]*"' /data/options.json | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')
HAOS_HOST_IP=$(grep -o '"haos_host_ip"[[:space:]]*:[[:space:]]*"[^"]*"' /data/options.json | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')

if [ -z "$CAMERA_UID" ] || [ -z "$HAOS_HOST_IP" ]; then
  echo "go2rtc-ziot: camera_uid and haos_host_ip must both be set in the add-on Configuration tab" >&2
  exit 1
fi

sed -e "s#__CAMERA_UID__#${CAMERA_UID}#g" -e "s#__HAOS_HOST_IP__#${HAOS_HOST_IP}#g" \
  /app/go2rtc.yaml.tmpl > /config/go2rtc.yaml

exec go2rtc
