"""
Build Pinecone index from URLs in groww.csv
This script:
1. Extracts text from URLs using extractor.py
2. Chunks the text using chunk.py
3. Generates embeddings using main.py
4. Stores vectors in Pinecone
"""

import sys
import time

try:
    from extractor import extract_corpus_from_file, generate_json_output
    from chunk import create_documents_from_corpus
    from main import get_embedding, upsert_vectors
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please make sure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)

def build_index(csv_file='groww.csv'):
    """
    Complete pipeline to build the Pinecone index.
    """
    print("=" * 60)
    print("Building Pinecone Index for Mutual Fund FAQ")
    print("=" * 60)
    
    # Step 1: Extract text from URLs
    print("\n[Step 1/4] Extracting text from URLs...")
    try:
        corpus = extract_corpus_from_file(csv_file)
    except FileNotFoundError:
        print(f"Error: {csv_file} not found. Please create it with URLs (one per line).")
        return
    except Exception as e:
        print(f"Error extracting text from URLs: {e}")
        import traceback
        traceback.print_exc()
        return
    
    if not corpus:
        print("Error: No corpus extracted. Please check:")
        print("  1. groww.csv exists and has URLs (one per line)")
        print("  2. URLs are accessible")
        print("  3. Internet connection is working")
        return
    
    print(f"✓ Extracted {len(corpus)} documents")

    # Generate JSON output
    print("\n[Step 1.5/4] Generating JSON output of parsed data...")
    generate_json_output(corpus)
    print("✓ JSON output generated.")
    
    # Step 2: Chunk the documents
    print("\n[Step 2/4] Chunking documents...")
    documents = create_documents_from_corpus(corpus)
    print(f"✓ Created {len(documents)} chunks from {len(corpus)} documents")
    
    # Step 3: Generate embeddings
    print("\n[Step 3/4] Generating embeddings...")
    documents_with_embeddings = []
    failed_count = 0
    for idx, doc in enumerate(documents, 1):
        try:
            print(f"  [{idx}/{len(documents)}] Generating embedding for: {doc['id'][:50]}...")
            embedding = get_embedding(doc['text'])
            if embedding:
                doc['embedding'] = embedding
                documents_with_embeddings.append(doc)
            else:
                print(f"    ✗ Failed to generate embedding")
                failed_count += 1
            # Small delay to avoid rate limits
            time.sleep(0.1)
        except Exception as e:
            print(f"    ✗ Error generating embedding: {e}")
            failed_count += 1
    
    if failed_count > 0:
        print(f"⚠ Warning: {failed_count} embeddings failed to generate")
    
    print(f"✓ Generated {len(documents_with_embeddings)} embeddings")
    
    # Step 4: Upsert to Pinecone (with text in metadata)
    print("\n[Step 4/4] Uploading to Pinecone...")
    # Add text to metadata for retrieval
    for doc in documents_with_embeddings:
        doc['metadata']['text'] = doc['text'][:5000]  # Store first 5000 chars in metadata
    upsert_vectors(documents_with_embeddings)
    print(f"✓ Uploaded {len(documents_with_embeddings)} vectors to Pinecone")
    
    print("\n" + "=" * 60)
    print("Index build complete!")
    print("=" * 60)
    print(f"Total documents: {len(corpus)}")
    print(f"Total chunks: {len(documents_with_embeddings)}")
    print(f"Index name: mf-facts")
    print("=" * 60)

if __name__ == "__main__":
    build_index()
