import unittest
from src.enrich_corpus import annotate, process


def row(items, name='테스트'):
    return dict(record_id='0', merchant_name=name, original_items=items,
                market_name='시장', search_document=f'가맹점명: {name}. 취급품목: {items}.')


class EnrichmentTests(unittest.TestCase):
    def test_chicken_is_not_raw_chicken(self):
        out = annotate(row('닭'))
        self.assertEqual(out['business_type_candidates'], '판매형태 불명')
        self.assertEqual(out['search_document'], out['search_document_enriched'])

    def test_no_substring_classification(self):
        self.assertEqual(annotate(row('떡갈비'))['category_candidates'], '')

    def test_missing_name_is_candidate_only(self):
        out = annotate(row('', '테스트정육점'))
        self.assertEqual(out['name_candidates'], '정육점')
        self.assertEqual(out['search_document'], out['search_document_enriched'])

    def test_preservation(self):
        source = row(' 식육, 의류 ')
        out = process([source])[0]
        self.assertTrue(all(out[k] == v for k, v in source.items()))
        self.assertEqual(out['category_candidates'], '정육|의류')

    def test_conflict_abstains(self):
        out = annotate(row('정육,한식'))
        self.assertEqual(out['annotation_status'], 'conflicting_evidence')
        self.assertEqual(out['search_document'], out['search_document_enriched'])

    def test_duplicate_id(self):
        with self.assertRaises(ValueError):
            process([row('생닭'), row('치킨')])
