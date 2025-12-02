"""Prompt templates for RAG answer generation.

Contains reusable prompt templates for different RAG tasks.
"""

# RAG answer generation template
RAG_ANSWER_TEMPLATE = """You are a helpful assistant that answers questions based on the provided context.

Context:
{context}

Question: {query}

Instructions:
- Answer the question using only the information from the context
- If the context doesn't contain enough information, say "I don't have enough information to answer this question"
- Be concise but complete
- Cite specific details from the context when relevant

Answer:"""


# Template for when no documents are found
NO_RESULTS_TEMPLATE = """I don't have any information about "{query}" in my knowledge base.

This could mean:
- The topic hasn't been indexed yet
- Your question might use different terminology than the documents
- Try rephrasing your question or using different keywords
"""


# Template for summarizing long context
SUMMARIZE_CONTEXT_TEMPLATE = """Summarize the following text concisely while preserving key information relevant to answering: {query}

Text:
{text}

Summary:"""


def build_rag_prompt(query: str, context: str) -> str:
    """Build RAG prompt from query and context.

    Args:
        query: User question
        context: Retrieved context

    Returns:
        Formatted prompt
    """
    return RAG_ANSWER_TEMPLATE.format(query=query, context=context)


def build_no_results_response(query: str) -> str:
    """Build response for when no documents are found.

    Args:
        query: User question

    Returns:
        No results message
    """
    return NO_RESULTS_TEMPLATE.format(query=query)


def build_summarize_prompt(query: str, text: str) -> str:
    """Build prompt for summarizing context.

    Args:
        query: Original query
        text: Text to summarize

    Returns:
        Summarization prompt
    """
    return SUMMARIZE_CONTEXT_TEMPLATE.format(query=query, text=text)
