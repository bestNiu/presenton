from statistics import mean


def evaluate_ranked_results(cases: list[dict], *, k: int = 10) -> dict:
    rows: list[dict] = []
    for case in cases:
        expected = {str(item) for item in case.get("expected_document_ids", [])}
        ranked = [str(item) for item in case.get("ranked_document_ids", [])[:k]]
        unique_ranked = list(dict.fromkeys(ranked))
        relevant = [item for item in unique_ranked if item in expected]
        first_rank = next(
            (index for index, item in enumerate(unique_ranked, start=1) if item in expected),
            None,
        )
        rows.append(
            {
                "case_id": case.get("case_id"),
                "hit": bool(relevant),
                "recall": len(set(relevant)) / len(expected) if expected else 1.0,
                "reciprocal_rank": 1 / first_rank if first_rank else 0.0,
                "first_relevant_rank": first_rank,
                "returned_count": len(unique_ranked),
            }
        )
    return {
        "case_count": len(rows),
        "k": k,
        "hit_rate": round(mean(item["hit"] for item in rows), 4) if rows else 0.0,
        "recall_at_k": round(mean(item["recall"] for item in rows), 4) if rows else 0.0,
        "mean_reciprocal_rank": (
            round(mean(item["reciprocal_rank"] for item in rows), 4) if rows else 0.0
        ),
        "cases": rows,
    }
