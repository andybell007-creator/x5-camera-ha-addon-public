#!/bin/bash
# Refreshes a ZIOT/gps555.net camera's JWT token via direct API call, with no
# phone or vendor app needed, and pushes it into the ziot_bridge add-on.
#
# Reverse-engineered via static decompilation of the Z-IOT CAM app: it logs
# in with a guest account using a fixed password, md5("666666"). Logging in
# again with the SAME existing guest username mints a fresh token for the
# SAME account, with cameras already bound -- no re-pairing needed.
#
# This talks to an undocumented, unofficial vendor API. It is not affiliated
# with the camera vendor, and the vendor can change or break this at any
# time without notice. Keep the vendor app installed as a fallback.
#
# Required environment variables:
#   HAOS_HOST         LAN IP or hostname of your Home Assistant OS install
#   ADDON_SLUG         ziot_bridge add-on slug, e.g. from `ha addons list`
#                       on HAOS (looks like <repo-hash>_ziot_bridge)
#   GUEST_USERNAME      Your camera's guest account username, e.g.
#                       guest_XXXXXXXXXXXXX -- see README.md in this folder
#                       for how to find it
#
# Optional:
#   SSH_KEY             Path to an SSH key authorised on HAOS's
#                       "Terminal & SSH" add-on (default: ~/.ssh/id_ed25519)
#
# Usage:
#   HAOS_HOST=192.168.1.50 ADDON_SLUG=xxxxxxxx_ziot_bridge \
#     GUEST_USERNAME=guest_XXXXXXXXXXXXX ./refresh_ziot_token.sh

set -euo pipefail

: "${HAOS_HOST:?set HAOS_HOST}"
: "${ADDON_SLUG:?set ADDON_SLUG}"
: "${GUEST_USERNAME:?set GUEST_USERNAME}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
GUEST_PASSWORD_MD5="f379eaf3c831b04de153469d1bec345e"  # md5("666666"), fixed by the app itself -- not account-specific

echo "== Logging in to mint a fresh token =="
RESPONSE=$(curl -s -X POST "https://ipc.gps555.net/api/v1/login" \
  -H "User-Agent: Dart/3.10 (dart:io)" \
  -H "content-type: application/json" \
  -d "{\"username\":\"$GUEST_USERNAME\",\"password\":\"$GUEST_PASSWORD_MD5\",\"loginType\":\"2\",\"pushFunc\":\"1\",\"pushKey\":\"\",\"lang\":\"en\"}")

TOKEN=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")

if [ -z "$TOKEN" ]; then
  echo "FAILED: no token in response:"
  echo "$RESPONSE"
  exit 1
fi

EXPIRE=$(python3 -c "
import base64, json, datetime
p = '$TOKEN'.split('.')[1]
p += '=' * (-len(p) % 4)
d = json.loads(base64.urlsafe_b64decode(p))
print(datetime.datetime.fromtimestamp(d['exp'], tz=datetime.timezone.utc))
")
echo "== Got token, expires $EXPIRE UTC =="

echo "== Pushing new token to Home Assistant add-on =="
ssh -i "$SSH_KEY" -o BatchMode=yes root@"$HAOS_HOST" \
  "curl -s -X POST -H \"Authorization: Bearer \$SUPERVISOR_TOKEN\" -H \"Content-Type: application/json\" \
   -d '{\"options\":{\"token\":\"$TOKEN\"}}' \
   http://supervisor/addons/$ADDON_SLUG/options"

echo ""
echo "== Restarting add-on to apply new token =="
echo "   (avoid running this in a tight loop -- some of these cheap cameras"
echo "    handle repeated abrupt restarts poorly and may drop back into"
echo "    AP/setup mode. A single refresh is fine.)"
ssh -i "$SSH_KEY" -o BatchMode=yes root@"$HAOS_HOST" "ha apps restart $ADDON_SLUG"

echo ""
echo "NEW_EXPIRY_UTC=$EXPIRE"
