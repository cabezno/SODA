import time
import requests
import sys
import subprocess
from pathlib import Path

# 1. Saltar entrevista
print("--> Saltando entrevista para acelerar...")
try:
    requests.post("http://127.0.0.1:8000/api/answer", json={"answer": "Todo bien, usar SQLite en memoria. Continuar sin mas detalles."}, timeout=10)
    requests.post("http://127.0.0.1:8000/api/answer", json={"answer": "Continuar sin más detalles"}, timeout=10)
except Exception:
    pass

# 2. Esperar a que la carpeta se cree y el proyecto termine (max 10 mins)
source_dir = Path("projects/test_inventario_fastapi/source")
metadata_file = Path("projects/test_inventario_fastapi/metadata.json")

print("--> SODA esta programando la API. Esperando a que el estado sea 'done'...")
start_wait = time.time()
while time.time() - start_wait < 600:
    if metadata_file.exists():
        import json
        with open(metadata_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("state") == "done":
                print("--> SODA ha terminado. El codigo esta listo.")
                break
    time.sleep(5)
else:
    print("--> SODA no termino a tiempo o el proceso sigue en curso.")
    sys.exit(1)

# 3. Ejecutar la app generada por SODA y probarla
print("--> Levantando la aplicacion generada...")
main_file = source_dir / "main.py"
if main_file.exists():
    # Instalar requerimientos primero
    req_file = source_dir / "requirements.txt"
    if req_file.exists():
        print("--> Instalando dependencias generadas...")
        subprocess.run(["venv\\Scripts\\python.exe", "-m", "pip", "install", "-r", str(req_file)])
    
    # Lanzar la API en un proceso
    api_process = subprocess.Popen(["venv\\Scripts\\python.exe", str(main_file)])
    print("--> Esperando 5 segundos a que Uvicorn levante...")
    time.sleep(5)
    
    # Hacer una peticion a la API inventada por SODA
    print("--> Consultando el endpoint /docs de la nueva API...")
    try:
        res = requests.get("http://127.0.0.1:8000/docs", timeout=5)
        if res.status_code == 200:
            print("========================================")
            print("¡EXITO TOTAL! La API generada por SODA esta viva y respondiendo.")
            print("========================================")
        else:
            print(f"La API respondio, pero con error: {res.status_code}")
    except Exception as e:
        print(f"Error al contactar la API de SODA: {e}")
    finally:
        api_process.terminate()
else:
    print("--> SODA no genero el archivo main.py.")

