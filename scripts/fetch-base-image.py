"""Download the pinned official amd64 Python image as a Docker load archive.

This helper needs no local Docker daemon. Registry blobs and uncompressed
layer hashes are verified; layers are never extracted into the host filesystem.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import shutil
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = "3.13.13-slim-bookworm"
DIGEST = "sha256:f576b530293e74140ea91d262232648d5c4f45640a95ec447757701bfcacf034"
REGISTRY = "https://registry-1.docker.io/v2/library/python"
CACHE = ROOT / "outputs" / "qa" / "python-base-blobs"
OUTPUT = ROOT / "outputs" / "releases" / f"python-{TAG}-amd64.tar.gz"


class StripRedirectAuth(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            redirected.remove_header("Authorization")
        return redirected


OPENER = urllib.request.build_opener(StripRedirectAuth())


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def fetch(url: str, token: str | None = None, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "ringlab-offline-image/1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if accept:
        headers["Accept"] = accept
    with OPENER.open(urllib.request.Request(url, headers=headers), timeout=45) as response:
        return response.read()


def blob(item: dict, token: str) -> Path:
    digest = item["digest"]
    algorithm, hex_digest = digest.split(":", 1)
    if algorithm != "sha256" or len(hex_digest) != 64 or any(c not in "0123456789abcdef" for c in hex_digest):
        raise ValueError("Unexpected registry digest")
    target = CACHE / hex_digest
    if target.exists() and target.stat().st_size == item["size"] and sha(target) == digest:
        return target
    partial = target.with_suffix(".part")
    for attempt in range(3):
        try:
            request = urllib.request.Request(REGISTRY + "/blobs/" + digest,
                                             headers={"Authorization": "Bearer " + token})
            with OPENER.open(request, timeout=45) as source, partial.open("wb") as dest:
                shutil.copyfileobj(source, dest, 1024 * 1024)
            if partial.stat().st_size != item["size"] or sha(partial) != digest:
                raise ValueError("Blob size or SHA-256 mismatch")
            partial.replace(target)
            print(f"Verified blob {hex_digest[:12]} ({item['size']} bytes)", flush=True)
            return target
        except Exception:
            if attempt == 2:
                raise
            print(f"Retrying blob {hex_digest[:12]}", flush=True)
    raise AssertionError("Unreachable")


def add_bytes(archive: tarfile.TarFile, name: str, content: bytes):
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(content))


def main():
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    CACHE.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    token = json.loads(fetch("https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/python:pull"))["token"]
    raw_manifest = fetch(REGISTRY + "/manifests/" + DIGEST, token,
                         "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json")
    if "sha256:" + hashlib.sha256(raw_manifest).hexdigest() != DIGEST:
        raise ValueError("Pinned image manifest hash mismatch")
    manifest = json.loads(raw_manifest)
    config_path = blob(manifest["config"], token)
    config = json.loads(config_path.read_bytes())
    if (config["os"], config["architecture"]) != ("linux", "amd64"):
        raise ValueError("Wrong image platform")
    diff_ids = config["rootfs"]["diff_ids"]
    if len(diff_ids) != len(manifest["layers"]):
        raise ValueError("Layer count mismatch")
    layers = []
    for item, diff_id in zip(manifest["layers"], diff_ids):
        compressed = blob(item, token)
        uncompressed = CACHE / (compressed.name + ".tar")
        with gzip.open(compressed, "rb") as source, uncompressed.open("wb") as dest:
            shutil.copyfileobj(source, dest, 1024 * 1024)
        if sha(uncompressed) != diff_id:
            raise ValueError("Uncompressed layer hash mismatch")
        layers.append(uncompressed)
    config_name = config_path.name + ".json"
    layer_names = [diff_id.split(":", 1)[1] + "/layer.tar" for diff_id in diff_ids]
    docker_manifest = [{"Config": config_name, "RepoTags": ["python:" + TAG], "Layers": layer_names}]
    partial_output = OUTPUT.with_suffix(OUTPUT.suffix + ".part")
    with tarfile.open(partial_output, "w:gz", compresslevel=6) as archive:
        archive.add(config_path, arcname=config_name, recursive=False)
        for path, name in zip(layers, layer_names):
            archive.add(path, arcname=name, recursive=False)
        add_bytes(archive, "manifest.json", json.dumps(docker_manifest).encode())
    # Verify the finished archive, including every layer's content hash.
    with tarfile.open(partial_output, "r:gz") as archive:
        if archive.extractfile(config_name).read() != config_path.read_bytes():
            raise ValueError("Archive config mismatch")
        for name, expected in zip(layer_names, diff_ids):
            digest = hashlib.sha256()
            with archive.extractfile(name) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if "sha256:" + digest.hexdigest() != expected:
                raise ValueError("Archive layer mismatch")
    partial_output.replace(OUTPUT)
    output_hash = sha(OUTPUT).split(":", 1)[1]
    OUTPUT.with_suffix(OUTPUT.suffix + ".sha256").write_text(output_hash + "  " + OUTPUT.name + "\n", encoding="ascii")
    OUTPUT.with_suffix(OUTPUT.suffix + ".source.json").write_text(json.dumps({
        "source": "https://hub.docker.com/_/python", "tag": "python:" + TAG,
        "platform": "linux/amd64", "manifest_digest": DIGEST,
        "config_digest": manifest["config"]["digest"], "archive_sha256": output_hash,
        "registry_blobs_and_layer_hashes_verified": True,
        "docker_load_verified": False,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Archive: {OUTPUT} ({OUTPUT.stat().st_size} bytes)", flush=True)
    print("SHA256: " + output_hash, flush=True)


if __name__ == "__main__":
    main()
