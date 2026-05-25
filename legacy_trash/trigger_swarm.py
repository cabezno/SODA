import requests
import sys

def launch():
    url = "http://127.0.0.1:8000/api/run"
    payload = {
        "description": "Crea un script en Python que lea un archivo de texto, cuente cuantas veces aparece cada palabra y muestre el top 5.",
        "project_name": "TEST_SWARM_FINAL"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(response.json())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    launch()
