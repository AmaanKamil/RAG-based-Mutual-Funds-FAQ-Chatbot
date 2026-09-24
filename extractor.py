import re
import sys
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup

def get_absolute_path(relative_path):
    """Convert relative path to absolute path based on the script's location."""
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (e.g., PyInstaller)
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
    return (base_path / relative_path).resolve()

def _clean_soup(soup):
    """Remove navigation, scripts and other boilerplate that pollutes the corpus."""
    for tag in soup(['script', 'style', 'noscript', 'svg', 'header', 'nav', 'footer', 'form', 'iframe']):
        tag.decompose()
    return soup


def _extract_exit_load_snippets(soup):
    """
    Find the smallest elements that mention exit load and return their text.
    Walks up a couple of levels so the value next to the label is included,
    but stops before grabbing a whole page section.
    """
    snippets = []
    for string in soup.find_all(string=re.compile(r'exit\s*load', re.I)):
        element = string.parent
        for _ in range(3):
            if element.parent is None or len(element.parent.get_text(' ', strip=True)) > 600:
                break
            element = element.parent
        text = element.get_text(' ', strip=True)
        if text and text not in snippets and len(text) <= 600:
            snippets.append(text)
    return snippets


def extract_text_from_url(url):
    """
    Extract readable text content from a URL.
    Exit load information is pulled out into a labelled section at the top
    (chunk.py keeps that section as its own chunk).
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = _clean_soup(BeautifulSoup(response.text, 'html.parser'))
    main = soup.find('main') or soup.body or soup

    exit_load_info = _extract_exit_load_snippets(main)
    # Keep block structure so chunk.py can split on paragraphs
    main_content = re.sub(r'\n\s*\n+', '\n\n', main.get_text('\n', strip=True).replace('\n', '\n\n'))

    if exit_load_info:
        return "EXIT LOAD INFORMATION: " + " | ".join(exit_load_info) + "\n\n" + main_content
    return main_content


def extract_corpus_from_file(csv_file=None):
    """
    Extract text corpus from URLs listed in a CSV file.
    Returns a list of dictionaries with 'url' and 'text' keys.
    """
    if csv_file is None:
        csv_file = get_absolute_path('groww.csv')
    else:
        csv_file = Path(csv_file)

    if not csv_file.exists():
        raise FileNotFoundError(
            f"CSV file not found at: {csv_file.absolute()}\n"
            "Please make sure the file exists and contains one URL per line."
        )

    print(f"Reading URLs from: {csv_file}")
    corpus = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    if not urls:
        print("Warning: No URLs found in the CSV file")
        return corpus

    print(f"Found {len(urls)} URLs to process")
    
    for i, url in enumerate(urls, 1):
        try:
            print(f"\n[{i}/{len(urls)}] Processing: {url}")
            text = extract_text_from_url(url)
            if text:
                corpus.append({
                    'url': url,
                    'text': text
                })
                print("✓ Successfully extracted text")
            else:
                print("⚠ No text extracted from URL")
        except Exception as e:
            print(f"❌ Error processing {url}: {str(e)}")
            continue
    
    print(f"\nExtraction complete. Successfully processed {len(corpus)} out of {len(urls)} URLs")
    return corpus

def generate_json_output(corpus, output_file=None):
    """
    Generates a JSON file from the extracted corpus.
    """
    if output_file is None:
        output_file = get_absolute_path('parsed_data.json')
    else:
        output_file = Path(output_file)
    
    output_dir = output_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert the corpus to a serializable format
    serializable_corpus = []
    for doc in corpus:
        try:
            serializable_corpus.append({
                'url': doc['url'],
                'text': doc['text'][:10000]  # Limit text length for JSON serialization
            })
        except (KeyError, TypeError):
            continue
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_corpus, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved extracted data to: {output_file.absolute()}")
        return str(output_file.absolute())
    except Exception as e:
        print(f"\n❌ Error saving JSON file: {e}")
        return None

if __name__ == "__main__":
    try:
        corpus = extract_corpus_from_file()
        if corpus:
            output_file = generate_json_output(corpus)
            if output_file:
                print(f"\n✅ Success! Data extracted and saved to: {output_file}")
            else:
                print("\n❌ Failed to save JSON output")
        else:
            print("\n❌ No data was extracted. Please check the input file and try again.")
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")
        sys.exit(1)