"""Smoke tests for Part 2 metrics. Run in server/ with:
python -m unittest discover -s test -p "test_event_metrics.py".
"""
import unittest

from src.event_pipeline.metrics import evaluate

SENT = "Công an huyện A bắt giữ Nguyễn Văn B."
GOLD = {"ann_id": "x1", "sentence": SENT,
        "entities": [{"id": "e1", "start": 0, "end": 15, "text": "Công an huyện A", "label": "ORGANIZATION"},
                     {"id": "e2", "start": 24, "end": 36, "text": "Nguyễn Văn B", "label": "PERSON"}],
        "triggers": [{"id": "t1", "start": 16, "end": 23, "text": "bắt giữ", "label": "BAT_GIU"}],
        "relations": [{"trigger_id": "t1", "arg_id": "e1", "role": "CO_QUAN"},
                      {"trigger_id": "t1", "arg_id": "e2", "role": "DOI_TUONG"}]}


class EventMetricsTest(unittest.TestCase):
    def test_perfect(self):
        res = evaluate([GOLD], [GOLD])
        for k in ("trigger_classification", "argument_identification", "relation", "event_exact_match"):
            self.assertEqual(res[k]["f1"], 1.0)

    def test_wrong_role(self):
        pred = dict(GOLD, relations=[{"trigger_id": "t1", "arg_id": "e1", "role": "CO_QUAN"},
                                     {"trigger_id": "t1", "arg_id": "e2", "role": "NAN_NHAN"}])
        res = evaluate([GOLD], [pred])
        self.assertEqual(res["trigger_classification"]["f1"], 1.0)
        self.assertEqual(res["argument_identification"]["f1"], 1.0)   # Correct entity.
        self.assertEqual(res["relation"]["tp"], 1)                     # One role is incorrect.
        self.assertEqual(res["event_exact_match"]["tp"], 0)            # The event does not match exactly.

    def test_wrong_type(self):
        pred = dict(GOLD, triggers=[dict(GOLD["triggers"][0], label="KHOI_TO")])
        res = evaluate([GOLD], [pred])
        self.assertEqual(res["trigger_identification"]["f1"], 1.0)
        self.assertEqual(res["trigger_classification"]["f1"], 0.0)
        self.assertEqual(res["relation"]["tp"], 0)

    def test_ids_do_not_matter(self):
        pred = dict(GOLD, entities=[dict(e, id="z" + e["id"]) for e in GOLD["entities"]],
                    relations=[dict(r, arg_id="z" + r["arg_id"]) for r in GOLD["relations"]])
        self.assertEqual(evaluate([GOLD], [pred])["event_exact_match"]["f1"], 1.0)


if __name__ == "__main__":
    unittest.main()
