import autogen
import os
from dotenv import load_dotenv

load_dotenv()

def test_gemini_autogen():
    config_list = [
        {
            "model": "gemini-1.5-flash",
            "api_key": os.getenv("GEMINI_API_KEY"),
            "api_type": "google"
        }
    ]
    
    assistant = autogen.AssistantAgent(
        name="assistant",
        llm_config={"config_list": config_list}
    )
    
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1
    )
    
    print("Enviando mensaje de prueba a Gemini vía AutoGen...")
    user_proxy.initiate_chat(assistant, message="Di 'Hola SODA'")

if __name__ == "__main__":
    try:
        test_gemini_autogen()
        print("✅ AutoGen + Gemini: CONEXIÓN EXITOSA")
    except Exception as e:
        print(f"❌ FALLO DE CONEXIÓN: {e}")
