from services.enterprise.knowledge_evaluation_service import evaluate_ranked_results
from services.enterprise.knowledge_service import _rank_chunk
from types import SimpleNamespace


def test_evaluate_ranked_results_reports_hit_recall_and_mrr():
    report = evaluate_ranked_results(
        [
            {
                "case_id": "case-1",
                "expected_document_ids": ["doc-a", "doc-b"],
                "ranked_document_ids": ["doc-x", "doc-a", "doc-a"],
            },
            {
                "case_id": "case-2",
                "expected_document_ids": ["doc-c"],
                "ranked_document_ids": ["doc-y"],
            },
        ],
        k=10,
    )

    assert report["case_count"] == 2
    assert report["hit_rate"] == 0.5
    assert report["recall_at_k"] == 0.25
    assert report["mean_reciprocal_rank"] == 0.25
    assert report["cases"][0]["first_relevant_rank"] == 2


def test_hybrid_rank_exposes_lexical_and_semantic_components():
    chunk = SimpleNamespace(content="中心启动周期与临床运营能力", heading="运营计划")
    document = SimpleNamespace(logical_name="项目方案", category="运营")

    score, matched, components = _rank_chunk(
        "临床运营", {"临床运营", "临床", "床运", "运营"}, chunk, document, "hybrid"
    )

    assert score > 0
    assert "运营" in matched
    assert components["lexical"] > 0
    assert components["semantic"] > 0
