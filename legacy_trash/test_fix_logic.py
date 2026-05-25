import re
import importlib.util
from pathlib import Path

def test_fix():
    raw_output = "ModuleNotFoundError: No module named 'sendgrid'"
    missing = set()
    pattern = re.compile(r"No module named ['\"]?([\w]+)['\"]?")
    
    for m in pattern.finditer(raw_output):
        print(f"Found match: {m.group(1)}")
        missing.add(m.group(1).lower())
    
    _MODULE_TO_PACKAGE = {"sendgrid": "sendgrid"}
    to_add = []
    
    for mod in sorted(missing):
        print(f"Checking module: {mod}")
        try:
            spec = importlib.util.find_spec(mod)
            print(f"Spec for {mod}: {spec}")
            if spec is not None:
                print(f"Skipping {mod} because it is already importable.")
                continue
        except Exception as e:
            print(f"Error checking {mod}: {e}")
            
        pkg = _MODULE_TO_PACKAGE.get(mod, mod)
        print(f"Package to add: {pkg}")
        to_add.append(pkg)
        
    print(f"Final list to add: {to_add}")

if __name__ == "__main__":
    test_fix()
