import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import os

from kernel.execution.runtime_manager import RuntimeManager

class TestRuntimeManager(unittest.TestCase):
    def setUp(self):
        self.registry_data = {
            "runtimes": {
                "python": {
                    "image_tag": "soda-runtime-python",
                    "dockerfile": "runtimes/python-uv/Dockerfile",
                    "tools": ["uv", "ruff", "pytest"]
                },
                "node": {
                    "image_tag": "soda-runtime-node",
                    "dockerfile": "runtimes/node-ts/Dockerfile",
                    "tools": ["pnpm", "vitest", "tsx"]
                }
            }
        }
        # Mocking the registry file
        self.mock_registry_path = "tests/mock_registry.json"
        with open(self.mock_registry_path, "w") as f:
            json.dump(self.registry_data, f)

    def tearDown(self):
        if os.path.exists(self.mock_registry_path):
            os.remove(self.mock_registry_path)

    @patch("docker.DockerClient")
    def test_load_registry(self, mock_docker):
        manager = RuntimeManager(registry_path=self.mock_registry_path)
        self.assertIn("python", manager.registry)
        self.assertIn("node", manager.registry)
        self.assertEqual(manager.registry["python"]["image_tag"], "soda-runtime-python")

    @patch("docker.DockerClient")
    def test_is_runtime_ready(self, mock_docker):
        mock_client = mock_docker.return_value
        manager = RuntimeManager(registry_path=self.mock_registry_path)
        manager.client = mock_client
        
        # Test ready
        mock_client.images.get.return_value = MagicMock()
        self.assertTrue(manager.is_runtime_ready("python"))
        
        # Test not ready
        import docker
        mock_client.images.get.side_effect = docker.errors.ImageNotFound("not found")
        self.assertFalse(manager.is_runtime_ready("node"))

    @patch("docker.DockerClient")
    def test_get_runtime_config(self, mock_docker):
        manager = RuntimeManager(registry_path=self.mock_registry_path)
        config = manager.get_runtime_config("python")
        self.assertEqual(config["image_tag"], "soda-runtime-python")
        
        config_none = manager.get_runtime_config("nonexistent")
        self.assertIsNone(config_none)

if __name__ == "__main__":
    unittest.main()
