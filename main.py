from dotenv import load_dotenv
import os
import time
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

load_dotenv()  # Load environment variables from .env

# Load keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text, model="text-embedding-3-small"):
    """
    Generate embedding for text using OpenAI's embedding model.
    """
    try:
        response = openai_client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

# Initialize Pinecone client (modern API)
pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "mf-facts"

# Create index if it doesn't exist, or recreate if dimension mismatch
existing_indexes = [idx.name for idx in pc.list_indexes()]
index_exists = index_name in existing_indexes

# Check if index exists and has correct dimension
if index_exists:
    try:
        index_info = pc.describe_index(index_name)
        if index_info.dimension != 1536:
            print(f"Warning: Existing index has dimension {index_info.dimension}, but we need 1536.")
            print(f"Deleting old index '{index_name}' to recreate with correct dimension...")
            pc.delete_index(index_name)
            # Wait for deletion to complete
            time.sleep(5)
            index_exists = False
    except Exception as e:
        print(f"Error checking index: {e}")
        index_exists = False

# Create index if it doesn't exist
if not index_exists:
    print(f"Creating index '{index_name}' with dimension 1536...")
    pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
    print(f"Created index: {index_name}")
    # Wait a moment for index to be ready (serverless indexes are usually ready quickly)
    time.sleep(5)

# Get the index
index = pc.Index(index_name)

def upsert_vectors(documents):
    """
    Upsert document vectors to Pinecone index.
    documents: list of dicts with 'id', 'embedding', and 'metadata' keys
    """
    if not documents:
        return
    
    # Prepare vectors in Pinecone format
    vectors = []
    for doc in documents:
        if doc.get('embedding'):
            vectors.append({
                'id': doc['id'],
                'values': doc['embedding'],
                'metadata': doc.get('metadata', {})
            })
    
    if not vectors:
        print("No valid vectors to upsert")
        return
    
    # Upsert in batches
    batch_size = 50
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i+batch_size]
        try:
            index.upsert(vectors=batch)
            print(f"Upserted batch {i//batch_size + 1} ({len(batch)} vectors)")
        except Exception as e:
            print(f"Error upserting batch: {e}")

def query_pinecone(query_text, top_k=5):
    """
    Query Pinecone index with a text query.
    Returns list of matches with metadata.
    """
    # Get embedding for the query
    query_embedding = get_embedding(query_text)
    if not query_embedding:
        return []
    
    try:
        # First, try to find exact matches for specific terms
        specific_terms = ['exit load', 'expense ratio', 'minimum sip', 'sip amount', 'nav', 'aum', 'returns']
        if any(term in query_text.lower() for term in specific_terms):
            # For specific financial queries, increase top_k to get more results
            results = index.query(
                vector=query_embedding,
                top_k=top_k * 2,  # Get more results for better filtering
                include_metadata=True,
                filter={
                    "text": {"$in": [query_text.lower()]}  # Try to match query terms
                }
            )
            
            # If no results with filter, try without filter
            if not results.matches:
                results = index.query(
                    vector=query_embedding,
                    top_k=top_k * 2,
                    include_metadata=True
                )
        else:
            # Regular query for general questions
            results = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
        
        # Filter out low-scoring results
        min_score = 0.6  # Adjust this threshold as needed
        filtered_matches = [match for match in results.matches if match.score >= min_score]
        
        # If we have filtered too many results, take the top ones
        return filtered_matches[:top_k]
        
    except Exception as e:
        print(f"Error querying Pinecone: {e}")
        return []
