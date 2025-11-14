# Quick Setup Guide

## Step 1: Install Dependencies

Install all required Python packages:

```bash
pip3 install -r requirements.txt
```

Or if you're using a virtual environment (recommended):

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

This will install:
- `google-generativeai` - For embeddings and LLM responses
- `pinecone-client` - For vector database
- `beautifulsoup4` - For web scraping
- `requests` - For HTTP requests
- `streamlit` - For the UI
- `python-dotenv` - For environment variables
- `lxml` - For HTML parsing

**After installation, the import errors in your IDE should disappear!**

## Step 2: Set Up API Keys

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your actual API keys:
   ```
   GEMINI_API_KEY=your-actual-gemini-key
   PINECONE_API_KEY=your-actual-pinecone-key
   ```

   **Where to get API keys:**
   - Google Gemini: https://aistudio.google.com/app/apikey
   - Pinecone: https://app.pinecone.io/ (sign up for free tier)

## Step 3: Build the Index

This scrapes URLs from `groww.csv`, chunks the text, generates embeddings, and stores them in Pinecone:

```bash
python3 build_index.py
```

**Note:** This will take a few minutes depending on:
- Number of URLs in `groww.csv`
- API rate limits
- Network speed

You should see progress output like:
```
============================================================
Building Pinecone Index for Mutual Fund FAQ
============================================================

[Step 1/4] Extracting text from URLs...
[1/6] Processing: https://groww.in/...
  ✓ Extracted 1234 characters
...
```

## Step 4: Run the Application

Start the Streamlit app:

```bash
streamlit run app.py
```

This will:
1. Open your default web browser
2. Navigate to `http://localhost:8501`
3. Show the chatbot interface

## Troubleshooting

### Import errors still showing?
- Make sure you've run `pip install -r requirements.txt`
- Restart your IDE/editor
- If using a virtual environment, make sure it's activated

### API key errors?
- Check that `.env` file exists and has correct keys
- Make sure keys don't have quotes around them (unless they're part of the key)
- Verify keys are valid on OpenAI/Pinecone websites

### Pinecone index errors?
- Make sure you've created a Pinecone account
- Check that your API key has proper permissions
- The index will be created automatically on first run

### Web scraping not working?
- Some websites may block automated requests
- Check your internet connection
- URLs in `groww.csv` should be accessible
