from services.enterprise.presentation_governance_service import compare_snapshot_content


def _slide(slide_id: str, index: int, title: str) -> dict:
    return {"id": slide_id, "index": index, "ui": {"title": title}, "content": {}, "speaker_note": None}


def test_snapshot_diff_reports_added_removed_changed_and_unchanged_slides():
    result = compare_snapshot_content(
        {"slides": [_slide("a", 0, "same"), _slide("b", 1, "before"), _slide("c", 2, "removed")]},
        {"slides": [_slide("a", 0, "same"), _slide("b", 1, "after"), _slide("d", 2, "added")]},
    )

    assert {key: result[key] for key in ("added", "removed", "changed", "unchanged")} == {
        "added": 1,
        "removed": 1,
        "changed": 1,
        "unchanged": 1,
    }
    assert next(item for item in result["slides"] if item["slide_id"] == "b")["changed_fields"] == ["ui"]
