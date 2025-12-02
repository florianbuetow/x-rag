"""Tests for prompt templates."""

from src.pipelines.prompt_templates import (
    RAG_ANSWER_TEMPLATE,
    build_no_results_response,
    build_rag_prompt,
    build_summarize_prompt,
)


def test_rag_answer_template_has_placeholders() -> None:
    """Test that RAG answer template has required placeholders."""
    assert "{context}" in RAG_ANSWER_TEMPLATE
    assert "{query}" in RAG_ANSWER_TEMPLATE


def test_build_rag_prompt() -> None:
    """Test building RAG prompt."""
    query = "What is Python?"
    context = "Python is a programming language."

    prompt = build_rag_prompt(query, context)

    assert query in prompt
    assert context in prompt
    assert "Answer the question" in prompt


def test_build_no_results_response() -> None:
    """Test building no results response."""
    query = "test query"

    response = build_no_results_response(query)

    assert query in response
    assert "don't have any information" in response


def test_build_summarize_prompt() -> None:
    """Test building summarize prompt."""
    query = "What is X?"
    text = "Long text to summarize"

    prompt = build_summarize_prompt(query, text)

    assert query in prompt
    assert text in prompt
    assert "Summary:" in prompt
