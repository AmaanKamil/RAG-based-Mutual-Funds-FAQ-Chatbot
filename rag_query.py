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
    return any(keyword in query_lower for keyword in ADVICE_KEYWORDS)

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
        
    # Enhanced query understanding
    query_lower = query.lower()
    is_exit_load = any(term in query_lower for term in ['exit load', 'exitload', 'withdrawal', 'redemption'])
    is_expense_ratio = any(term in query_lower for term in ['expense ratio', 'expenseratio', 'ter'])
    is_sip = any(term in query_lower for term in ['sip', 'systematic investment plan', 'minimum investment'])
    is_nav = any(term in query_lower for term in ['nav', 'net asset value'])
    is_aum = any(term in query_lower for term in ['aum', 'assets under management'])
    
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
        
        if is_exit_load and ('exit load' in chunk_text or 'exitload' in chunk_text.replace(' ', '')):
            is_relevant = True
        elif is_expense_ratio and ('expense ratio' in chunk_text or 'ter' in chunk_text):
            is_relevant = True
        elif is_sip and ('sip' in chunk_text or 'systematic investment plan' in chunk_text or 'minimum investment' in chunk_text):
            is_relevant = True
        elif is_nav and ('nav' in chunk_text or 'net asset value' in chunk_text):
            is_relevant = True
        elif is_aum and ('aum' in chunk_text or 'assets under management' in chunk_text):
            is_relevant = True
            
        if is_relevant:
            relevant_chunks.append(chunk)
        else:
            other_chunks.append(chunk)
    
    # Combine chunks with relevant ones first
    retrieved_chunks = relevant_chunks + other_chunks
    
    # Get the most relevant chunk
    top_chunk = retrieved_chunks[0]
    if hasattr(top_chunk, 'metadata'):
        metadata = top_chunk.metadata
    else:
        metadata = top_chunk.get('metadata', {})
    
    context = metadata.get('text', '')
    citation_url = metadata.get('url', '')
    
    if not context:
        context = "Relevant information from source documents."
    
    # Build a more specific prompt based on the query type
    if is_exit_load:
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

    # Combine context from multiple chunks
    combined_context = context[:3000]  # First chunk
    for chunk in retrieved_chunks[1:3]:  # Add up to 2 more chunks
        if hasattr(chunk, 'metadata'):
            chunk_metadata = chunk.metadata
        else:
            chunk_metadata = chunk.get('metadata', {})
        chunk_text = chunk_metadata.get('text', '')
        if chunk_text:
            combined_context += "\n\n" + chunk_text[:1000]  # Add first 1000 chars of each additional chunk

    user_prompt = f"""Context from source document:
{combined_context}

Question: {query}

Provide a factual answer in maximum 3 sentences based ONLY on the context above. If the context doesn't contain the answer, say that you couldn't find this information in the source documents."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=150
        )
        
        # Check if we got a valid response
        if not response or not hasattr(response, 'choices') or not response.choices:
            raise ValueError("Invalid response from the model")
            
        answer = response.choices[0].message.content.strip()
        
        return {
            'answer': answer,
            'citation': citation_url if citation_url else None,
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
