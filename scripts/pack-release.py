"""Package only serving files; exclude uploads, raw data, caches and test fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ringlab.workbench import Workbench


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "releases" / "ringlab-fastapi.zip")
    args = parser.parse_args()
    Workbench()  # Reject a stale dataset/model before packaging anything.
    fixed = ["Dockerfile", ".dockerignore", "requirements.txt", "requirements.lock.txt", "requirements-dev.txt",
             "DEPLOYMENT.md", "README.md", "WEB_GUIDE.md", "data/rings.json", "data/training/manifest.json",
             "data/training/example-query.json", "web/assets/worlds-edge.jpg"]
    files = [ROOT / name for name in fixed]
    for folder, pattern in (("ringlab", "*.py"), ("web", "*.html"), ("web", "*.css"), ("web", "*.js"),
                            ("web", "*.mjs"), ("models", "stage-*.joblib"), ("deploy", "*")):
        files.extend(sorted((ROOT / folder).glob(pattern)))
    files.extend(ROOT / "scripts" / name for name in ("start-web.ps1", "load-test.py", "pack-release.py", "fetch-base-image.py"))
    hashes = {str(file.relative_to(ROOT).as_posix()): hashlib.sha256(file.read_bytes()).hexdigest()
              for file in files if file.is_file()}
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "python": "3.13.13", "files": hashes,
                "images_and_raw_collection_included": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name in hashes:
            archive.write(ROOT / name, name)
        archive.writestr("release-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Release: {args.output.resolve()} ({len(hashes)} files)")


if __name__ == "__main__":
    main()
