def chunk_text(text, max_length=800):
    """
    Split text into chunks with special handling for exit load information.
    Tries to keep related information together while respecting max_length.
    """
    if not text:
        return []
    
    # First, identify and extract exit load sections
    exit_load_sections = []
    remaining_text = text
    
    # Look for exit load sections (added by our enhanced extractor)
    if 'EXIT LOAD INFORMATION:' in text:
        parts = text.split('EXIT LOAD INFORMATION:')
        if len(parts) > 1:
            exit_load_section = parts[1].split('\n\n', 1)[0]
            exit_load_sections.append('EXIT LOAD INFORMATION:' + exit_load_section)
            remaining_text = parts[0] + (parts[1].split('\n\n', 1)[1] if '\n\n' in parts[1] else '')
    
    # Process the remaining text
    paragraphs = remaining_text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    # Add exit load sections as separate chunks first
    for section in exit_load_sections:
        if section.strip():
            chunks.append(section.strip())
    
    # Process regular paragraphs
    for para in paragraphs:
        para = para.strip()
        if not para or para in exit_load_sections:
            continue
            
        # If paragraph is about exit load, keep it as a separate chunk
        if 'exit load' in para.lower() or 'exitload' in para.lower().replace(' ', ''):
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            chunks.append(para)
            continue
            
        # If paragraph is too long, split it into sentences
        if len(para) > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # Try to split at sentence boundaries
            sentences = para.split('. ')
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                    
                # Add period back if it was at the end of the sentence
                if not sentence.endswith('.'):
                    sentence += '.'
                    
                if len(current_chunk) + len(sentence) + 1 < max_length:
                    current_chunk += ' ' + sentence if current_chunk else sentence
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence
        
        # If paragraph fits in current chunk, add it
        elif len(current_chunk) + len(para) + 2 < max_length:
            current_chunk += '\n\n' + para if current_chunk else para
        
        # Otherwise, start a new chunk
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para
    
    # Add any remaining content
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # Ensure no chunk is too large
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > max_length * 1.5:  # Allow some flexibility
            # Split very large chunks by sentence
            sentences = chunk.split('. ')
            temp_chunk = ""
            for sentence in sentences:
                if not sentence.strip():
                    continue
                if not sentence.endswith('.'):
                    sentence += '.'
                if len(temp_chunk) + len(sentence) + 1 < max_length:
                    temp_chunk += ' ' + sentence if temp_chunk else sentence
                else:
                    if temp_chunk:
                        final_chunks.append(temp_chunk.strip())
                    temp_chunk = sentence
            if temp_chunk:
                final_chunks.append(temp_chunk.strip())
        else:
            final_chunks.append(chunk)
    
    return final_chunks

def create_documents_from_corpus(corpus):
    """
    Create document chunks from corpus.
    corpus: list of dicts with 'url' and 'text' keys
    Returns: list of dicts with 'id', 'text', and 'metadata' keys
    """
    documents = []
    for item in corpus:
        url = item.get('url', '')
        text = item.get('text', '')
        if not text:
            continue
            
        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            # Create a safe ID from URL
            url_safe = url.replace('https://', '').replace('http://', '').replace('/', '_').replace('?', '_').replace('=', '_')
            doc_id = f"{url_safe}_chunk{idx}"
            
            documents.append({
                'id': doc_id,
                'text': chunk,
                'metadata': {
                    'url': url,
                    'chunk_index': idx,
                    'total_chunks': len(chunks)
                }
            })
    
    return documents
