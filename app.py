"""
Streamlit UI for Facts-Only Mutual Fund FAQ Assistant
"""

import streamlit as st
from rag_query import query_rag
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Facts-Only MF Assistant",
    page_icon="📊",
    layout="wide"
)

# Custom CSS for better styling with Groww branding
st.markdown("""
    <style>
    .groww-header {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    .groww-logo {
        font-size: 2rem;
        font-weight: bold;
        color: #00D09C;
        text-decoration: none;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #00D09C;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        color: #666;
        margin-bottom: 1rem;
    }
    .scheme-info {
        background-color: #f8f9fa;
        border-left: 4px solid #00D09C;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
        color: #333;
        font-size: 0.95rem;
    }
    .disclaimer {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
        color: #856404;
        font-weight: 500;
    }
    .disclaimer strong {
        color: #856404;
    }
    .example-question {
        background-color: #f0f2f6;
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 4px;
        cursor: pointer;
    }
    .example-question:hover {
        background-color: #e0e2e6;
    }
    .citation {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.5rem;
    }
    .timestamp {
        font-size: 0.8rem;
        color: #999;
        margin-top: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Header with Groww branding
st.markdown("""
    <div class="groww-header">
        <span class="groww-logo">Groww</span>
    </div>
""", unsafe_allow_html=True)
st.markdown('<h1 class="main-header">📊 Facts-Only MF Assistant</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Get factual information about mutual fund schemes from verified sources</p>', unsafe_allow_html=True)

# Scheme coverage information
st.markdown("""
    <div class="scheme-info">
        <strong>📋 Covered Schemes:</strong><br>
        This chatbot answers questions about the following Groww mutual fund schemes:<br>
        • Groww Value Fund Direct Growth<br>
        • Groww Large Cap Fund Direct Growth<br>
        • Groww Aggressive Hybrid Fund Direct Growth<br>
        • Groww Liquid Fund Direct Growth
    </div>
""", unsafe_allow_html=True)

# Disclaimer with better visibility
st.markdown("""
    <div class="disclaimer">
        <strong>⚠️ Facts-only. No investment advice.</strong><br>
        This assistant provides factual information about mutual fund schemes from official sources (AMC, SEBI, AMFI). 
        It does not provide investment advice, recommendations, or opinions about which schemes to buy or sell.
    </div>
""", unsafe_allow_html=True)

# Example questions
st.markdown("### 💡 Example Questions")
example_questions = [
    "What is the expense ratio of Groww Value Fund?",
    "What is the minimum SIP amount for Groww Large Cap Fund?",
    "What is the exit load for Groww Aggressive Hybrid Fund?",
    "What is the lock-in period for ELSS schemes?",
    "What is the riskometer rating for Groww Liquid Fund?",
    "How to download capital gains statement from Groww?"
]

col1, col2, col3 = st.columns(3)
for idx, question in enumerate(example_questions[:3]):
    with [col1, col2, col3][idx]:
        if st.button(question, key=f"example_{idx}", use_container_width=True):
            st.session_state.user_input = question

# Chat interface
st.markdown("---")
st.markdown("### 💬 Ask a Question")

# User input
user_input = st.text_input(
    "Enter your question about mutual fund schemes:",
    value=st.session_state.get('user_input', ''),
    key="user_input_field",
    placeholder="e.g., What is the expense ratio of Groww Value Fund?"
)

if 'user_input' in st.session_state:
    user_input = st.session_state.user_input
    del st.session_state.user_input

# Display chat history
if st.session_state.messages:
    st.markdown("### 📜 Chat History")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "citation" in message and message["citation"]:
                st.markdown(f'<p class="citation">📎 Source: <a href="{message["citation"]}" target="_blank">{message["citation"]}</a></p>', unsafe_allow_html=True)
            if "timestamp" in message:
                st.markdown(f'<p class="timestamp">Last updated from sources: {message["timestamp"]}</p>', unsafe_allow_html=True)

# Process query
if user_input:
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Show user message
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Get response
    with st.chat_message("assistant"):
        with st.spinner("Searching for factual information..."):
            response = query_rag(user_input)
        
        # Display answer
        answer = response.get('answer', '')
        st.markdown(answer)
        
        # Display citation if available
        citation = response.get('citation')
        if citation:
            st.markdown(f'<p class="citation">📎 Source: <a href="{citation}" target="_blank">{citation}</a></p>', unsafe_allow_html=True)
        
        # Display timestamp
        timestamp = response.get('timestamp', datetime.now().strftime("%Y-%m-%d"))
        st.markdown(f'<p class="timestamp">Last updated from sources: {timestamp}</p>', unsafe_allow_html=True)
        
        # Add assistant message to history
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "citation": citation,
            "timestamp": timestamp,
            "refused": response.get('refused', False)
        })

# Footer
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem;">
        <p>This assistant uses information from official sources: AMC websites, SEBI, and AMFI.</p>
        <p>For educational resources, visit: <a href="https://www.amfiindia.com/investor-corner/knowledge-center" target="_blank">AMFI Knowledge Center</a></p>
    </div>
""", unsafe_allow_html=True)

