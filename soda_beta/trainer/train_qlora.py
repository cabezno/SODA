#!/usr/bin/env python3
import os
import sys
import torch
from pathlib import Path

# Force UTF-8 on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"

def train_qlora(
    dataset_path: str,
    base_model_name: str = "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    output_dir: str = "soda_beta/trainer/soda_adapters",
    epochs: int = 3,
    batch_size: int = 1,
    learning_rate: float = 2e-4
):
    print("================================================================================")
    print("                 SODA BETA LOCAL TRAINING PIPELINE (QLoRA)")
    print("================================================================================")
    print(f"Dispositivo de hardware detectado: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU (⚠️ ALERTA: Requiere GPU CUDA)'}")
    print(f"Cargando dataset desde: {dataset_path}")
    print(f"Modelo base: {base_model_name}")

    if not torch.cuda.is_available():
        print("ERROR CRÍTICO: CUDA no está disponible. El entrenamiento QLoRA local requiere una GPU NVIDIA.")
        sys.exit(1)

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from datasets import load_dataset
        from trl import SFTTrainer
    except ImportError:
        print("ERROR: Librerías necesarias para entrenamiento no encontradas. Ejecuta:")
        print("  pip install transformers peft datasets trl bitsandbytes accelerate")
        sys.exit(1)

    # 1. Configuración de Cuantización (Ahorro estricto de VRAM < 6GB)
    print("[1/5] Configurando cuantización de 4 bits para bitsandbytes...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True
    )

    # 2. Carga del Modelo Base y Tokenizador
    print("[2/5] Cargando modelo base y tokenizador (espacio latente)...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )

    # Preparación para entrenamiento en 4 bits
    model = prepare_model_for_kbit_training(model)
    model.gradient_checkpointing_enable() # Ahorro extremo de VRAM

    # 3. Configuración de LoRA (Adaptador de Peso Bajo)
    print("[3/5] Creando adaptador LoRA (PEFT)...")
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # 4. Carga y Procesamiento del Dataset
    print("[4/5] Cargando y formateando dataset JSONL...")
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    def format_prompts(batch):
        formatted = []
        for inst, inp, out in zip(batch["instruction"], batch["input"], batch["output"]):
            text = f"<|im_start|>system\n{inst}<|im_end|>\n<|im_start|>user\n{inp}<|im_end|>\n<|im_start|>assistant\n{out}<|im_end|>"
            formatted.append(text)
        return {"text": formatted}

    dataset = dataset.map(format_prompts, batched=True)

    # 5. Argumentos de Entrenamiento y Ejecución del Trainer
    print("[5/5] Iniciando bucle de SFTTrainer...")
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        max_steps=100, # Bucle corto de optimización local
        learning_rate=learning_rate,
        bf16=True,
        logging_steps=10,
        save_strategy="steps",
        save_steps=50,
        report_to="none" # Sin telemetrías externas en local
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=1536, # Límites estrictos para no saturar atención
        packing=False,
        args=training_args
    )

    # Desactivar cache para forzar entrenamiento
    model.config.use_cache = False

    print("--- INICIANDO FINE-TUNING LOCAL DE SODA BETA ---")
    trainer.train()

    # Guardar adaptador entrenado
    adapter_path = Path(output_dir) / "soda_final_adapter"
    trainer.model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    print(f"🎉 ¡ENTRENAMIENTO COMPLETADO CON ÉXITO! Adaptador LoRA guardado en: {adapter_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python train_qlora.py <ruta_al_dataset_jsonl>")
        sys.exit(1)
    train_qlora(sys.argv[1])
