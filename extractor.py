import os
import sys
import time
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def get_absolute_path(relative_path):
    """Convert relative path to absolute path based on the script's location."""
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle (e.g., PyInstaller)
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
    return (base_path / relative_path).resolve()

def extract_text_from_url(url):
    """
    Extract text content from a URL, with special handling for dynamic Groww pages.
    Special handling for exit load information extraction.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # First, try fetching with requests for static content
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # First, try to extract exit load information specifically
        exit_load_info = []
        
        # Common patterns for exit load information
        exit_load_selectors = [
            "div[data-testid*='exitLoad']",
            "div:contains('Exit Load')",
            "table:contains('Exit Load')",
            "p:contains('exit load')",
            "div:contains('exit load')",
            "div.fund-attributes",
            "div.fund-details",
            "div.key-information"
        ]
        
        for selector in exit_load_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(' ', strip=True)
                    if 'exit load' in text.lower() or 'exitload' in text.lower().replace(' ', ''):
                        if element.name == 'table':
                            # Format table data
                            rows = element.find_all('tr')
                            table_data = []
                            for row in rows:
                                cols = row.find_all('td')
                                if cols:
                                    table_data.append(' | '.join(col.get_text(strip=True) for col in cols))
                            if table_data:
                                exit_load_info.append("Exit Load Details:\n" + "\n".join(table_data))
                        else:
                            exit_load_info.append(text)
            except Exception as e:
                continue
        
        # If we found exit load info, prepend it to the main content
        if exit_load_info:
            exit_load_text = "\n\n".join(exit_load_info)
            main_content = soup.get_text(' ', strip=True)
            return f"{exit_load_text}\n\n{main_content}"
        
        # If no exit load info found, proceed with normal extraction
        main_content = soup.get_text(' ', strip=True)
        return main_content

    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

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