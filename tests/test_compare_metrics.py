import unittest
from src.compare_metrics import score_results


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(data_version='raw', query_id='Q1', query_type='specific_item',
                          rank=i, record_id=str(i)) for i in range(1, 6)]

    def test_known_metrics(self):
        qrels = [dict(query_id='Q1', record_id=str(i), relevance=v, label_source='test')
                 for i, v in enumerate([0, 2, 1, 2, 0], 1)]
        per, _ = score_results(self.rows, qrels)
        self.assertEqual(per[0]['unknown_as_nonmatch_precision_at_5'], .4)
        self.assertEqual(per[0]['unknown_as_nonmatch_mrr_at_5'], .5)

    def test_unjudged_not_silently_negative(self):
        per, _ = score_results(self.rows, [])
        self.assertEqual(per[0]['judged_at_5'], 0)
        self.assertEqual(per[0]['unknown_as_match_precision_at_5'], 1)
        self.assertEqual(per[0]['unknown_as_nonmatch_precision_at_5'], 0)

    def test_incomplete(self):
        with self.assertRaises(ValueError):
            score_results(self.rows[:3], [])

    def test_duplicate_judgments(self):
        q = dict(query_id='Q1', record_id='1', relevance=2, label_source='test')
        with self.assertRaises(ValueError):
            score_results(self.rows, [q, q])
