import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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
                                cells = row.find_all(['th', 'td'])
                                table_data.append(' | '.join(cell.get_text(strip=True) for cell in cells))
                            exit_load_info.append('\n'.join(table_data))
                        else:
                            exit_load_info.append(text)
            except Exception as e:
                print(f"  (Warning: Error processing selector {selector}: {e})")
        
        # Remove unwanted elements
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()

        main_content = soup.find('main') or soup.find('body')
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            static_text = '\n'.join(lines)

            # If sufficient content is extracted, return it
            # Add exit load information at the beginning of the content
            if exit_load_info:
                static_text = "EXIT LOAD INFORMATION:\n" + "\n\n".join(exit_load_info) + "\n\n" + static_text
            
            if len(static_text) > 500: # Heuristic to check if enough content was extracted
                return static_text

        # If static content is insufficient or it's a Groww page that likely needs dynamic rendering
        if 'groww.in' in url or len(static_text) <= 500:
            print(f"  (Falling back to Selenium for dynamic content extraction for {url})")
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            driver.get(url)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'main'))
            )
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            driver.quit()
            
            main_content = soup.find('main') or soup.find('body')
            if main_content:
                for elem in main_content.find_all(['nav', 'header', 'footer', 'script', 'style', 'aside']):
                    elem.decompose()
                
                text_parts = []
                for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'li', 'div']):
                    if element.name.startswith('h'):
                        text_parts.append(f"\n\n{element.get_text(strip=True)}\n")
                    elif element.name == 'p' or element.name == 'li':
                        text_parts.append(f"{element.get_text(strip=True)}\n")
                    elif element.name == 'div' and element.get_text(strip=True):
                        text_parts.append(f"{element.get_text(separator='\n', strip=True)}\n")

                full_text = '\n'.join(text_parts)
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                return '\n'.join(lines)
        
        return ""
    except requests.exceptions.RequestException as req_e:
        print(f"Error fetching {url} with requests: {req_e}")
        print(f"  (Falling back to Selenium for dynamic content extraction for {url})")
        # Fallback to Selenium if requests fails
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            driver.get(url)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'main'))
            )
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            driver.quit()
            
            main_content = soup.find('main') or soup.find('body')
            if main_content:
                for elem in main_content.find_all(['nav', 'header', 'footer', 'script', 'style', 'aside']):
                    elem.decompose()
                
                text_parts = []
                for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'p', 'li', 'div']):
                    if element.name.startswith('h'):
                        text_parts.append(f"\n\n{element.get_text(strip=True)}\n")
                    elif element.name == 'p' or element.name == 'li':
                        text_parts.append(f"{element.get_text(strip=True)}\n")
                    elif element.name == 'div' and element.get_text(strip=True):
                        text_parts.append(f"{element.get_text(separator='\n', strip=True)}\n")

                full_text = '\n'.join(text_parts)
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                return '\n'.join(lines)
            return ""
        except Exception as selenium_e:
            print(f"Error processing {url} with Selenium fallback: {selenium_e}")
            return ""
    except Exception as e:
        print(f"An unexpected error occurred for {url}: {e}")
        return ""

def extract_corpus_from_file(csv_file='groww.csv'):
    """
    Extract text corpus from URLs listed in a CSV file.
    Returns a list of dictionaries with 'url' and 'text' keys.
    """
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f.readlines() if line.strip()]
    except FileNotFoundError:
        print(f"Error: {csv_file} not found")
        return []
    
    corpus = []
    print(f"Extracting text from {len(urls)} URLs...")
    
    for idx, url in enumerate(urls, 1):
        print(f"[{idx}/{len(urls)}] Processing: {url}")
        text = extract_text_from_url(url)
        if text and len(text) > 50:
            corpus.append({
                'url': url,
                'text': text
            })
            print(f"  ✓ Extracted {len(text)} characters")
        else:
            print(f"  ✗ Failed to extract content or content too short")
        time.sleep(1)
    
    print(f"\nExtracted text from {len(corpus)} URLs successfully")
    return corpus

import json

def generate_json_output(corpus, output_file='parsed_data.json'):
    """
    Generates a JSON file from the extracted corpus, including placeholder questions.
    """
    json_output = []
    for item in corpus:
        # Placeholder questions - these would ideally be generated by an LLM
        # based on the content for a more robust solution.
        if "groww.in" in item['url']:
            questions = [
                f"What is the {item['url'].split('/')[-1].replace('-', ' ').title()}?",
                "What are the key features of this mutual fund?",
                "What are the investment objectives of this fund?"
            ]
        elif "sebi.gov.in" in item['url']:
            questions = [
                f"What are the details for the fund mentioned in {item['url']}?",
                "How can I find fund information on SEBI?",
                "What regulations apply to this fund?"
            ]
        else:
            questions = [
                f"What information is available at {item['url']}?",
                "What are the main topics discussed on this page?",
                "What questions can be answered from this content?"
            ]

        json_output.append({
            "url": item['url'],
            "extracted_text": item['text'],
            "potential_questions": questions
        })

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, ensure_ascii=False, indent=2)
    print(f"\nGenerated JSON output to {output_file}")

if __name__ == "__main__":
    corpus = extract_corpus_from_file()
    generate_json_output(corpus)
