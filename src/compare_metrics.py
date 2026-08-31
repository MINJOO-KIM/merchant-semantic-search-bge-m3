"""Scoring fixed query-document qrels; no use of enrichment rules or scores as labels."""
from collections import defaultdict
from statistics import mean


def score_results(rows, qrels, k=5):
    if k != 5 or not rows:
        raise ValueError('This comparison requires nonempty results and k=5')
    lookup = {}
    for r in qrels:
        key = (str(r['query_id']), str(r['record_id']))
        if key in lookup:
            raise ValueError('Duplicate query-document judgment')
        raw = str(r.get('relevance', '')).strip()
        grade = None if not raw else float(raw)
        if grade is not None and grade not in (0, 1, 2):
            raise ValueError('Invalid relevance')
        if grade is not None and not r.get('label_source'):
            raise ValueError('A label requires its provenance')
        lookup[key] = grade
    groups = defaultdict(list)
    for row in rows:
        groups[(row['data_version'], row['query_id'])].append(row)
    result = []
    for (version, qid), group in sorted(groups.items()):
        group = sorted(group, key=lambda r: int(r['rank']))
        if len({r['record_id'] for r in group}) != len(group):
            raise ValueError('Duplicate result ID')
        top = group[:k]
        if [int(r['rank']) for r in top] != list(range(1, k + 1)):
            raise ValueError('Incomplete or duplicate top-k ranks')
        labels = [lookup.get((str(qid), str(r['record_id']))) for r in top]
        out = dict(data_version=version, query_id=qid, query_type=top[0]['query_type'],
                   judged_at_5=sum(x is not None for x in labels) / k)
        for scenario in ('unknown_as_nonmatch', 'unknown_as_match'):
            hits = [x == 2 or (x is None and scenario == 'unknown_as_match') for x in labels]
            first = next((i for i, hit in enumerate(hits, 1) if hit), None)
            out[scenario + '_precision_at_5'] = sum(hits) / k
            out[scenario + '_top1'] = float(hits[0])
            out[scenario + '_hit_at_5'] = float(any(hits))
            out[scenario + '_mrr_at_5'] = 1 / first if first else 0.
        result.append(out)
    summaries = []
    # Keep exact-name lookup separate: it often has only one correct record.
    for version in sorted({r['data_version'] for r in result}):
        for scope in ('item_intent', 'name_lookup'):
            subset = [r for r in result if r['data_version'] == version and
                      (r['query_type'] == 'missing_item_name') == (scope == 'name_lookup')]
            if subset:
                summaries.append(dict(data_version=version, scope=scope, queries=len(subset),
                    **{key: mean(r[key] for r in subset)
                       for key in subset[0] if key not in ('data_version', 'query_id', 'query_type')}))
    return result, summaries
