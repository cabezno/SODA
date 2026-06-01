import shutil
from pathlib import Path
from typing import Optional

class SODAFileSystem:
    """
    IMP-022: File System Manager with Automatic Backups.
    Ensures that every file write operation is preceded by a backup if the file already exists.
    """
    @staticmethod
    def safe_write(filepath: Path, content: str, watchdog = None) -> None:
        """
        Escribe contenido en un archivo de forma segura.
        Si el archivo ya existe, realiza un respaldo previo usando el watchdog.
        """
        filepath = Path(filepath)

        # 1. Crear directorios si no existen
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 2. Si el archivo ya existe y el watchdog está activo, respaldar
        if filepath.exists() and filepath.is_file() and watchdog is not None:
            try:
                # El watchdog debe tener el método backup_file implementado
                if hasattr(watchdog, "backup_file"):
                    backup_path = watchdog.backup_file(filepath)
                    print(f"🛡️ [FS_MANAGER] Respaldo creado para {filepath.name} -> {backup_path}")
            except Exception as e:
                print(f"⚠️ [FS_MANAGER] No se pudo respaldar {filepath.name}: {e}")

        # 3. Escritura atómica
        temp_file = filepath.with_suffix(".tmp")
        try:
            # Limpiar contenido si viene con bloques markdown (común en IAs)
            clean_content = content.strip()
            if clean_content.startswith("```"):
                lines = clean_content.splitlines()
                if len(lines) > 1:
                    clean_content = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

            temp_file.write_text(clean_content, encoding="utf-8", errors="replace")
            
            if filepath.exists():
                filepath.unlink()
            
            temp_file.rename(filepath)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise e
