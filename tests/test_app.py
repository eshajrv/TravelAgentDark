import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    def test_exported_team_budget_in_morning_brief(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"FLIGHTHAWK_OUTPUT_DIR": folder}):
            (Path(folder) / "night_1.json").write_text(json.dumps({"traces": [], "team_budget": {"budget": 1500, "booked": 456.75}}))
            at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
            at.radio(key="source").set_value("Runner output").run()
            self.assertFalse(at.exception)
            self.assertTrue(any("Team budget: $456.75 of $1,500.00 used" in x.value for x in at.markdown))
            at.slider(key="tick").set_value(30).run()
            self.assertFalse(any("Team budget:" in x.value for x in at.markdown))

    def test_demo_navigation_replay_and_filters(self):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertFalse(at.exception)
        self.assertEqual([m.value for m in at.metric[:4]], ["3", "2", "1", "$690"])
        at.selectbox(key="night").select(2).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.metric[3].value, "$569")
        at.slider(key="tick").set_value(0).run()
        self.assertEqual(at.metric[1].value, "0")
        at.text_input(key="search").set_value("does-not-exist").run()
        self.assertTrue(any("No decisions match" in x.value for x in at.info))
        at.selectbox(key="route").select("rohan_sfo_ord").run()
        self.assertFalse(at.exception)

    def test_missing_and_corrupt_runner_output(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"REDEYE_OUTPUT_DIR": folder}):
            at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
            at.radio(key="source").set_value("Runner output").run()
            self.assertFalse(at.exception)
            self.assertTrue(any("No night results" in x.value for x in at.info))
            (Path(folder) / "night_1.json").write_text("{")
            at.run()
            self.assertFalse(at.exception)
            self.assertTrue(at.warning)
            self.assertEqual(at.metric[0].value, "0")


if __name__ == "__main__":
    unittest.main()
