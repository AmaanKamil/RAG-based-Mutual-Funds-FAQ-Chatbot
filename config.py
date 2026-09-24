"""
Shared configuration: reads secrets from Streamlit secrets (cloud) or .env (local).
"""

import os
from dotenv import load_dotenv

load_dotenv()


def get_secret(name, default=None):
    """
    Look up a secret in this order:
    1. Environment variable / .env
    2. st.secrets top-level key
    3. st.secrets["secrets"] section (for secrets.toml files with a [secrets] header)
    """
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
        if "secrets" in st.secrets and name in st.secrets["secrets"]:
            return st.secrets["secrets"][name]
    except Exception:
        # No secrets.toml available (e.g. running build_index.py locally)
        pass
    return default


OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
PINECONE_API_KEY = get_secret("PINECONE_API_KEY")

INDEX_NAME = "mf-facts"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
CHAT_MODEL = get_secret("CHAT_MODEL", "gpt-4o-mini")

# Date the knowledge base was last scraped and indexed (update after re-running build_index.py)
KB_LAST_UPDATED = get_secret("KB_LAST_UPDATED", "2025-11-14")
