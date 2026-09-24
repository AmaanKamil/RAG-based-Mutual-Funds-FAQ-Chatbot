"""
RAG Query System for Mutual Fund FAQ
Handles query processing, retrieval, and response generation with citations.
"""

import re

from openai import APIError, APITimeoutError, AuthenticationError, RateLimitError

from config import CHAT_MODEL, KB_LAST_UPDATED
from main import (
    SCHEMES, detect_facets, detect_schemes, get_openai_client,
    is_comparison_query, query_pinecone,
)

EDUCATIONAL_LINK = "https://www.amfiindia.com/investor-corner/knowledge-center"

# Word-boundary patterns that indicate a request for investment advice.
# Kept narrow on purpose: factual questions like "what is the portfolio turnover"
# or "top holdings in the portfolio" must NOT be refused.
ADVICE_PATTERNS = [
    r"\bshould i\b", r"\bshall i\b", r"\bcan i invest\b",
    r"\bis (it|this|that) (a )?(good|bad|safe|worth)\b", r"\bworth (it|investing|buying)\b",
    r"\brecommend", r"\badvi[cs]e\b", r"\bsuggest",
    r"\bbest\b", r"\bworst\b", r"\bbetter\b", r"\bgood (fund|investment|time)\b",
    r"\bwhich (one|fund|scheme)? ?(should|would|to)\b", r"\bwhere (should|to) i? ?invest\b",
    r"\bhow much (should i|to) invest\b", r"\ballocat(e|ion) my\b",
    r"\bwill (it|the fund|this fund) (go up|grow|give)\b", r"\bfuture returns?\b", r"\bpredict",
]

NOT_FOUND_ANSWER = (
    "I couldn't find this information in my source documents. "
    "Please try rephrasing your question or check the official scheme page directly."
)


def is_investment_advice_query(query):
    """
    Check if the query is asking for investment advice rather than facts.
    """
    query_lower = query.lower()
    return any(re.search(pattern, query_lower) for pattern in ADVICE_PATTERNS)


def _response(answer, citation=None, sources=None, refused=False):
    return {
        'answer': answer,
        'citation': citation,
        'sources': sources or ([citation] if citation else []),
        'refused': refused,
        'timestamp': KB_LAST_UPDATED,
    }


SYSTEM_PROMPT = """You are a facts-only assistant for Groww mutual fund schemes.
Answer ONLY from the numbered context passages supplied by the user. Never use outside knowledge.

Rules:
1. State exact figures (percentages, rupee amounts, holding periods, dates) exactly as they appear in the context.
2. If the question asks for several things (e.g. exit load AND expense ratio, or several schemes), answer every part.
   Use a short bullet list or a small markdown table when there are multiple parts or schemes.
3. For a single simple question, answer in at most 3 sentences.
4. If a requested fact is not in the context, say explicitly which part you could not find. Never guess.
5. Never give investment advice, opinions, recommendations or return predictions.
6. Do not include URLs or a "Source" line in your answer; citations are added separately."""


def get_facts_only_response(query, retrieved_chunks, model=CHAT_MODEL):
    """
    Generate a facts-only response using retrieved context.
    retrieved_chunks: list of {'text', 'url', 'score'} dicts, best first.
    """
    if not retrieved_chunks:
        return _response(NOT_FOUND_ANSWER)

    facets = detect_facets(query)
    schemes = detect_schemes(query)
    is_complex = len(facets) > 1 or len(schemes) > 1 or is_comparison_query(query)
    max_chunks = max(10, 4 * len(schemes)) if is_complex else 6

    # Build numbered context from unique chunks, keeping source URLs in rank order
    context_parts, sources, seen_texts = [], [], set()
    for chunk in retrieved_chunks:
        if len(context_parts) >= max_chunks:
            break
        text, url = chunk['text'], chunk['url']
        if text in seen_texts:
            continue
        seen_texts.add(text)
        context_parts.append(f"[{len(context_parts) + 1}] (source: {url})\n{text}")
        if url and url not in sources:
            sources.append(url)

    context = "\n\n".join(context_parts)
    scheme_hint = ""
    if schemes:
        scheme_hint = "\nSchemes asked about: " + ", ".join(schemes) + \
            ". Only use figures from passages that belong to these schemes (check the source URL)."

    user_prompt = f"""Context passages:
{context}

Question: {query}{scheme_hint}

Answer using only the context above."""

    try:
        response = get_openai_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=600 if is_complex else 300,
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            raise ValueError("Empty response from the model")
    except (AuthenticationError, RateLimitError, APITimeoutError, APIError) as e:
        print(f"API error: {e}")
        return _response("I'm having trouble reaching the AI service right now. Please try again in a moment.")
    except Exception as e:
        print(f"Error generating response: {e}")
        return _response("I ran into an unexpected error while answering. Please try again.")

    # Cite the scheme page(s) the question was about when we used them, else the top-ranked source
    scheme_urls = [SCHEMES[s][1] for s in schemes]
    preferred = [u for u in sources if u in scheme_urls]
    ordered_sources = preferred + [u for u in sources if u not in preferred]
    return _response(answer, citation=ordered_sources[0] if ordered_sources else None,
                     sources=ordered_sources[:max(3, len(schemes))])


def query_rag(user_query, top_k=5, model=CHAT_MODEL):
    """
    Main RAG query function.
    Returns a dict with 'answer', 'citation', 'sources', 'refused' and 'timestamp'.
    """
    user_query = (user_query or "").strip()
    if not user_query:
        return _response("Please enter a question about one of the covered mutual fund schemes.")

    if is_investment_advice_query(user_query):
        return _response(
            "I can only share factual information about mutual fund schemes (expense ratio, exit load, "
            "minimum SIP, riskometer, benchmark, etc.), not investment advice. For help deciding what to "
            "invest in, please consult a SEBI-registered investment adviser, or see AMFI's investor education resources.",
            citation=EDUCATIONAL_LINK,
            refused=True,
        )

    try:
        retrieved_chunks = query_pinecone(user_query, top_k=top_k)
    except Exception as e:
        print(f"Retrieval error: {e}")
        return _response("I couldn't search the knowledge base right now. Please try again in a moment.")

    return get_facts_only_response(user_query, retrieved_chunks, model=model)
