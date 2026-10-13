"""Normalize paired Ring Guessr responses; no session credentials are persisted."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from .data import DATA_FILE, ROOT, load_records, save_records, validate_record, write_json_atomic
from .retrieval import audit

SOURCE = "https://apexlegendsstatus.com/algs/ring-guessr"
MODE_CLASSIFICATION = json.loads((ROOT / "data" / "source-modes.json").read_text(encoding="utf-8"))["classification"]


def normalize(pair: dict) -> dict | None:
    known, reveal = pair["known"], pair["reveal"]
    if known.get("error") or reveal.get("error") or not known.get("success") or not reveal.get("success"):
        raise ValueError("请求未成功，不能作为配对样本")
    map_version = known.get("map", "")
    if not map_version.startswith("mp_rr_desertlands"):
        return None
    if pair.get("source_mode") not in ("ALGS", "PUBLIC"):
        raise ValueError("来源模式必须为 ALGS 或 PUBLIC")
    rings = [{"stage": i + 1, **{k: r[k] for k in ("x", "y", "r")}} for i, r in enumerate(known["rings"])]
    final = reveal.get("finalRing")
    if not isinstance(final, dict):
        raise ValueError("响应没有最终圈，不能入库")
    final = {"x": final["x"], "y": final["y"], "r": final.get("r"), "label": "ringguessr_final", "stage": None}
    # Dedup by known coordinates and target, partitioned by map and source mode.
    signature = {"map": map_version, "source_mode": pair["source_mode"], "known": rings, "final": final}
    digest = hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
    game_id = reveal.get("gameId") or None
    record = {
        "id": "rg_" + digest, "source": "apexlegendsstatus_ringguessr",
        "source_url": f"https://apexlegendsstatus.com/algs/game/{game_id}" if game_id and pair["source_mode"] == "ALGS" else SOURCE,
        "source_game_id": game_id, "source_mode": pair["source_mode"],
        "game_mode": MODE_CLASSIFICATION[pair["source_mode"]]["game_mode"],
        "game_mode_evidence": MODE_CLASSIFICATION[pair["source_mode"]]["evidence"].copy(),
        "map": "worlds_edge", "map_version": map_version, "build": None,
        "collected_at": pair["collected_at"], "coordinate_size": 16384,
        "known_rings": rings, "final_ring": final,
        "game_description": reveal.get("gameDesc"),
        "provenance": {"method": "same_session_same_round", "round": pair.get("round"),
                       "batch_id": pair.get("batch_id"), "duplicate_key": "map_source_known_and_final_coordinates"},
    }
    return validate_record(record)


def ingest(path: Path, output: Path = DATA_FILE) -> dict:
    records = load_records(output)
    by_id = {r["id"]: r for r in records}
    counts = Counter()
    errors = []
    quarantine = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = normalize(json.loads(line))
            if record is None:
                counts["other_maps"] += 1
            elif record["id"] in by_id:
                old = by_id[record["id"]]
                old["source_url"] = record["source_url"]
                old["game_mode"] = record["game_mode"]
                old["game_mode_evidence"] = record["game_mode_evidence"]
                # Keep every available source game ID for evaluation leakage checks.
                ids = set(old.get("source_game_ids", []))
                for match_id in (old.get("source_game_id"), record.get("source_game_id")):
                    if match_id:
                        ids.add(match_id)
                old["source_game_ids"] = sorted(ids)
                counts["duplicates"] += 1
            else:
                by_id[record["id"]] = record
                counts["new"] += 1
        except (KeyError, TypeError, ValueError) as exc:
            counts["invalid"] += 1
            errors.append({"line": line_number, "reason": str(exc)})
            quarantine.append({"raw_file": path.name, "line": line_number, "reason": str(exc), "raw_pair": json.loads(line) if line.lstrip().startswith("{") and _is_json(line) else None})
    records = sorted(by_id.values(), key=lambda r: (r["source_mode"], r["map_version"], r["id"]))
    save_records(records, output)
    quarantine_path = output.with_name("quarantine-records.json")
    write_json_atomic(quarantine_path, quarantine)
    return {"total": len(records), "new": counts["new"], "duplicates": counts["duplicates"],
            "other_maps": counts["other_maps"], "invalid": counts["invalid"], "errors": errors[:10],
            "source_modes": dict(Counter(r["source_mode"] for r in records)),
            "map_versions": dict(Counter(r["map_version"] for r in records)), "audit": audit(records)}


def _is_json(line):
    try:
        json.loads(line)
        return True
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs", type=Path)
    parser.add_argument("--output", type=Path, default=DATA_FILE)
    parser.add_argument("--allow-quarantine", action="store_true", help="Keep invalid responses separately and continue importing valid records")
    args = parser.parse_args()
    result = ingest(args.pairs, args.output)
    print(json.dumps(result, ensure_ascii=True))
    report = args.output.with_name("collection-report.json")
    write_json_atomic(report, result)
    if result["invalid"] and not args.allow_quarantine:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
