"""
RAG Query System for Mutual Fund FAQ
Handles query processing, retrieval, and response generation with citations.
"""

from main import get_embedding, query_pinecone
from datetime import datetime
import re
import os
from dotenv import load_dotenv
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, APITimeoutError

# Load environment variables
load_dotenv()

# Initialize the client based on available API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Initialize the appropriate client and model
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
    model = "gpt-3.5-turbo"  # or "gpt-4" if you have access
elif OPENROUTER_API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY
    )
    model = "openai/gpt-3.5-turbo"  # OpenRouter format
else:
    raise ValueError("No API key found. Please set either OPENAI_API_KEY or OPENROUTER_API_KEY in .env file")

# Keywords that indicate investment advice requests
ADVICE_KEYWORDS = [
    'should i', 'should i buy', 'should i sell', 'should i invest',
    'is it good', 'is it bad', 'is it worth', 'worth investing',
    'recommend', 'recommendation', 'advice', 'suggest',
    'best', 'worst', 'better', 'compare returns', 'which is better',
    'portfolio', 'allocation', 'how much to invest'
]

EDUCATIONAL_LINK = "https://www.amfiindia.com/investor-corner/knowledge-center"

def is_investment_advice_query(query):
    """
    Check if the query is asking for investment advice.
    """
    query_lower = query.lower()
    
    # Check for comparison queries that are not just asking for facts
    if any(term in query_lower for term in ['which is better', 'should i choose', 'which one should i pick']):
        return True
        
    # Check for other investment advice patterns
    advice_phrases = [
        'should i', 'should i buy', 'should i sell', 'should i invest',
        'is it good', 'is it bad', 'is it worth', 'worth investing',
        'recommend', 'recommendation', 'advice', 'suggest',
        'best', 'worst', 'better', 'compare returns',
        'portfolio', 'allocation', 'how much to invest',
        'which would you recommend', 'which would you choose'
    ]
    
    return any(phrase in query_lower for phrase in advice_phrases)

def format_citation(url):
    """
    Format URL as a citation link.
    """
    return f"[Source]({url})"

def get_facts_only_response(query, retrieved_chunks, model=model):
    """
    Generate a facts-only response using retrieved context.
    Max 3 sentences, includes citation.
    Special handling for different types of mutual fund queries.
    """
    if not retrieved_chunks:
        return {
            'answer': "I couldn't find relevant information in the source documents. Please try rephrasing your question or check the official sources directly.",
            'citation': None,
            'timestamp': datetime.now().strftime("%Y-%m-%d")
        }
    # Initialize citations set
    citations = set()

    # Enhanced query understanding
    query_lower = query.lower()
    is_exit_load = any(term in query_lower for term in ['exit load', 'exitload', 'withdrawal', 'redemption'])
    is_expense_ratio = any(term in query_lower for term in ['expense ratio', 'expenseratio', 'ter'])
    is_sip = any(term in query_lower for term in ['sip', 'systematic investment plan', 'minimum investment'])
    is_nav = any(term in query_lower for term in ['nav', 'net asset value'])
    is_aum = any(term in query_lower for term in ['aum', 'assets under management'])
    is_comparison = any(term in query_lower for term in ['compare', 'which has', 'which one has', 'difference between', 'vs', 'versus'])
    
    # Extract scheme names for comparison
    scheme_names = []
    if is_comparison:
        # Look for common mutual fund scheme names in the query
        schemes = ['Groww Value Fund', 'Groww Large Cap Fund', 'Groww Aggressive Hybrid Fund', 'Groww Liquid Fund']
        scheme_names = [scheme for scheme in schemes if scheme.lower() in query_lower]
    
    # Reorder chunks based on relevance to the query
    relevant_chunks = []
    other_chunks = []
    
    for chunk in retrieved_chunks:
        if hasattr(chunk, 'metadata'):
            metadata = chunk.metadata
        else:
            metadata = chunk.get('metadata', {})
        
        chunk_text = metadata.get('text', '').lower()
        is_relevant = False
        relevance_score = 0
        
        # Score relevance based on query type
        # In rag_query.py, update the relevance scoring section
        if is_exit_load and ('exit load' in chunk_text or 'exitload' in chunk_text.replace(' ', '')):
            relevance_score += 5  # Increased weight for exit load
            is_relevant = True
        if is_expense_ratio and ('expense ratio' in chunk_text or 'ter' in chunk_text):
            relevance_score += 5  # Increased weight for expense ratio
            is_relevant = True
        if is_sip and ('sip' in chunk_text or 'systematic investment plan' in chunk_text or 'minimum investment' in chunk_text):
            relevance_score += 5  # Increased weight for SIP
            is_relevant = True
        if is_nav and ('nav' in chunk_text or 'net asset value' in chunk_text):
            relevance_score += 2
            is_relevant = True
        if is_aum and ('aum' in chunk_text or 'assets under management' in chunk_text):
            relevance_score += 2
            is_relevant = True
        if is_comparison and any(scheme.lower() in chunk_text for scheme in scheme_names):
            relevance_score += 3  # Higher weight for scheme-specific info in comparisons
            
        if is_relevant:
            chunk.relevance_score = relevance_score
            relevant_chunks.append(chunk)
        else:
            other_chunks.append(chunk)
    
    # Sort relevant chunks by relevance score (highest first)
    relevant_chunks.sort(key=lambda x: getattr(x, 'relevance_score', 0), reverse=True)
    
    # Combine chunks with relevant ones first
    retrieved_chunks = relevant_chunks + other_chunks
    
    # In rag_query.py, update the context building part
    # Get more chunks for multi-faceted queries
    is_multi_faceted = (is_exit_load + is_expense_ratio + is_sip + is_nav + is_aum) > 1
    max_chunks = 10 if is_multi_faceted else 5
    top_chunks = retrieved_chunks[:max_chunks]

    # Build context from top chunks, removing duplicates
    context_parts = []
    seen_texts = set()

    for chunk in top_chunks:
        if hasattr(chunk, 'metadata'):
            metadata = chunk.metadata
        else:
            metadata = chunk.get('metadata', {})
        
        text = metadata.get('text', '')
        url = metadata.get('url', '')
        
        # Only add unique text to avoid redundancy
        if text and text not in seen_texts:
            seen_texts.add(text)
            context_parts.append(text)
        if url:
            citations.add(url)

    context = "\n\n".join(context_parts)
    citation = next(iter(citations), None)  # Get the first citation if available
    
    # Build a more specific prompt based on the query type
    # Update the system prompt for multi-faceted queries
    if is_exit_load + is_expense_ratio + is_sip > 1:  # Multiple information types requested
        system_prompt = """You are an expert mutual fund assistant providing multiple pieces of information.
        Your role is to provide clear, factual answers to all parts of the query based on the provided context.

        Rules for responses:
        1. Address each part of the query separately
        2. Be specific about the values (e.g., percentages, amounts)
        3. If information for any part is missing, clearly state what's missing
        4. Keep the response well-structured and easy to read
        5. Always cite the source URL for the information
        """
    elif is_comparison:
        system_prompt = """You are an expert mutual fund assistant specializing in comparing different mutual fund schemes. 
        Your role is to provide clear, factual comparisons based on the provided context.

        Rules for comparison responses:
        1. List each scheme and its relevant details in a clear, structured format
        2. Be specific about the values being compared (expense ratios, exit loads, etc.)
        3. If the context contains information for some schemes but not others, clearly state what information is missing
        4. Keep the response concise but comprehensive
        5. Always cite the source URL for the information
        """
    elif is_exit_load:
        system_prompt = """You are an expert mutual fund assistant specializing in exit load information. 
        Your role is to provide clear, accurate information about exit loads based on the provided context.

        Rules for exit load responses:
        1. Be specific about the exit load percentage and holding period
        2. If multiple exit loads are mentioned, list them clearly
        3. If no exit load is mentioned, state that clearly
        4. Keep the response concise but complete (max 3 sentences)
        5. Always cite the source URL for the information
        """
    elif is_expense_ratio:
        system_prompt = """You are an expert mutual fund assistant specializing in expense ratio information. 
        Your role is to provide clear, accurate information about expense ratios based on the provided context.

        Rules for expense ratio responses:
        1. State the exact expense ratio percentage if available
        2. Mention if it's the direct or regular plan if specified
        3. Note any additional charges if mentioned
        4. Keep the response concise (max 3 sentences)
        5. Always cite the source URL for the information
        """
    elif is_sip:
        system_prompt = """You are an expert mutual fund assistant specializing in SIP information. 
        Your role is to provide clear, accurate information about SIPs based on the provided context.

        Rules for SIP responses:
        1. State the minimum SIP amount if available
        2. Mention any frequency options (monthly, quarterly, etc.)
        3. Note any special conditions or requirements
        4. Keep the response concise (max 3 sentences)
        5. Always cite the source URL for the information
        """
    else:
        system_prompt = """You are a facts-only assistant for mutual fund information. Your role is to provide concise, factual answers based ONLY on the provided context. 

        Rules:
        1. Answer in maximum 3 sentences
        2. Only state facts from the context - no opinions, no advice
        3. Be precise and clear
        4. If the context doesn't contain the answer, say so clearly
        5. Never provide investment advice, recommendations, or comparisons of returns
        6. Focus on factual information like expense ratios, exit loads, minimum SIP amounts, etc."""

    if is_multi_faceted:
        user_prompt = f"""Context from source documents:
{context}

Question: {query}

Please provide a complete response addressing all requested metrics. For each metric:

1. Exit Load (if requested):
   - State the exit load percentage
   - Mention any holding period requirements
   - Example: "Exit Load: 1% if redeemed within 1 year"

2. Expense Ratio (if requested):
   - State the exact percentage
   - Mention if it's for direct or regular plan if specified
   - Example: "Expense Ratio: 0.50% (Direct Plan)"

3. Minimum SIP Amount (if requested):
   - State the minimum amount
   - Mention any frequency options if available
   - Example: "Minimum SIP: ₹500 per month"

If any information is not available in the context, clearly state which specific metric is missing.

Format your response with clear section headers for each metric."""
    else:
        user_prompt = f"""Context from source documents:
{context}


Question: {query}

Provide a factual answer based ONLY on the context above. If the context doesn't contain the answer, say that you couldn't find this information in the source documents."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=500 if is_comparison else 250  # Allow more tokens for comparison responses
        )
        
        # Check if we got a valid response
        if not response or not hasattr(response, 'choices') or not response.choices:
            raise ValueError("Invalid response from the model")
            
        answer = response.choices[0].message.content.strip()
        
        return {
            'answer': answer,
            'citation': citation,
            'timestamp': datetime.now().strftime("%Y-%m-%d")
        }
    except (APIError, AuthenticationError, RateLimitError, APITimeoutError) as e:
        print(f"API error: {e}")
        return {
            'answer': f"I'm having trouble connecting to the AI service. Error: {str(e)[:200]}",
            'citation': None,
            'timestamp': datetime.now().strftime("%Y-%m-%d")
        }
    except Exception as e:
        print(f"Error generating response: {e}")
        return {
            'answer': "I encountered an unexpected error while processing your request. Please try rephrasing your question or try again later.",
            'citation': None,
            'timestamp': datetime.now().strftime("%Y-%m-%d")
        }
   

def query_rag(user_query, top_k=5, model=model):
    """
    Main RAG query function.
    Returns a dictionary with 'answer', 'citation', 'refused', and 'timestamp'.
    
    Args:
        user_query (str): The user's query
        top_k (int): Number of chunks to retrieve
        model (str): The model to use for generating responses
    """
    # Check if this is an investment advice query
    if is_investment_advice_query(user_query):
        return {
            'answer': f"I can only provide factual information about mutual fund schemes, not investment advice. For educational resources about mutual funds, please visit: {EDUCATIONAL_LINK}",
            'citation': EDUCATIONAL_LINK,
            'refused': True,
            'timestamp': datetime.now().strftime("%Y-%m-%d")
        }
    
    # Get relevant chunks from Pinecone (retrieve more for better context)
    retrieved_chunks = query_pinecone(user_query, top_k=top_k)
    
    if not retrieved_chunks:
        return {
            'answer': "I couldn't find relevant information in the source documents. Please try rephrasing your question or check the official sources directly.",
            'citation': None,
            'refused': False,
            'timestamp': datetime.now().strftime("%Y-%m-%d")
        }
    
    # Generate response
    response = get_facts_only_response(user_query, retrieved_chunks, model=model)
    response['refused'] = False
    
    return response
