"""
Streamlit UI for Facts-Only Mutual Fund FAQ Assistant
"""

import streamlit as st

from chunk import source_title
from config import KB_LAST_UPDATED
from rag_query import query_rag

st.set_page_config(
    page_title="Groww MF Facts Assistant",
    page_icon="📊",
    layout="centered",
)

st.markdown("""
    <style>
    .block-container { padding-top: 2.5rem; max-width: 780px; }
    .hero-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.1rem; }
    .hero-title span { color: #00B386; }
    .hero-sub { color: #5f6b76; margin-bottom: 1.2rem; }
    .notice {
        background: #F4F7F6; border-left: 4px solid #00B386; border-radius: 8px;
        padding: 0.7rem 1rem; font-size: 0.9rem; color: #3d4852; margin-bottom: 1.2rem;
    }
    .sources { font-size: 0.8rem; color: #6b7785; margin-top: 0.4rem; }
    .sources a { color: #00B386; text-decoration: none; }
    div[data-testid="stButton"] button {
        text-align: left; justify-content: flex-start; border-radius: 10px;
        border: 1px solid #e3e8ec; font-size: 0.88rem; min-height: 3rem;
    }
    div[data-testid="stButton"] button:hover { border-color: #00B386; color: #00B386; }
    </style>
""", unsafe_allow_html=True)

SCHEMES = [
    "Groww Value Fund",
    "Groww Large Cap Fund",
    "Groww Aggressive Hybrid Fund",
    "Groww Liquid Fund",
]

EXAMPLE_QUESTIONS = [
    "What is the expense ratio of Groww Value Fund?",
    "What is the minimum SIP amount for Groww Large Cap Fund?",
    "What is the exit load for Groww Aggressive Hybrid Fund?",
    "What is the riskometer rating of Groww Liquid Fund?",
    "Compare the expense ratio and exit load of all four funds",
    "Who is the fund manager of Groww Value Fund?",
]

if "messages" not in st.session_state:
    st.session_state.messages = []


def ask(question):
    st.session_state.pending_question = question


def render_sources(message):
    sources = message.get("sources") or ([message["citation"]] if message.get("citation") else [])
    links = " · ".join(f'<a href="{url}" target="_blank">{source_title(url)}</a>' for url in sources)
    if links:
        st.markdown(f'<div class="sources">📎 {links} &nbsp;|&nbsp; Data as of {message.get("timestamp", KB_LAST_UPDATED)}</div>',
                    unsafe_allow_html=True)


def show_answer(message):
    # Escape $ so Streamlit doesn't render amounts as LaTeX
    st.markdown(message["content"].replace("$", "\\$"))
    render_sources(message)


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### 📋 Covered schemes")
    st.markdown("\n".join(f"- {s} (Direct Growth)" for s in SCHEMES))
    st.markdown("### ℹ️ What I can answer")
    st.markdown("Expense ratio, exit load, minimum SIP / lump sum, riskometer, benchmark, "
                "fund manager, NAV, AUM and other factual scheme details.")
    st.caption(f"Knowledge base last updated: {KB_LAST_UPDATED}")
    if st.session_state.messages and st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ---------- Header ----------
st.markdown('<div class="hero-title">📊 <span>Groww</span> MF Facts Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Quick, sourced answers about Groww mutual fund schemes.</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="notice">⚠️ <b>Facts only. No investment advice.</b> Answers come from official scheme pages '
    '(Groww AMC, SEBI). For investment decisions, consult a SEBI-registered adviser.</div>',
    unsafe_allow_html=True,
)

prompt = st.chat_input("Ask about expense ratio, exit load, SIP, riskometer…")
if "pending_question" in st.session_state:
    prompt = st.session_state.pop("pending_question")

# ---------- Example questions (only on an empty chat) ----------
if not st.session_state.messages and not prompt:
    st.markdown("**Try asking:**")
    cols = st.columns(2)
    for idx, question in enumerate(EXAMPLE_QUESTIONS):
        cols[idx % 2].button(question, key=f"example_{idx}", on_click=ask, args=(question,),
                             use_container_width=True)

# ---------- Chat history ----------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            show_answer(message)
        else:
            st.markdown(message["content"])

# ---------- New question ----------
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Looking this up in the source documents…"):
            response = query_rag(prompt)
        message = {
            "role": "assistant",
            "content": response.get("answer", ""),
            "citation": response.get("citation"),
            "sources": response.get("sources", []),
            "timestamp": response.get("timestamp", KB_LAST_UPDATED),
            "refused": response.get("refused", False),
        }
        show_answer(message)
    st.session_state.messages.append(message)
