import unittest

from src.evaluate_draft import binary_metrics, evaluate, resolve_label


def row(rank, label="2", evidence="not_reviewed", human=""):
    return dict(experiment_id="test", model="test", data_version="raw",
                query_id="q", query="test", query_type="specific_item",
                rank=str(rank), record_id=str(rank), relevance=human,
                ai_suggested_relevance=label, human_evidence_status=evidence)


class DraftEvaluationTest(unittest.TestCase):
    def test_known_example(self):
        values = binary_metrics([0, 2, 0, 2, 2], 5, False)
        self.assertEqual(values, dict(precision_at_5=0.6, top1_success=0.0,
                                     hit_at_5=1.0, mrr_at_5=0.5))

    def test_unknown_and_inferred_are_not_confirmed(self):
        for evidence in ("unknown", "user_inference", "partial_or_unknown"):
            self.assertEqual(resolve_label(row(1, evidence=evidence, human="0")),
                             (None, "unresolved"))

    def test_user_report_overrides_ai(self):
        self.assertEqual(resolve_label(row(1, evidence="user_reported", human="0")),
                         (0, "human_reported"))

    def test_scenario_endpoints(self):
        rows = [row(1, evidence="unknown", human="1"), row(2), row(3, "0"), row(4, "0"), row(5, "0")]
        result = evaluate(rows)
        summary = result["summaries"][0]
        self.assertEqual(summary["unknown_as_nonmatch"]["precision_at_5"], 0.2)
        self.assertEqual(summary["unknown_as_match"]["precision_at_5"], 0.4)
        self.assertEqual(result["label_sources"]["unresolved"], 1)

    def test_missing_rank_rejected(self):
        with self.assertRaises(ValueError):
            evaluate([row(1), row(2)])

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            evaluate([row(1)] * 5)

    def test_invalid_status_or_label_rejected(self):
        for value in (row(1, "3"), row(1, evidence="made_up")):
            with self.assertRaises(ValueError):
                resolve_label(value)

    def test_invalid_human_provenance_rejected(self):
        with self.assertRaises(ValueError):
            resolve_label(row(1, human="2"))


if __name__ == "__main__":
    unittest.main()
