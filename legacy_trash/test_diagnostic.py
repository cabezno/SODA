import os
import sys
import json
import asyncio
from pathlib import Path
from kernel.execution.project_scaffolder import ProjectScaffolder
from kernel.execution.boot_agent import _detect_commands

async def diagnostic():
    print("=== SODA SYSTEM DIAGNOSTIC ===")
    
    # 1. Check Project 'wordpress_'
    project_id = "wordpress_"
    base_dir = Path("D:/Desktop/iacomp/SODA-PROJECT")
    project_dir = base_dir / "projects" / project_id
    source_dir = project_dir / "source"
    
    print(f"\n--- Project: {project_id} ---")
    if not project_dir.exists():
        print(f"ERROR: Project directory {project_dir} does not exist.")
    else:
        print(f"Project directory exists: {project_dir}")
        
    if not source_dir.exists():
        print(f"ERROR: Source directory {source_dir} does not exist.")
    else:
        print(f"Source directory exists: {source_dir}")
        files = list(source_dir.rglob("*"))
        print(f"Total files in source: {len(files)}")
        
        # Check for manifests
        pkg_json = source_dir / "package.json"
        req_txt = source_dir / "requirements.txt"
        print(f"package.json exists: {pkg_json.exists()}")
        print(f"requirements.txt exists: {req_txt.exists()}")
        
        # Test Scaffolder Detection
        scaffolder = ProjectScaffolder()
        detected_stack = scaffolder._detect_stack(source_dir, [])
        print(f"Scaffolder detected stack: {detected_stack}")
        
        # Test BootAgent Detection
        arch_path = project_dir / "architecture.json"
        arch = {}
        if arch_path.exists():
            arch = json.loads(arch_path.read_text(encoding="utf-8"))
        
        install_cmd, run_cmd, boot_stack = _detect_commands(source_dir, arch)
        print(f"BootAgent detected stack: {boot_stack}")
        print(f"Install command: {install_cmd}")
        print(f"Run command: {run_cmd}")

    # 2. Check AI Drivers
    print("\n--- AI Drivers ---")
    try:
        from kernel.drivers.provider_hub import AIProviderHub
        from kernel.drivers.gemini_driver import GeminiDriver
        from kernel.drivers.ollama_driver import OllamaDriver
        from dotenv import load_dotenv
        load_dotenv()
        
        gemini_key = os.getenv("GEMINI_API_KEY")
        print(f"GEMINI_API_KEY: {'[SET]' if gemini_key else '[MISSING]'}")
        
        if gemini_key:
            gemini = GeminiDriver(api_key=gemini_key)
            # We won't call it to avoid costs/tokens, just check if it can be initialized
            print("Gemini driver initialized.")
            
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        print(f"OLLAMA_BASE_URL: {ollama_url}")
        # Test connection to Ollama
        import requests
        try:
            resp = requests.get(f"{ollama_url}/api/tags", timeout=2)
            if resp.status_code == 200:
                models = [m['name'] for m in resp.json().get('models', [])]
                print(f"Ollama connected. Available models: {models}")
            else:
                print(f"Ollama returned status {resp.status_code}")
        except Exception as e:
            print(f"Ollama connection failed: {e}")
            
    except Exception as e:
        print(f"AI Drivers check failed: {e}")

    # 3. Check Docker
    print("\n--- Docker Sandbox ---")
    try:
        import docker
        client = docker.from_env()
        print(f"Docker connected: {client.ping()}")
        containers = client.containers.list()
        print(f"Running containers: {len(containers)}")
    except Exception as e:
        print(f"Docker check failed: {e}")

    # 4. Check Git
    print("\n--- Git ---")
    try:
        import subprocess
        res = subprocess.run(["git", "version"], capture_output=True, text=True)
        print(f"Git version: {res.stdout.strip()}")
    except Exception as e:
        print(f"Git check failed: {e}")

    print("\n=== DIAGNOSTIC COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(diagnostic())
