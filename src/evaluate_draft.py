"""Diagnostic only: AI-assisted labels are not an independent benchmark.

Unknown/inferred human labels remain unresolved. Scenario ranges hold the
unverified AI labels fixed; they are NOT confidence intervals or proven bounds.
No source CSV or human label is changed. Output is an aggregate JSON report.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_label(value: str) -> int | None:
    if not str(value).strip():
        return None
    number = float(value)
    if number not in (0, 1, 2):
        raise ValueError(f"Invalid relevance label: {value!r}")
    return int(number)


def resolve_label(row: dict[str, str]) -> tuple[int | None, str]:
    evidence = row["human_evidence_status"]
    human = parse_label(row.get("relevance", ""))
    ai = parse_label(row.get("ai_suggested_relevance", ""))
    if evidence == "user_reported":
        if human is None:
            raise ValueError("user_reported requires a human label")
        return human, "human_reported"
    if evidence in {"unknown", "user_inference", "partial_or_unknown"}:
        return None, "unresolved"
    if evidence == "not_reviewed":
        if human is not None:
            raise ValueError("Human label conflicts with not_reviewed status")
        if ai in (0, 2):
            return ai, "ai_unverified"
        return None, "unresolved"
    raise ValueError(f"Unsupported evidence status: {evidence!r}")


def binary_metrics(labels: list[int | None], k: int, optimistic: bool) -> dict:
    hits = [value == 2 or (value is None and optimistic) for value in labels[:k]]
    first = next((position for position, hit in enumerate(hits, 1) if hit), None)
    return {
        f"precision_at_{k}": sum(hits) / k,
        "top1_success": float(hits[0]),
        f"hit_at_{k}": float(any(hits)),
        f"mrr_at_{k}": 1 / first if first else 0.0,
    }


def evaluate(rows: list[dict[str, str]], k: int = 5) -> dict:
    if k < 1 or not rows:
        raise ValueError("Positive k and nonempty results are required")
    required = {"experiment_id", "model", "data_version", "query_id", "query",
                "query_type", "record_id", "rank", "relevance",
                "ai_suggested_relevance", "human_evidence_status"}
    if any(required - row.keys() for row in rows):
        raise ValueError("Required columns are missing")
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row[name] for name in ("experiment_id", "model", "data_version", "query_id"))
        groups[key].append(row)
    queries, counts = [], Counter()
    for key, group in sorted(groups.items()):
        ranks = [int(row["rank"]) for row in group]
        if len(set(ranks)) != len(ranks) or min(ranks) < 1:
            raise ValueError(f"Duplicate or invalid ranks in {key}")
        if len({row["record_id"] for row in group}) != len(group):
            raise ValueError(f"Duplicate records in {key}")
        if len({(row["query"], row["query_type"]) for row in group}) != 1:
            raise ValueError(f"Inconsistent query metadata in {key}")
        top = sorted(group, key=lambda row: int(row["rank"]))[:k]
        if [int(row["rank"]) for row in top] != list(range(1, k + 1)):
            raise ValueError(f"Need complete ranks 1..{k} in {key}; do not silently change denominator")
        resolved = [resolve_label(row) for row in top]
        counts.update(status for _, status in resolved)
        labels = [value for value, _ in resolved]
        queries.append({
            "experiment_id": key[0], "model": key[1], "data_version": key[2],
            "query_id": key[3], "query_type": top[0]["query_type"],
            "unresolved_count": labels.count(None),
            "unknown_as_nonmatch": binary_metrics(labels, k, False),
            "unknown_as_match": binary_metrics(labels, k, True),
        })
    summaries = []
    experiments = sorted({(q["experiment_id"], q["model"], q["data_version"]) for q in queries})
    for experiment in experiments:
        selected = [q for q in queries if (q["experiment_id"], q["model"], q["data_version"]) == experiment]
        for category in ["ALL", "DISCOVERY_ONLY"] + sorted({q["query_type"] for q in selected}):
            subset = [q for q in selected if category == "ALL" or q["query_type"] == category
                      or (category == "DISCOVERY_ONLY" and q["query_type"] != "missing_item_name")]
            if not subset:
                continue
            summary = dict(zip(("experiment_id", "model", "data_version"), experiment))
            summary.update(query_type=category, query_count=len(subset))
            for scenario in ("unknown_as_nonmatch", "unknown_as_match"):
                summary[scenario] = {
                    metric: mean(q[scenario][metric] for q in subset)
                    for metric in subset[0][scenario]
                }
            summaries.append(summary)
    return {
        "status": "PROVISIONAL_AI_ASSISTED_DIAGNOSTIC_NOT_MODEL_SELECTION_EVIDENCE",
        "caveat": "AI labels are unverified and held fixed. Scenarios vary only unresolved labels; not confidence intervals. Human reports are not external verification.",
        "k": k, "input_rows": len(rows), "evaluated_rows": len(queries) * k,
        "query_count": len(queries), "label_sources": dict(counts),
        "ndcg": "not_computed_without_shared_qrels",
        "recall": "not_computed_without_sufficient_relevant_document_pool",
        "summaries": summaries, "queries": queries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        raise ValueError("Output must not overwrite the source CSV")
    result = evaluate(read_rows(args.input), args.k)
    result["source_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "query_count", "label_sources", "summaries")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
