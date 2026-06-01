from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from soda_beta.observatory.packetizer import StructuralPacketizer

logger = logging.getLogger(__name__)


class DatasetCompiler:
    """
    SODA Beta Dataset Compiler.
    Transforms physical source files and logs into training pairs (JSONL) 
    for the Dual-Layer Compression and Decompression learning model.
    """

    def __init__(self, workspace_dir: Path, output_dir: Path):
        self.workspace = Path(workspace_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.packetizer = StructuralPacketizer()

    def compile_from_source_folder(self, source_dir: Path, dataset_name: str = "compiled_dataset.jsonl") -> int:
        """
        Scans a physical directory, compiles its files into Dual-Ended training pairs:
        1. Compresión: Code -> Structural Tag
        2. Descompresión: Structural Tag -> Code
        """
        source_path = Path(source_dir)
        if not source_path.exists():
            logger.error(f"Source path {source_dir} does not exist.")
            return 0

        compiled_pairs: List[Dict[str, Any]] = []
        files = list(source_path.rglob("*.py")) # We prioritize Python for the local Beta

        self._log(f"Compilando {len(files)} archivos desde {source_path}...")

        for f in files:
            try:
                code_content = f.read_text(encoding="utf-8", errors="ignore")
                if not code_content.strip():
                    continue

                rel_path = str(f.relative_to(source_path))
                
                # Generate Structural Tag (La Etiqueta)
                tag = self.packetizer.generate_structural_tag(
                    filepath=rel_path,
                    code=code_content,
                    gist=f"Modulo de producción para {f.name} en el ecosistema."
                )

                tag_json = json.dumps(tag, ensure_ascii=False, indent=2)

                # Pair A: COMPRESIÓN (Code -> Tag)
                pair_compress = {
                    "instruction": "Comprime este código fuente y genera exclusivamente su Etiqueta Estructural en formato JSON.",
                    "input": f"Archivo: {rel_path}\n\nCódigo Fuente:\n```python\n{code_content}\n```",
                    "output": tag_json,
                    "metadata": {"type": "compression", "file": rel_path}
                }

                # Pair B: DESCOMPRESIÓN (Tag -> Code)
                pair_decompress = {
                    "instruction": "Descomprime esta Etiqueta Estructural y genera exclusivamente su código de producción correspondiente. No agregues explicaciones.",
                    "input": f"Etiqueta Estructural:\n{tag_json}",
                    "output": code_content,
                    "metadata": {"type": "decompression", "file": rel_path}
                }

                compiled_pairs.append(pair_compress)
                compiled_pairs.append(pair_decompress)

            except Exception as e:
                logger.error(f"Error procesando {f}: {e}")

        # Write to JSONL
        out_file = self.output_dir / dataset_name
        with open(out_file, mode="w", encoding="utf-8") as out:
            for pair in compiled_pairs:
                out.write(json.dumps(pair, ensure_ascii=False) + "\n")

        self._log(f"Dataset de compresión dual guardado en {out_file} ({len(compiled_pairs)} pares de entrenamiento).")
        return len(compiled_pairs)

    def compile_causal_chains(self, source_dir: Path, dataset_name: str = "causal_chains.jsonl") -> int:
        """
        Compiles the temporal utilization sequences of tags (Capa 2).
        Sorts files by logical dependency or creation time and trains the model 
        to predict the next tag sequence (Next-Step Tag Prediction).
        """
        source_path = Path(source_dir)
        files = sorted(list(source_path.rglob("*.py")), key=lambda p: p.stat().st_mtime)
        if len(files) < 3:
            return 0

        chains = []
        tags_sequence = []

        # First, generate all tags in chronological order
        for f in files:
            try:
                code_content = f.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(f.relative_to(source_path))
                tag = self.packetizer.generate_structural_tag(rel_path, code_content)
                tags_sequence.append(tag)
            except Exception:
                pass

        # Build prediction pairs (predict next tag given history)
        for i in range(1, len(tags_sequence)):
            history = tags_sequence[:i]
            target_next = tags_sequence[i]

            pair = {
                "instruction": "Dada la secuencia temporal de módulos desarrollados en SODA, predice y genera la Etiqueta Estructural del siguiente módulo coherente que se debe construir.",
                "input": f"Historial de Módulos (Secuencia Causal):\n" + json.dumps([h["tag_id"] for h in history], ensure_ascii=False) + "\n\nDetalle del último módulo:\n" + json.dumps(history[-1], ensure_ascii=False),
                "output": json.dumps(target_next, ensure_ascii=False, indent=2),
                "metadata": {"type": "causal_chainer", "target": target_next["tag_id"]}
            }
            chains.append(pair)

        out_file = self.output_dir / dataset_name
        with open(out_file, mode="w", encoding="utf-8") as out:
            for pair in chains:
                out.write(json.dumps(pair, ensure_ascii=False) + "\n")

        self._log(f"Dataset de encadenamiento temporal guardado en {out_file} ({len(chains)} secuencias causales).")
        return len(chains)

    def _log(self, msg: str):
        print(f"[DatasetCompiler] {msg}")
