from claimdesk.domain.clauses import CLAUSE_V3
from claimdesk.rag.attribute import (
    ANCHOR_PHRASE,
    CONGENITAL_QUESTION,
    WRONG_DRAFT,
    attribute_congenital_chunked_case,
    attribute_congenital_generation_control,
    recall_fixed_chunks,
)
from claimdesk.rag.chunk import CONGENITAL_CHUNK_STRIDE, CONGENITAL_CHUNK_WINDOW


def test_day06_congenital_wrong_answer_is_chunking_not_generation():
    assert ANCHOR_PHRASE in CLAUSE_V3

    recalled = recall_fixed_chunks(CONGENITAL_QUESTION)
    assert len(recalled) >= 1
    for chunk in recalled:
        assert chunk.clause_id == "AK-2024-6.1"
        assert chunk.text.strip()

    union = "".join(chunk.text for chunk in recalled)
    assert ANCHOR_PHRASE not in union

    result = attribute_congenital_chunked_case()
    assert result.stage == "retrieval"
    assert result.subreason == "chunking"
    assert result.question == CONGENITAL_QUESTION
    assert "一律不赔" in result.draft
    assert "不是一律不赔" not in result.draft
    assert result.recalled_chunks == recalled


def test_day06_congenital_recall_has_sentence_still_generation():
    result = attribute_congenital_generation_control()
    assert result.stage == "generation"
    assert result.subreason == "ignore"
    assert ANCHOR_PHRASE in result.recalled_chunks[0].text
    assert result.draft == WRONG_DRAFT


def test_day06_chunk_params_are_explicit():
    assert CONGENITAL_CHUNK_WINDOW == 14
    assert CONGENITAL_CHUNK_STRIDE == 7
    chunks = recall_fixed_chunks(CONGENITAL_QUESTION)
    assert len(chunks) == 3
