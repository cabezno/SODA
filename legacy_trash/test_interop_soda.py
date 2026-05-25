import asyncio
import json
import re
from kernel.drivers.gemini_driver import GeminiDriver

async def test_ia_interop():
    gemini = GeminiDriver()
    
    print("=== TEST DE INTEROPERABILIDAD SODA (MODERNO) ===")
    
    # PASO 1: EL ARQUITECTO (Gemini 3.1 Pro)
    print("\n1. [Arquitecto: Gemini 3.1 Pro] Generando Contrato...")
    prompt_arch = (
        "Genera un contrato técnico en JSON para un módulo de 'Validador de Transacciones Cripto'. "
        "Debe incluir una interfaz con inputs (monto, wallet_id, firma) y outputs. "
        "Genera SOLO el JSON puro, sin markdown."
    )
    try:
        res_arch = await gemini.call(
            system_prompt="Eres el Arquitecto Senior de SODA. Genera solo JSON.",
            user_message=prompt_arch,
            model="gemini-3.1-pro-preview"
        )
        contrato_raw = res_arch.content
        contrato_match = re.search(r'\{.*\}', contrato_raw, re.DOTALL)
        if not contrato_match:
            print(f"  ❌ Error: No se encontró JSON en la respuesta.")
            return
        contrato = contrato_match.group(0)
        print("  ↳ Contrato generado con éxito.")
    except Exception as e:
        print(f"  ❌ Error en Arquitecto: {e}")
        return

    # PASO 2: EL PROGRAMADOR (Gemini 3 Flash - Simulando rapidez de DeepSeek)
    print("\n2. [Programador: Gemini 3 Flash] Implementando Código...")
    prompt_coder = f"Implementa este contrato técnico en Python. Respeta exactamente nombres y tipos:\n{contrato}"
    try:
        res_coder = await gemini.call(
            system_prompt="Eres el Programador Experto de SODA. Escribe solo el código Python encapsulado en <CODE></CODE>.",
            user_message=prompt_coder,
            model="gemini-3-flash-preview" 
        )
        codigo = res_coder.content
        print(f"  ↳ Código implementado con {res_coder.model_used}.")
    except Exception as e:
        print(f"  ❌ Error en Programador: {e}")
        return

    # PASO 3: EL AUDITOR (Gemini 3.1 Pro - Juez de Calidad)
    print("\n3. [Auditor: Gemini 3.1 Pro] Verificando consistencia...")
    prompt_audit = (
        f"Compara este CONTRATO con este CÓDIGO.\n\n"
        f"CONTRATO:\n{contrato}\n\n"
        f"CÓDIGO:\n{codigo}\n\n"
        "Responde con JSON: {\"match\": true/false, \"analisis\": \"...\"}"
    )
    try:
        res_audit = await gemini.call(
            system_prompt="Eres el Auditor de SODA. Detecta discrepancias de comunicación.",
            user_message=prompt_audit,
            model="gemini-3.1-pro-preview"
        )
        print(f"\nRESULTADO FINAL DE INTEROPERABILIDAD:")
        print(res_audit.content)
    except Exception as e:
        print(f"  ❌ Error en Auditor: {e}")

if __name__ == "__main__":
    asyncio.run(test_ia_interop())
