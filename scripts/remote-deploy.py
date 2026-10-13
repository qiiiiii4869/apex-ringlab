"""Use the explicitly authorized deployment key and verified server host key."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["exec", "upload", "download"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--remote")
    args = parser.parse_args()
    connection = json.loads((ROOT / "outputs/qa/ssh-deploy-connection.json").read_text())
    if not connection.get("host_key_verified"):
        raise RuntimeError("Server identity must be verified first")
    options = ["-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "KexAlgorithms=curve25519-sha256", "-o", "HostKeyAlgorithms=ssh-ed25519",
               "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
               "-o", "UserKnownHostsFile=" + connection["known_hosts_path"], "-i", connection["private_key_path"]]
    destination = connection["user"] + "@" + connection["host"]
    if args.action == "exec":
        result = subprocess.run(["ssh", "-T", *options, destination, "bash -s"],
                                input=args.path.read_text(encoding="utf-8").encode("utf-8"))
    else:
        if not args.remote or not args.remote.startswith(("/root/", "/opt/")):
            raise ValueError("Specify an absolute deployment destination")
        local_path = str(args.path.resolve())
        remote_path = destination + ":" + args.remote
        if args.action == "download":
            args.path.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(["scp", *options, remote_path, local_path])
        else:
            result = subprocess.run(["scp", *options, local_path, remote_path])
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
