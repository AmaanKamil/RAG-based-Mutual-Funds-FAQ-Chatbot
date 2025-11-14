# Facts-Only Mutual Fund FAQ Assistant

A RAG-based chatbot that answers factual questions about mutual fund schemes using verified sources from AMC, SEBI, and AMFI websites. Provides concise, citation-backed responses while strictly avoiding any investment advice.

## Scope

**Product Selected:** Groww  
**AMC:** Groww Mutual Fund  
**Schemes Covered:**
- Groww Value Fund (Direct Growth)
- Groww Large Cap Fund (Direct Growth)
- Groww Aggressive Hybrid Fund (Direct Growth)
- Groww Liquid Fund (Direct Growth)

## Features

- ✅ Answers factual queries about mutual fund schemes
- ✅ Provides one citation link per answer
- ✅ Refuses investment advice questions with polite message
- ✅ Concise responses (max 3 sentences)
- ✅ Shows "Last updated from sources" timestamp
- ✅ Simple, user-friendly Streamlit interface

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Google Gemini API key
- Pinecone API key

### Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with your API keys:
```
GEMINI_API_KEY=your_gemini_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here
```

4. Add URLs to `groww.csv` (one URL per line). The file should contain 15-25 URLs from:
   - Groww mutual fund scheme pages
   - SEBI fund details pages
   - AMFI pages
   - Official factsheets and KIM/SID documents

5. Build the Pinecone index:
```bash
python build_index.py
```

This will:
- Extract text from all URLs in `groww.csv`
- Chunk the documents
- Generate embeddings using Google Gemini
- Store vectors in Pinecone

6. Run the Streamlit app:
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Project Structure

```
.
├── app.py              # Streamlit UI
├── build_index.py      # Script to build Pinecone index
├── chunk.py            # Text chunking utilities
├── extractor.py        # Web scraping for URLs
├── main.py             # OpenAI and Pinecone setup
├── rag_query.py        # RAG query processing
├── groww.csv           # List of source URLs
├── requirements.txt    # Python dependencies
├── README.md         # This file
├── sources.md          # List of all source URLs used
├── sample_qa.md        # Sample Q&A examples
└── disclaimer.txt      # Disclaimer text
```

## Usage

1. **Start the app:** Run `streamlit run app.py`

2. **Ask questions:** Type factual questions about mutual fund schemes, such as:
   - "What is the expense ratio of Groww Value Fund?"
   - "What is the minimum SIP amount for Groww Large Cap Fund?"
   - "What is the exit load for Groww Aggressive Hybrid Fund?"
   - "What is the lock-in period for ELSS schemes?"
   - "What is the riskometer rating for Groww Liquid Fund?"
   - "How to download capital gains statement from Groww?"

3. **View citations:** Each answer includes a source link to the official document

4. **Investment advice:** The assistant will politely refuse questions asking for investment advice and provide an educational link instead

## Known Limitations

1. **Limited corpus:** Currently uses 6 URLs. To reach 15-25 URLs as required, add more scheme pages, SEBI pages, and AMFI pages to `groww.csv`

2. **Web scraping:** Some pages may have dynamic content that requires JavaScript rendering. The current scraper handles static HTML content.

3. **Text extraction:** The quality of extracted text depends on the HTML structure of source pages. Some pages may require manual selector adjustments in `extractor.py`

4. **Embedding costs:** Generating embeddings for large corpora incurs Google Gemini API costs

5. **Pinecone storage:** Free tier has limits on vector storage. For larger corpora, consider Pinecone paid plans

6. **Response quality:** Responses depend on the quality and completeness of source documents. Some factual queries may not be answerable if information isn't in the corpus

## Technical Details

- **Embedding Model:** Google Gemini `models/embedding-001` (768 dimensions)
- **LLM Model:** Google Gemini `gemini-pro` for response generation
- **Vector Database:** Pinecone (serverless, AWS us-east-1)
- **Chunking:** Paragraph-based with max length of 500 characters
- **Retrieval:** Top 3 most similar chunks per query

## Disclaimer

This assistant provides factual information only. It does not provide investment advice, recommendations, or opinions. Always consult with a qualified financial advisor before making investment decisions.

For educational resources about mutual funds, visit: [AMFI Knowledge Center](https://www.amfiindia.com/investor-corner/knowledge-center)

## License

This project is for educational purposes as part of the NextLeap Generative AI Bootcamp.
