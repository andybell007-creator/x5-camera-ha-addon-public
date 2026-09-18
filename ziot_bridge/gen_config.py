import json
import os

with open("/data/options.json") as f:
    options = json.load(f)

config = {
    "token": options.get("token", ""),
    "port": options.get("port", 8085),
    "cameras": options.get("cameras", []),
}

out_path = "/app/ziot_config.json"
with open(out_path, "w") as f:
    json.dump(config, f)
os.chmod(out_path, 0o600)
