import json
import os
from pathlib import Path

config_path = Path.home() / ".docker" / "config.json"
if config_path.exists():
    with open(config_path, "r") as f:
        config = json.load(f)
    
    if config.get("credsStore") == "desktop":
        print("Changing credsStore to wincred")
        config["credsStore"] = "wincred"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=8)
