import requests

def test_soda():
    print("Enviando petición a SODA...")
    payload = {
        "description": "Crea una API en Python usando FastAPI. Debe tener una única ruta en / que devuelva el texto puro 'hola soda'. Nada complejo."
    }
    
    try:
        response = requests.post("http://127.0.0.1:8000/api/run", json=payload, timeout=10)
        print("Status:", response.status_code)
        print("Response:", response.json())
    except Exception as e:
        print("Error al contactar con SODA:", e)

if __name__ == "__main__":
    test_soda()