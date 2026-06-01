#!/usr/bin/env python3
import os
import sys
import time
import torch
from pathlib import Path

# Force UTF-8 on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"


def run_local_evaluation(
    adapter_dir: str = "soda_beta/trainer/soda_adapters/soda_final_adapter",
    base_model_name: str = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
):
    print("================================================================================")
    print("                 SODA BETA LOCAL INFERENCE & EVALUATION TEST")
    print("================================================================================")
    print(f"CUDA disponible: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Dispositivo activo: {torch.cuda.get_device_name(0)}")

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel
    except ImportError:
        print("ERROR: Librerías 'transformers' o 'peft' no encontradas.")
        print("Instálalas ejecutando: pip install transformers peft bitsandbytes accelerate")
        sys.exit(1)

    # 1. Load Tokenizer
    print(f"\n[1/4] Cargando Tokenizador para {base_model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)

    # 2. Configure 4-bit Quantization (RTX 5070 Ti VRAM optimized)
    print("[2/4] Configurando bitsandbytes de 4 bits (VRAM ~1.2 GB)...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True
    )

    # 3. Load Model (Base or Peft Adapter)
    print(f"[3/4] Cargando Modelo Base {base_model_name}...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True
        )
    except Exception as e:
        print(f"ERROR cargando el modelo base. Asegúrate de tener conexión o caché caliente: {e}")
        sys.exit(1)

    # Check if a trained adapter exists
    adapter_path = Path(adapter_dir)
    if adapter_path.exists():
        print(f"--> [OK] Detectado adaptador LoRA entrenado en: {adapter_path}")
        print("--> Aplicando adaptador LoRA en caliente en la GPU...")
        try:
            model = PeftModel.from_pretrained(model, str(adapter_path))
            print("--> ¡Adaptador aplicado de manera exitosa!")
        except Exception as e:
            print(f"⚠️ Alerta aplicando adaptador (corriendo con modelo base): {e}")
    else:
        print("--> [Aviso] No se detectó adaptador entrenado. Corriendo en modo base (Prueba en Seco).")

    # 4. Generate Mock Decompression Task
    print("\n[4/4] Formulando tarea de prueba (Descompresión de Etiqueta Estructural)...")
    
    mock_tag = {
        "tag_id": "soda-tag-vortex-simple",
        "archivo": "vortex_simple.py",
        "sinopsis": "Modulo para verificar latencias de renderizado en Vulkan.",
        "imports": ["time", "sys"],
        "interfaces": {
            "funciones_standalones": [
                "async def check_gpu_latency(): \"Retorna la latencia de Vulkan\" [Fluido: Try-Except -> Llama a time.time() -> Retorna]"
            ]
        }
    }

    # Format the prompt identical to SODA Beta training
    instruction = "Descomprime esta Etiqueta Estructural y genera exclusivamente su código de producción correspondiente. No agregues explicaciones."
    prompt = f"<|im_start|>system\n{instruction}<|im_end|>\n<|im_start|>user\nEtiqueta Estructural:\n{json_dumps_custom(mock_tag)}<|im_end|>\n<|im_start|>assistant\n"

    print("\n--- PROMPT ENVIADO AL SLM LOCAL ---")
    print(prompt)
    print("-----------------------------------")

    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    print("\nEjecutando inferencia local...")
    start_time = time.time()
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.0, # Greedy Deterministic
            top_p=1.0,
            repetition_penalty=1.15,
            pad_token_id=tokenizer.eos_token_id
        )

    end_time = time.time()
    latency = end_time - start_time
    
    # Decode output
    full_output = tokenizer.decode(outputs[0], skip_special_tokens=False)
    
    # Extract assistant's response
    response_start = full_output.find("<|im_start|>assistant\n")
    if response_start != -1:
        assistant_response = full_output[response_start + len("<|im_start|>assistant\n"):]
        # Strip any trailing end token
        assistant_response = assistant_response.replace("<|im_end|>", "").strip()
    else:
        assistant_response = full_output

    generated_tokens = len(outputs[0]) - len(inputs[0])
    tokens_per_second = generated_tokens / latency if latency > 0 else 0

    print("\n================== RESPUESTA GENERADA ==================")
    print(assistant_response)
    print("========================================================")
    print(f"\nMÉTRICAS DE TELEMETRÍA LOCAL:")
    print(f"- Latencia de Generación: {latency:.3f} segundos")
    print(f"- Tokens Generados: {generated_tokens}")
    print(f"- Velocidad de Inferencia: {tokens_per_second:.1f} tokens/segundo")
    print("========================================================")


def json_dumps_custom(obj: dict) -> str:
    """Helper to dump JSON beautifully."""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except NameError:
        import json
        return json.dumps(obj, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run_local_evaluation()
