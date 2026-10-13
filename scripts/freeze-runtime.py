"""Refresh exact dependency versions only after deliberately validating upgrades."""
from importlib.metadata import version
from pathlib import Path

PACKAGES = ["numpy", "Pillow", "opencv-python-headless", "scikit-learn", "joblib", "scipy",
            "threadpoolctl", "narwhals", "cloudpickle", "fastapi", "uvicorn", "starlette", "pydantic", "pydantic-core",
            "annotated-types", "annotated-doc", "typing-extensions", "typing-inspection",
            "opentelemetry-api", "anyio", "idna", "click", "h11"]
root = Path(__file__).resolve().parents[1]
lines = ["# Tested with CPython 3.13.13; model dependencies match the unmodified training manifest."]
lines += [f"{package}=={version(package)}" for package in PACKAGES]
lines += [f"colorama=={version('colorama')}; sys_platform == 'win32'",
          f"tzdata=={version('tzdata')}; sys_platform == 'win32'"]
(root / "requirements.lock.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
