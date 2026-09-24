"""
Embedding + Pinecone helpers shared by the app (retrieval) and build_index.py (ingestion).
"""

import re
import time
from functools import lru_cache

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

from config import (
    OPENAI_API_KEY, PINECONE_API_KEY, INDEX_NAME,
    EMBEDDING_MODEL, EMBEDDING_DIMENSION,
)

# Minimum cosine similarity for a chunk to be used as context.
# text-embedding-3-small scores relevant matches roughly in the 0.3-0.6 range,
# so a higher cut-off silently drops good context.
MIN_SCORE = 0.25

# Scheme name -> (regex that detects it in a query, its source URL in the index)
SCHEMES = {
    "Groww Value Fund": (r"\bvalue\s+fund\b|\bgroww\s+value\b", "https://groww.in/mutual-funds/groww-value-fund-direct-growth"),
    "Groww Large Cap Fund": (r"\blarge\s*-?\s*cap\b", "https://groww.in/mutual-funds/groww-large-cap-fund-direct-growth"),
    "Groww Aggressive Hybrid Fund": (r"\b(aggressive|hybrid)\b", "https://groww.in/mutual-funds/groww-aggressive-hybrid-fund-direct-growth"),
    "Groww Liquid Fund": (r"\bliquid\b", "https://groww.in/mutual-funds/groww-liquid-fund-direct-growth"),
}

# Facet name -> regex (word-boundary aware, so "ter" doesn't match "interest")
FACETS = {
    "exit_load": r"exit\s*load|redemption|redeem|withdraw",
    "expense_ratio": r"expense\s*ratio|\bter\b",
    "sip": r"\bsips?\b|systematic investment|minimum (investment|amount)|lump\s*sum",
    "nav": r"\bnav\b|net asset value",
    "aum": r"\baum\b|assets under management|fund size",
}

# Standalone search phrases used to retrieve each facet of a multi-part question
FACET_QUERIES = {
    "exit_load": "Exit load if redeemed within",
    "expense_ratio": "Expense ratio",
    "sip": "Minimum SIP investment and minimum lumpsum investment",
    "nav": "Latest NAV net asset value",
    "aum": "Fund size AUM assets under management",
}

COMPARISON_PATTERN = r"\bcompare\b|\bcomparison\b|difference between|\bvs\.?\b|\bversus\b|which (\w+ )?(has|have)"


def detect_facets(text):
    text = text.lower()
    return {name for name, pattern in FACETS.items() if re.search(pattern, text)}


ALL_SCHEMES_PATTERN = r"\ball (the )?(four |4 )?(funds|schemes)\b|\beach (fund|scheme)\b|\bevery (fund|scheme)\b"


def detect_schemes(text):
    text = text.lower()
    if re.search(ALL_SCHEMES_PATTERN, text):
        return list(SCHEMES)
    return [name for name, (pattern, _) in SCHEMES.items() if re.search(pattern, text)]


def is_comparison_query(text):
    return bool(re.search(COMPARISON_PATTERN, text.lower())) or len(detect_schemes(text)) > 1


@lru_cache(maxsize=1)
def get_openai_client():
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set (add it to .env or Streamlit secrets)")
    return OpenAI(api_key=OPENAI_API_KEY)


@lru_cache(maxsize=1)
def get_pinecone_client():
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY is not set (add it to .env or Streamlit secrets)")
    return Pinecone(api_key=PINECONE_API_KEY)


@lru_cache(maxsize=1)
def get_index():
    return get_pinecone_client().Index(INDEX_NAME)


def ensure_index():
    """
    Create the index if it doesn't exist. Only called from build_index.py,
    never at app start-up. Never deletes an existing index.
    """
    pc = get_pinecone_client()
    if INDEX_NAME in [idx.name for idx in pc.list_indexes()]:
        dimension = pc.describe_index(INDEX_NAME).dimension
        if dimension != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Index '{INDEX_NAME}' has dimension {dimension}, expected {EMBEDDING_DIMENSION}. "
                "Delete it manually in the Pinecone console if you want to rebuild it."
            )
        return

    print(f"Creating index '{INDEX_NAME}' with dimension {EMBEDDING_DIMENSION}...")
    pc.create_index(
        name=INDEX_NAME,
        dimension=EMBEDDING_DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    while not pc.describe_index(INDEX_NAME).status["ready"]:
        time.sleep(1)
    print(f"Created index: {INDEX_NAME}")


def get_embedding(text, model=EMBEDDING_MODEL):
    """
    Generate embedding for text using OpenAI's embedding model.
    """
    try:
        response = get_openai_client().embeddings.create(input=text, model=model)
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None


def upsert_vectors(documents):
    """
    Upsert document vectors to Pinecone index.
    documents: list of dicts with 'id', 'embedding', and 'metadata' keys
    """
    vectors = [
        {'id': doc['id'], 'values': doc['embedding'], 'metadata': doc.get('metadata', {})}
        for doc in documents if doc.get('embedding')
    ]
    if not vectors:
        print("No valid vectors to upsert")
        return

    index = get_index()
    batch_size = 50
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        try:
            index.upsert(vectors=batch)
            print(f"Upserted batch {i // batch_size + 1} ({len(batch)} vectors)")
        except Exception as e:
            print(f"Error upserting batch: {e}")


def _query_index(query_embedding, top_k, url=None):
    """Raw Pinecone query, optionally restricted to a single source URL."""
    kwargs = {'filter': {'url': {'$eq': url}}} if url else {}
    return get_index().query(vector=query_embedding, top_k=top_k, include_metadata=True, **kwargs).matches


def query_pinecone(query_text, top_k=5):
    """
    Retrieve the most relevant chunks for a query.

    Pulls a wide candidate set from Pinecone, drops low-similarity matches and
    duplicate texts, then re-ranks by similarity plus small bonuses for chunks
    that come from a scheme named in the query or mention the requested facet
    (exit load, SIP, ...). When several schemes are asked about, each scheme is
    queried separately so every one of them is represented in the context.

    Returns a list of dicts: {'text', 'url', 'score'} (best first).
    Raises on connection/auth errors so the caller can show a proper message.
    """
    query_embedding = get_embedding(query_text)
    if not query_embedding:
        raise RuntimeError("Could not generate an embedding for the query")

    facets = detect_facets(query_text)
    schemes = detect_schemes(query_text)
    scheme_urls = [SCHEMES[s][1] for s in schemes]

    # A single embedding of a multi-part question ("exit load and expense ratio ...")
    # tends to miss one of the parts, so also search for each requested facet on its own
    embeddings = [query_embedding]
    if len(facets) > 1:
        for facet in sorted(facets):
            facet_embedding = get_embedding(FACET_QUERIES[facet])
            if facet_embedding:
                embeddings.append(facet_embedding)

    # Candidate pool is large because the index contains many near-duplicate chunks
    matches = []
    for embedding in embeddings:
        if len(scheme_urls) > 1:
            for url in scheme_urls:
                matches.extend(_query_index(embedding, top_k * 6, url=url))
        elif scheme_urls:
            # One scheme named: search its own page, plus a small unfiltered search (e.g. SEBI page)
            matches.extend(_query_index(embedding, top_k * 8, url=scheme_urls[0]))
            matches.extend(_query_index(embedding, top_k * 2))
        else:
            matches.extend(_query_index(embedding, top_k * 10))

    ranked, seen_texts = [], set()
    for match in sorted(matches, key=lambda m: m.score, reverse=True):
        metadata = match.metadata or {}
        text = metadata.get('text', '')
        url = metadata.get('url', '')
        if match.score < MIN_SCORE or not text or text in seen_texts:
            continue
        seen_texts.add(text)

        rank_score = match.score
        if scheme_urls and url in scheme_urls:
            rank_score += 0.1
        if facets:
            rank_score += 0.05 * len(facets & detect_facets(text))
        ranked.append({'text': text, 'url': url, 'score': match.score, '_rank': rank_score})

    ranked.sort(key=lambda c: c['_rank'], reverse=True)

    # Guarantee coverage: the best chunk for every (scheme, facet) pair goes first,
    # so no part of a multi-part / multi-scheme question gets crowded out
    groups = scheme_urls if len(scheme_urls) > 1 else [None]
    must_have = []
    for url in groups:
        in_group = [c for c in ranked if url is None or c['url'] == url]
        for facet in sorted(facets):
            # Prefer a chunk that states a figure ("Expense ratio: 0.9%") over one that only defines the term
            with_value = re.compile(rf"(?:{FACETS[facet]}).{{0,60}}?\d", re.I | re.S)
            best = next((c for c in in_group if with_value.search(c['text'])), None) or \
                next((c for c in in_group if facet in detect_facets(c['text'])), None)
            if best and best not in must_have:
                must_have.append(best)
        if not facets and in_group and in_group[0] not in must_have:
            must_have.append(in_group[0])
    ranked = must_have + [c for c in ranked if c not in must_have]

    max_results = max(top_k * 3, 4 * len(schemes)) if (len(schemes) > 1 or len(facets) > 1) else top_k * 2
    return ranked[:max_results]
