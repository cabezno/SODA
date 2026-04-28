import time, requests, sys, os, subprocess
from pathlib import Path

print("Esperando SODA...")
time.sleep(5)

pname = "test_api_v" + str(int(time.time()))
req = {
    "description": "Una API REST en Python (FastAPI) para gestionar inventario de una tienda. Endpoints CRUD para productos (nombre, precio, stock). Usar SQLite en memoria con SQLAlchemy. Incluye un requirements.txt y un main.py configurado para uvicorn en el puerto 8000. Super simple, sin dependencias extra.",
    "project_name": pname
}

print(f"Lanzando {pname}...")
requests.post("http://127.0.0.1:8000/api/run", json=req)
time.sleep(3)

print("Saltando entrevista...")
requests.post("http://127.0.0.1:8000/api/answer", json={"answer": "Todo perfecto. Continuar sin mas detalles."})

print("Monitoreando estado...")
meta = Path("projects") / pname / "metadata.json"
src = Path("projects") / pname / "source"
start = time.time()

while time.time() - start < 300:
    if meta.exists():
        import json
        with open(meta, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"Estado SODA: {data.get('state')}")
            if data.get("state") == "done":
                break
    time.sleep(5)

if not src.exists():
    print("SODA fallo. La carpeta de código no existe.")
    sys.exit(1)

print("\n!!! SODA TERMINO DE PROGRAMAR !!!")
print("Archivos generados:")
for file in src.rglob("*"):
    if file.is_file():
        print(f"  - {file.name}")

print("\nArrancando la API autogenerada...")
req_file = src / "requirements.txt"
main_file = src / "main.py"

if req_file.exists():
    print("Instalando dependencias...")
    subprocess.run(["venv\\Scripts\\python.exe", "-m", "pip", "install", "-r", str(req_file)])

if main_file.exists():
    print("Lanzando Servidor...")
    proc = subprocess.Popen(["venv\\Scripts\\python.exe", str(main_file)])
    time.sleep(4)
    try:
        res = requests.get("http://127.0.0.1:8000/docs", timeout=3)
        if res.status_code == 200:
            print("\n*** EXITO: LA API RESPONDE (Swagger UI detectado) ***")
    except Exception as e:
        print(f"Fallo al contactar API: {e}")
    finally:
        proc.terminate()
