"""Shared pytest configuration for SODA tests."""
import sys
import pytest


def _robust_rmtree(path):
    """shutil.rmtree with Windows-safe retry on PermissionError (locked venv files)."""
    import shutil, time, stat, os

    def _on_error(func, fpath, exc_info):
        # Make read-only files writable then retry
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except PermissionError:
            time.sleep(0.05)
            try:
                func(fpath)
            except Exception:
                pass  # best-effort — don't block teardown
        except Exception:
            pass

    shutil.rmtree(path, onerror=_on_error)


if sys.platform == "win32":
    # Patch pytest's internal cleanup to use the robust rmtree
    try:
        import _pytest.tmpdir as _pt
        _orig_cleanup = getattr(_pt, "cleanup_on_next_exit", None)
        # Patch shutil.rmtree used by TempPathFactory
        import shutil as _shutil
        _orig_rmtree = _shutil.rmtree

        def _patched_rmtree(path, ignore_errors=False, onerror=None):
            if onerror is None and not ignore_errors:
                _robust_rmtree(path)
            else:
                _orig_rmtree(path, ignore_errors=ignore_errors, onerror=onerror)

        _shutil.rmtree = _patched_rmtree
    except Exception:
        pass


def pytest_configure(config):
    """Redirect tmp_path to D: drive to avoid filling C:\\Temp during pipeline tests."""
    if sys.platform == "win32":
        import pathlib
        basetemp = pathlib.Path("D:/Desktop/pytest-soda-tmp")
        try:
            basetemp.mkdir(parents=True, exist_ok=True)
            config.option.basetemp = str(basetemp)
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
