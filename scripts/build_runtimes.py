import sys
from pathlib import Path

# Añadir el raíz al path para poder importar el kernel
sys.path.append(str(Path(__file__).resolve().parent.parent))

from kernel.execution.runtime_manager import RuntimeManager

def main():
    manager = RuntimeManager()
    runtimes = manager.list_available_runtimes()
    
    print(f"SODA Runtime Builder")
    print(f"====================")
    print(f"Available runtimes: {', '.join(runtimes)}\n")
    
    for key in runtimes:
        if manager.is_runtime_ready(key):
            print(f"[OK] Runtime '{key}' is already built.")
        else:
            print(f"[..] Building runtime '{key}'...")
            try:
                manager.build_runtime(key)
                print(f"[SUCCESS] Runtime '{key}' built successfully.\n")
            except Exception as e:
                print(f"[ERROR] Failed to build '{key}': {str(e)}\n")

if __name__ == "__main__":
    main()
