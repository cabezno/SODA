import time, requests, sys, os, subprocess
from pathlib import Path

pname = "test_cli_definitiva"
print(f"--> [PILOTO] Lanzando proyecto: {pname}")

req = {
    "description": "Script CLI en Python puro. Debe preguntar el nombre al usuario por consola, imprimir 'Hola [nombre]' y añadir el nombre con la fecha actual a un archivo llamado historial.txt. Proyecto rapido.",
    "project_name": pname
}

try:
    requests.post("http://127.0.0.1:8000/api/run", json=req, timeout=10)
except Exception as e:
    print(f"--> [PILOTO ERROR] No se pudo conectar a SODA: {e}")
    sys.exit(1)

meta_file = Path(f"projects/{pname}/metadata.json")
start = time.time()
answered = False
estado_previo = ""

while time.time() - start < 400: # Max 6.5 minutos
    # 1. Chequear si SODA pregunta algo en la entrevista
    if Path("log_definitivo.log").exists() and not answered:
        with open("log_definitivo.log", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if "Asking user" in content or "Esperando confirm" in content:
                print("--> [PILOTO] Respondiendo a la Entrevista (Continuar)...")
                requests.post("http://127.0.0.1:8000/api/answer", json={"answer": "Continuar y Generar"})
                answered = True
                
    # 2. Monitorear la maquina de estados de SODA
    if meta_file.exists():
        import json
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            estado_actual = data.get("state", "")
            if estado_actual != estado_previo:
                print(f"--> [SODA ESTADO] Cambio a: {estado_actual.upper()}")
                estado_previo = estado_actual
                
            if estado_actual == "done":
                print("--> [PILOTO] SODA reporta proyecto DONE. Simulando clic en 'EJECUTAR'...")
                break
        except: pass
    time.sleep(5)

# 3. Ejecucion Final del Codigo
src_dir = Path(f"projects/{pname}/source")
main_py = src_dir / "main.py"

print("\n=======================================================")
if main_py.exists():
    print(f"--> [PILOTO] Ejecutando: python {main_py.name}")
    try:
        # Simulamos que un usuario escribe "UsuarioDePrueba" en la consola
        res = subprocess.run(
            ["venv\\Scripts\\python.exe", str(main_py)], 
            input=b"UsuarioDePrueba\n", 
            capture_output=True, 
            text=True,
            timeout=10
        )
        print("[SALIDA ESTANDAR]")
        print(res.stdout)
        if res.stderr:
            print("[ERRORES]")
            print(res.stderr)
            
        historial = src_dir / "historial.txt"
        if historial.exists():
            print(f"\n[VALIDACION] El archivo historial.txt existe. Contenido:")
            print(historial.read_text(encoding="utf-8"))
        else:
            print("\n[VALIDACION FALLIDA] No se creo historial.txt")
            
    except subprocess.TimeoutExpired:
        print("[ERROR] El script se colgo esperando input o en un bucle infinito.")
else:
    print("--> [PILOTO ERROR] No se encontro main.py. SODA no termino correctamente.")
print("=======================================================")
