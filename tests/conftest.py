"""Shared pytest configuration for SODA tests."""
import sys
import pytest

# ── Windows: patch shutil.rmtree to survive locked files (daemon-thread log handles) ──
if sys.platform == "win32":
    import shutil as _shutil
    import stat as _stat
    import os as _os
    import time as _time

    _orig_rmtree = _shutil.rmtree  # capture BEFORE patching to avoid recursion

    def _soda_onerror(func, fpath, exc_info):
        """Best-effort: chmod → retry → sleep 100ms → retry → give up silently."""
        try:
            _os.chmod(fpath, _stat.S_IWRITE)
            func(fpath)
        except PermissionError:
            _time.sleep(0.1)
            try:
                func(fpath)
            except Exception:
                pass  # locked by a daemon thread — skip, don't block teardown
        except Exception:
            pass

    def _patched_rmtree(path, ignore_errors=False, onerror=None):
        # Always call _orig_rmtree (not the patched version) with our onerror
        # so locked files are silently skipped instead of crashing fixture teardown.
        _orig_rmtree(path, onerror=_soda_onerror)

    _shutil.rmtree = _patched_rmtree


def pytest_configure(config):
    """Redirect tmp_path to D: drive to avoid filling C:\\Temp during pipeline tests."""
    if sys.platform == "win32":
        import os, pathlib
        root = pathlib.Path("D:/Desktop/pytest-soda-tmp-root")
        try:
            root.mkdir(parents=True, exist_ok=True)
            # PYTEST_DEBUG_TEMPROOT makes pytest use make_numbered_dir_with_cleanup,
            # which creates a session-unique subdir and handles stale dirs gracefully.
            os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(root))
        except (PermissionError, OSError):
            pass  # fallback to default if D: is unavailable


@pytest.fixture(autouse=True)
def _restore_docker_module(request):
    """Restore sys.modules['docker'] for tests that need the real docker SDK.

    test_pipeline.py and test_unit.py stub 'docker' as a MagicMock at module
    level. test_runtime_manager.py needs the real module. This fixture saves
    and restores it around each test in that file.
    """
    # Support both old (.fspath) and new (.path) pytest APIs
    node_path = getattr(request, "path", None) or getattr(request, "fspath", None)
    needs_real = node_path is not None and str(node_path).endswith("test_runtime_manager.py")
    if not needs_real:
        yield
        return

    # Save the current (possibly stubbed) docker entry
    stub = sys.modules.get("docker")
    # Remove the stub so the real import can proceed
    if "docker" in sys.modules:
        del sys.modules["docker"]
    # Also remove sub-modules that may be stubs
    stubs_to_remove = [k for k in list(sys.modules) if k == "docker" or k.startswith("docker.")]
    saved_stubs = {k: sys.modules.pop(k) for k in stubs_to_remove}

    yield

    # Restore the stub after the test
    sys.modules.update(saved_stubs)
    if stub is not None:
        sys.modules["docker"] = stub
