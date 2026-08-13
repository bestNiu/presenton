import uuid

from models.sql.slide import SlideModel
from services.enterprise.presentation_quality_service import _slide_issues


def test_quality_rules_detect_bounds_placeholder_and_missing_numeric_citation():
    slide = SlideModel(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        presentation=uuid.uuid4(),
        layout_group="general",
        layout="general-1",
        index=2,
        content={},
        ui={
            "id": "slide-3",
            "elements": [
                {
                    "type": "text",
                    "position": {"x": 1200, "y": 690},
                    "size": {"width": 200, "height": 80},
                    "runs": [{"text": "TODO：增长率达到 35%"}],
                }
            ],
        },
    )

    issues = _slide_issues(
        slide, require_numeric_citations=True, cited=False
    )

    assert {item["rule_code"] for item in issues} == {
        "element_out_of_bounds",
        "placeholder_residue",
        "numeric_citation_missing",
    }
    assert all(item["slide_index"] == 2 for item in issues)


def test_numeric_citation_rule_accepts_cited_slide():
    slide = SlideModel(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        presentation=uuid.uuid4(),
        layout_group="general",
        layout="general-1",
        index=0,
        content={},
        ui={
            "id": "slide-1",
            "elements": [
                {
                    "type": "text",
                    "position": {"x": 20, "y": 20},
                    "size": {"width": 400, "height": 80},
                    "runs": [{"text": "计划覆盖 30 家中心"}],
                }
            ],
        },
    )

    issues = _slide_issues(slide, require_numeric_citations=True, cited=True)

    assert issues == []
