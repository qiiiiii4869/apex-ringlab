import copy
import json
import tempfile
import unittest
from pathlib import Path

from ringlab.data import load_records, save_records, validate_record
from ringlab.ingest import ingest, normalize
from ringlab.retrieval import audit, retrieve


def pair(mode="PUBLIC", game_id=None):
    return {"source_mode": mode, "collected_at": "2026-10-11T00:00:00Z", "round": 1,
            "known": {"success": True, "map": "mp_rr_desertlands_hu", "rings": [{"x": 8000, "y": 8000, "r": 4800}]},
            "reveal": {"success": True, "gameId": game_id, "finalRing": {"x": 9000, "y": 8000, "r": 700}}}


class CollectionTests(unittest.TestCase):
    def test_only_first_ring_is_required(self):
        record = normalize(pair())
        self.assertEqual(len(record["known_rings"]), 1)
        self.assertNotIn("rings", record)
        self.assertEqual(record["game_mode"], "ranked")
        self.assertEqual(record["game_mode_evidence"]["type"], "user_confirmation")
        self.assertIsNone(record["final_ring"]["stage"])

    def test_missing_final_ring_is_not_a_sample(self):
        bad = pair()
        del bad["reveal"]["finalRing"]
        with self.assertRaises(ValueError):
            normalize(bad)

    def test_other_maps_not_imported(self):
        other = pair()
        other["known"]["map"] = "mp_rr_tropic_island_mu2"
        self.assertIsNone(normalize(other))

    def test_partial_mode_is_rejected(self):
        bad = pair("P")
        with self.assertRaisesRegex(ValueError, "ALGS"):
            normalize(bad)

    def test_final_outside_known_circle_rejected(self):
        bad = normalize(pair())
        bad["final_ring"]["x"] = 16000
        with self.assertRaises(ValueError):
            validate_record(bad)

    def test_missing_final_radius_preserved(self):
        raw = pair()
        del raw["reveal"]["finalRing"]["r"]
        self.assertIsNone(normalize(raw)["final_ring"]["r"])

    def test_public_source_id_does_not_invent_algs_replay_link(self):
        public = normalize(pair("PUBLIC", "public-game"))
        self.assertEqual(public["source_game_id"], "public-game")
        self.assertEqual(public["source_url"], "https://apexlegendsstatus.com/algs/ring-guessr")

    def test_resume_deduplicates_and_keeps_source_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "pairs.jsonl"
            output = Path(directory) / "rings.json"
            raw.write_text("\n".join(json.dumps(p) for p in [pair("ALGS", "game1"), pair("ALGS", "game2")]), encoding="utf-8")
            first = ingest(raw, output)
            second = ingest(raw, output)
            self.assertEqual(first["total"], 1)
            self.assertEqual(second["new"], 0)
            self.assertEqual(load_records(output)[0]["source_game_ids"], ["game1", "game2"])

    def test_reclassification_updates_existing_records_without_changing_ids(self):
        raw_pair = pair("PUBLIC", "public-game")
        old = normalize(raw_pair)
        old["game_mode"] = "unknown"
        old.pop("game_mode_evidence")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rings.json"
            raw = Path(directory) / "pairs.jsonl"
            save_records([old], output)
            raw.write_text(json.dumps(raw_pair), encoding="utf-8")
            result = ingest(raw, output)
            updated = load_records(output)
            self.assertEqual(result["total"], 1)
            self.assertEqual(updated[0]["id"], old["id"])
            self.assertEqual(updated[0]["game_mode"], "ranked")
            self.assertEqual(updated[0]["game_mode_evidence"]["type"], "user_confirmation")

    def test_conflicting_final_rings_kept_and_audited(self):
        first = pair()
        second = copy.deepcopy(first)
        second["reveal"]["finalRing"]["x"] += 200
        records = [normalize(first), normalize(second)]
        self.assertNotEqual(records[0]["id"], records[1]["id"])
        self.assertEqual(audit(records)["conflict_groups"], 1)
        result = retrieve(records, records[0]["known_rings"], "mp_rr_desertlands_hu")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertIn("final_ring", result["candidates"][0])
        self.assertFalse(result["ranked_validated"])

    def test_invalid_response_quarantined_without_losing_valid_records(self):
        good = pair()
        bad = copy.deepcopy(good)
        bad["reveal"]["finalRing"]["x"] = 16000
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "pairs.jsonl"
            output = Path(directory) / "rings.json"
            raw.write_text("\n".join(json.dumps(p) for p in [good, bad]), encoding="utf-8")
            result = ingest(raw, output)
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["invalid"], 1)
            quarantined = json.loads(output.with_name("quarantine-records.json").read_text(encoding="utf-8"))
            self.assertEqual(quarantined[0]["line"], 2)
            self.assertEqual(quarantined[0]["raw_pair"]["reveal"]["finalRing"]["x"], 16000)


if __name__ == "__main__":
    unittest.main()
