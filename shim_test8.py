import sys
import os
from pathlib import Path

# Agregar el directorio source al path
source_path = Path("projects/test8/source").resolve()
sys.path.insert(0, str(source_path))

# 1. Configurar el logger
import src.logger
src.logger.logger = src.logger.get_logger()

# 2. Patch preprocessor
import src.preprocessor
if not hasattr(src.preprocessor, 'preprocess_text'):
    src.preprocessor.preprocess_text = src.preprocessor.preprocess
# También parchear la clase Preprocessor que espera Searcher
if not hasattr(src.preprocessor, 'Preprocessor'):
    class MockPreprocessor:
        def preprocess_text(self, text):
            return src.preprocessor.preprocess(text)
    src.preprocessor.Preprocessor = MockPreprocessor

# 3. Patch storage
import src.storage
if not hasattr(src.storage, 'Storage'):
    src.storage.Storage = src.storage.StorageManager
if not hasattr(src.storage, 'IndexStorage'):
    src.storage.IndexStorage = src.storage.StorageManager

# 4. Importar cli
import src.cli

if __name__ == "__main__":
    src.cli.main_cli()
