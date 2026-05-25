import time, requests, sys, os
from pathlib import Path

def notify_pilot(msg):
    print(f"--> [PILOTO] {msg}")

notify_pilot("Esperando arranque de SODA...")
time.sleep(6)

pname = "test_informe_final"
req = {
    "description": "Una aplicacion CLI simple en Python que pida el nombre al usuario y guarde un saludo con la fecha y hora en un archivo log_saludos.txt. Super veloz.",
    "project_name": pname
}

notify_pilot(f"Iniciando proyecto: {pname}")
requests.post("http://127.0.0.1:8000/api/run", json=req)

answered_wisdom = False
answered_details = False
answered_execute = False

start_time = time.time()
while time.time() - start_time < 600: # 10 minutos max
    if not Path("informe_final.log").exists():
        time.sleep(1)
        continue
        
    with open("informe_final.log", "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
        
    for line in lines:
        # 1. Responder a la entrevista Wisdom
        if ("Asking user" in line or "Responde aqu" in line) and not answered_wisdom:
            notify_pilot("Deteccion de preguntas iniciales. Respondiendo...")
            time.sleep(3)
            requests.post("http://127.0.0.1:8000/api/answer", json={"answer": "Todo claro, no necesita configuracion extra."})
            answered_wisdom = True
            
        # 2. Responder al nuevo boton "Detalles de usuario"
        if "Detalles de usuario" in line and "prefieres continuar" in line and not answered_details:
            notify_pilot("Deteccion de boton 'Detalles de usuario'. Presionando 'Continuar'...")
            time.sleep(3)
            requests.post("http://127.0.0.1:8000/api/answer", json={"answer": "Continuar sin más detalles"})
            answered_details = True
            
        # 3. Esperar al boton final de EJECUTAR
        if "Ejecutar" in line and "done" in line.lower() and not answered_execute:
            notify_pilot("!!! SODA AVISA QUE EL PROYECTO ESTA LISTO !!!")
            notify_pilot("Presionando boton 'EJECUTAR'...")
            time.sleep(5)
            # En la UI de SODA, la ejecucion manual suele ser un comando de interaccion o un endpoint especifico
            # Simularemos el comando de ejecucion
            requests.post("http://127.0.0.1:8000/api/execute", json={"project_id": pname})
            answered_execute = True
            
    if answered_execute:
        notify_pilot("Ciclo completado. Esperando un momento para capturar logs finales...")
        time.sleep(15)
        notify_pilot("Prueba terminada con exito.")
        sys.exit(0)
        
    time.sleep(5)

notify_pilot("Timeout alcanzado.")
