import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from kernel.communication.telegram_gateway import TelegramGateway

async def test_telegram_emission():
    """
    Script de diagnóstico para verificar la emisión de Telegram.
    Requiere TELEGRAM_BOT_TOKEN y telegram_chat_id configurados.
    """
    # 1. Cargar entorno
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("❌ ERROR: No se encontró TELEGRAM_BOT_TOKEN en el .env")
        return

    print(f"--- Iniciando Test de Emisión Telegram ---")
    tg = TelegramGateway()
    
    if not tg._chat_id:
        print("⚠️ ADVERTENCIA: No hay chat_id vinculado en soda_config.json.")
        print("   Vincule su bot primero o configure el ID manualmente para este test.")
        return

    print(f"✅ Bot Token detectado.")
    print(f"✅ Chat ID detectado: {tg._chat_id}")

    # 2. Probar envío simple
    print("\n[1/3] Enviando mensaje de texto simple...")
    success = await tg.send("🚀 SODA FUSION: Test de emisión iniciado.")
    if success:
        print("   - Mensaje encolado exitosamente.")
    else:
        print("   - Fallo al encolar mensaje.")

    # 3. Probar evento de PREGUNTA (Simulación)
    print("\n[2/3] Enviando evento USER_QUESTION...")
    await tg.send_event("USER_QUESTION", "Este es un test de pregunta. ¿Recibes esto?", {"question": "Test de pregunta"})
    print("   - Evento de pregunta enviado.")

    # 4. Probar evento DONE con botones
    print("\n[3/3] Enviando evento DONE con botones interactivos...")
    await tg.send_event("DONE", "✅ Test completado. Proyecto 'TEST_FUSION' listo.", {"project_id": "TEST_FUSION"})
    print("   - Evento DONE enviado.")

    print("\n--- Test Finalizado ---")
    print("Verifica tu Telegram. Deberías haber recibido 3 mensajes.")
    print("(Nota: El trabajador de envío tarda unos segundos en procesar la cola)")
    
    # Dar tiempo al worker para procesar antes de cerrar el script
    await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(test_telegram_emission())
