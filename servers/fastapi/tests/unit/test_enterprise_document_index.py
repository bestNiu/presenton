from services.enterprise.document_index_service import build_document_chunks


def test_build_document_chunks_preserves_heading_and_line_locator():
    text = "# 公司概览\n" + ("企业能力" * 35) + "\n" + ("交付经验" * 35)

    chunks = build_document_chunks(text, max_characters=200)

    assert len(chunks) == 2
    assert [item["chunk_index"] for item in chunks] == [0, 1]
    assert all(item["heading"] == "公司概览" for item in chunks)
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 2
    assert chunks[1]["start_line"] == 1
    assert chunks[1]["end_line"] == 3
    assert chunks[0]["locator"]["heading"] == "公司概览"
    assert len(chunks[0]["content_hash"]) == 64


def test_build_document_chunks_handles_plain_text_and_empty_input():
    chunks = build_document_chunks("第一行\n第二行", max_characters=200)

    assert len(chunks) == 1
    assert chunks[0]["heading"] is None
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 2
    assert build_document_chunks("") == []
