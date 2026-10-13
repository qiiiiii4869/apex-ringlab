import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ringlab.data import write_json_atomic


class AtomicWriteTests(unittest.TestCase):
    def test_transient_windows_lock_retries_without_truncating_previous_data(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "rings.json"
            target.write_text('["previous"]', encoding="utf-8")
            real_replace = Path.replace
            calls = []

            def locked_then_available(source, destination):
                calls.append(destination)
                if len(calls) <= 2:
                    self.assertEqual(json.loads(target.read_text(encoding="utf-8")), ["previous"])
                    error = PermissionError("Windows sharing lock")
                    error.winerror = 5
                    raise error
                return real_replace(source, destination)

            with patch.object(Path, "replace", autospec=True, side_effect=locked_then_available), patch("ringlab.data.time.sleep") as sleep:
                write_json_atomic(target, ["new"])
            self.assertEqual(len(calls), 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.05, 0.1])
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), ["new"])
            self.assertFalse(target.with_suffix(".json.tmp").exists())

    def test_persistent_lock_stops_after_limit_and_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "rings.json"
            target.write_text('["previous"]', encoding="utf-8")
            error = PermissionError("Persistent Windows sharing lock")
            error.winerror = 32
            with patch.object(Path, "replace", side_effect=error) as replace, patch("ringlab.data.time.sleep") as sleep:
                with self.assertRaises(PermissionError):
                    write_json_atomic(target, ["new"], attempts=3)
            self.assertEqual(replace.call_count, 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), ["previous"])
            self.assertEqual(json.loads(target.with_suffix(".json.tmp").read_text(encoding="utf-8")), ["new"])

    def test_other_permission_errors_are_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "rings.json"
            with patch.object(Path, "replace", side_effect=PermissionError("Directory permissions")) as replace, patch("ringlab.data.time.sleep") as sleep:
                with self.assertRaises(PermissionError):
                    write_json_atomic(target, [])
            self.assertEqual(replace.call_count, 1)
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
