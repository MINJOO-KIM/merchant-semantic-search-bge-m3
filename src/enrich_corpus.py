"""Conservative, auditable corpus annotations; NOT query relevance or NICE codes.

All input rows are processed. Unmatched/ambiguous rows deliberately abstain.
Outputs JSON for the report/CSV exporter; source data is never overwritten.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

VERSION = 'evidence_rules_v1'
# Exact item tokens, not substring matching: 떡갈비 must not become 떡.
# These are text-based hypotheses, not independently verified shop facts.
GROUPS = [
    ('도서', '상품', '서적|도서|책|서점'),
    ('정육', '원육판매 후보', '정육|정육점|식육|식육점'),
    ('생닭', '원육판매 후보', '생닭'),
    ('육류', '판매형태 불명', '육류|축산물|소고기|쇠고기|돼지고기|닭|고기|닭오리'),
    ('반찬', '식품', '반찬|반찬류|밑반찬'),
    ('커피', '음료', '커피|카페|커피전문점'),
    ('화장품', '상품', '화장품'),
    ('주방용품', '상품', '주방용품|주방기구|그릇'),
    ('생활용품', '상품', '생활용품|가정용품|가정용품 소매'),
    ('아동복', '상품', '아동복|유아복|어린이옷'),
    ('의류', '상품', '의류|옷|여성의류|남성의류|여성복|남성복|한복|속옷|내의'),
    ('과일', '식품', '과일|청과'),
    ('채소', '식품', '채소|야채'),
    ('건어물', '식품', '건어물'),
    ('수산물', '판매형태 불명', '수산물|생선|해산물'),
    ('떡', '식품', '떡|떡류'),
    ('떡케이크', '식품', '떡케이크'),
    ('빵', '식품', '빵|제과|제빵'),
    ('두부', '식품', '두부'),
    ('김치', '식품', '김치'),
    ('젓갈', '식품', '젓갈'),
    ('피부관리', '서비스', '피부관리|피부미용'),
    ('머리미용', '서비스', '미용실|헤어|두발미용'),
    ('미용', '서비스 세부불명', '미용|미용업'),
    ('네일', '서비스', '네일|네일아트'),
    ('조리음식', '음식점 후보', '한식|중식|일식|양식|분식|음식점|일반음식점|치킨|칼국수|피자|족발|김밥|햄버거|국수|만두|마라탕|떡볶이|닭강정|감자탕|해물찜'),
    ('의약품', '상품', '의약품|약|약국'),
    ('의료', '서비스', '의료|의료서비스|한의원|치과'),
    ('꽃', '상품', '꽃|생화'),
    ('침구', '상품', '이불|침구류'),
    ('신발', '상품', '신발'),
    ('액세서리', '상품', '악세사리|액세서리|귀금속'),
    ('휴대폰', '상품', '휴대폰'),
    ('가구', '상품', '가구'),
    ('세탁', '서비스', '세탁|세탁소'),
    ('운동', '서비스', '헬스|태권도|필라테스'),
    ('교육', '서비스', '교육서비스'),
]
LOOKUP = {term: (category, mode) for category, mode, terms in GROUPS for term in terms.split('|')}
NAME_TERMS = ('정육점', '서점', '미용실', '아동복', '반찬', '화장품', '카페')


def annotate(row):
    raw = row['original_items']
    tokens = [re.sub(r'\s+', ' ', t).strip() for t in re.split(r'[,，/;；·\n]+', raw)]
    tokens = [re.sub(r'\s+등$', '', t) for t in tokens if t]
    matches = [(t, *LOOKUP[t]) for t in tokens if t in LOOKUP]
    unknown = [t for t in tokens if t not in LOOKUP]
    categories = list(dict.fromkeys(x[1] for x in matches))
    modes = list(dict.fromkeys(x[2] for x in matches))
    # Naming clues are retained for inspection, never silently used as shop facts.
    candidates = [t for t in NAME_TERMS if t in row['merchant_name']]
    status = 'item_evidence' if matches else ('missing_items' if not raw.strip() else 'unresolved')
    if matches and unknown:
        status = 'partial_item_evidence'
    if '조리음식' in categories and any(x in categories for x in ['정육', '생닭']):
        status = 'conflicting_evidence'
    # Avoid asserting a sales channel where the source only says 고기/닭/미용.
    additions = [c for c in categories if c not in ('육류', '미용')]
    if status == 'conflicting_evidence':
        additions = []
    suffix = (' 품목·업종 참고: ' + ', '.join(additions) + '.') if additions else ''
    return {**row, 'normalized_items': ', '.join(tokens),
            'category_candidates': '|'.join(categories), 'business_type_candidates': '|'.join(modes),
            'name_candidates': '|'.join(candidates), 'annotation_status': status,
            'annotation_evidence': '; '.join(f'원본 품목 [{t}] → {c}' for t, c, _ in matches),
            'unmapped_tokens': '|'.join(unknown), 'annotation_source': 'deterministic_rules_unverified',
            'annotation_version': VERSION, 'search_document_enriched': row['search_document'] + suffix}


def process(rows):
    required = {'record_id', 'merchant_name', 'original_items', 'market_name', 'search_document'}
    if not rows or any(required - row.keys() for row in rows):
        raise ValueError('Missing required raw document columns')
    if len({r['record_id'] for r in rows}) != len(rows):
        raise ValueError('record_id must be unique')
    result = [annotate(row) for row in rows]
    assert all(all(out[k] == row[k] for k in row) for row, out in zip(rows, result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        raise ValueError('Cannot overwrite source')
    with args.input.open(encoding='utf-8-sig', newline='') as f:
        rows = process(list(csv.DictReader(f)))
    summary = {'rows': len(rows), 'status_counts': dict(Counter(r['annotation_status'] for r in rows)),
               'changed_documents': sum(r['search_document'] != r['search_document_enriched'] for r in rows),
               'source_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
               'version': VERSION, 'verified_ground_truth': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'summary': summary, 'rows': rows}, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
