import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from models import Decision, Trace
from ui_data import Night, comparison, load_nights, purchases, read_night

ROOT = Path(__file__).resolve().parents[1]


class ReaderTests(unittest.TestCase):
    def test_fixture_story_and_model_contract(self):
        nights = load_nights(ROOT / "demo" / "fixtures", demo=True)
        self.assertFalse(nights[1].warnings + nights[2].warnings)
        self.assertEqual(purchases(nights[1])["esha_sfo_jfk"].regret, 125)
        self.assertEqual(sum(r["Savings"] for r in comparison(nights[1], nights[2])), 121)
        self.assertNotIn("priya_bos_sfo", purchases(nights[2]))
        rohan = next(t for t in nights[1].trips if t.traveler == "Rohan")
        self.assertEqual(rohan.banned_dates, ["2026-12-03"])
        self.assertNotIn("2026-12-03", rohan.dates)

    def test_partial_invalid_and_duplicate_traces(self):
        good = asdict(Trace(1, 0, "a", 100, Decision("BUY", "okay")))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "night_1.json"
            rows = [good, good, {**good, "tick": 32}, {**good, "tick": 1, "price": float("nan")}, {**good, "tick": 2, "decision": "BUY"}]
            path.write_text(json.dumps(rows))
            night = read_night(path, 1)
            self.assertEqual(len(night.traces), 1)
            self.assertEqual(len(night.warnings), 4)
            path.write_text('{"traces":')
            night = read_night(path, 1)
            self.assertFalse(night.traces)
            self.assertTrue(night.warnings)

    def test_real_results_never_inherit_sample_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "night_1.json"
            path.write_text(json.dumps([asdict(Trace(1,0,"unknown",123,Decision("WAIT","waiting")))]))
            night = load_nights(Path(folder))[1]
            self.assertFalse(night.trips)
            self.assertFalse(night.lessons)
            self.assertFalse(night.demo)

    def test_purchase_is_counted_once_and_comparison_is_matched(self):
        a = Night(1, [Trace(1,0,"a",100,Decision("BUY","first")),Trace(1,1,"a",120,Decision("BUY","duplicate intent")),Trace(1,2,"b",200,Decision("BUY","only first night"))])
        b = Night(2, [Trace(2,0,"a",90,Decision("BUY","new intent")),Trace(2,1,"c",50,Decision("BUY","only second night"))])
        self.assertEqual(purchases(a)["a"].price,100)
        self.assertEqual(comparison(a,b),[{"Trip":"a","Night 1":100,"Night 2":90,"Savings":10}])

    def test_versioned_envelope_and_sidecars(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / "night_2.json").write_text(json.dumps({"schema_version":1,"bookings":[],"traces":[asdict(Trace(2,1,"a",200,Decision("WAIT","hold")))]}))
            (p / "lessons_2.json").write_text(json.dumps({"lessons":["watch longer"]}))
            result = load_nights(p)[2]
            self.assertFalse(result.warnings)
            self.assertEqual(result.lessons,["watch longer"])

    def test_execution_fields_keep_simulation_and_omit_credentials(self):
        offer = {"trip_id":"a","tick":0,"price":200,"travel_date":"2026-12-02"}
        payload = {"memory_mode":"offline_demo_fixture","payment_backend":"link","status":"completed","traces":[],"observations":[{"offer":offer,"eligible":True,"rejection_rules":[]}],"execution_events":[{"offer":offer,"status":"pending","backend":"link","checkout":{"status":"approved","card_file":"PRIVATE-CREDENTIAL-PATH","raw_cli":"PRIVATE-OUTPUT"}}],"bookings":[{"trip_id":"a","price":200,"status":"simulated_confirmed","payment_backend":"mock"}],"metrics":{"simulated_replacement_savings":12,"confirmed_real_flight_savings":0}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "night_1.json"
            path.write_text(json.dumps(payload))
            night = read_night(path,1)
            self.assertFalse(night.warnings)
            self.assertEqual(night.metadata["memory_mode"],"offline_demo_fixture")
            self.assertEqual(night.executions[0]["Execution"],"pending")
            self.assertEqual(night.executions[0]["Payment"],"approved")
            self.assertEqual(night.bookings[0]["Status"],"simulated_confirmed")
            self.assertNotIn("PRIVATE-",repr(night))
            self.assertEqual(night.metrics["simulated_replacement_savings"],12)


if __name__ == "__main__":
    unittest.main()
