from __future__ import annotations
import math
from typing import List, Dict

def approx_token_count(text: str) -> int:
    # approx ~ 1 token ≈ 4 chars en anglais / 3-5 en fr ; on reste simple
    return max(1, math.ceil(len(text) / 4))

"""
Text chunking utilities for document processing
"""

from typing import List, Dict, Any, Optional


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    separators: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Split text into chunks with overlap
    
    Args:
        text: Input text to chunk
        chunk_size: Maximum size of each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks
        separators: List of separators to use for splitting (defaults to paragraphs, sentences)
    
    Returns:
        List of chunk dictionaries with text, metadata, and index
    """
    if separators is None:
        separators = [
            "\n\n",  # Paragraph breaks
            "\n",    # Line breaks
            ". ",    # Sentence ends
            "! ",    # Exclamation ends
            "? ",    # Question ends
            "; ",    # Semicolon
            ", ",    # Comma
            " ",     # Space
            ""       # Character level
        ]
    
    chunks = []
    start = 0
    chunk_index = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        
        # Try to find a good break point
        if end < len(text):
            best_end = end
            for separator in separators:
                if separator == "":
                    break
                
                # Look for separator near the end
                search_start = max(start, end - len(separator) * 10)
                last_sep = text.rfind(separator, search_start, end)
                
                if last_sep > start:
                    best_end = last_sep + len(separator)
                    break
            
            end = best_end
        
        # Extract chunk text
        chunk_text = text[start:end].strip()
        
        if chunk_text:  # Only add non-empty chunks
            chunk_data = {
                "text": chunk_text,
                "index": chunk_index,
                "metadata": {
                    "start_char": start,
                    "end_char": end,
                    "chunk_size": len(chunk_text)
                }
            }
            chunks.append(chunk_data)
            chunk_index += 1
        
        # Move start position with overlap
        start = max(start + 1, end - chunk_overlap)
    
    return chunks


def chunk_text_recursive(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Dict[str, Any]]:
    """
    Recursive text chunking that preserves semantic boundaries
    
    Args:
        text: Input text to chunk
        chunk_size: Target size of each chunk
        chunk_overlap: Number of characters to overlap
        
    Returns:
        List of chunk dictionaries
    """
    # Hierarchical separators
    separators = ["\n\n\n", "\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]
    
    def _split_text(text: str, separators: List[str]) -> List[str]:
        """Recursively split text using separators"""
        if not separators or len(text) <= chunk_size:
            return [text]
        
        separator = separators[0]
        splits = text.split(separator)
        
        result = []
        current_chunk = ""
        
        for split in splits:
            # If adding this split would exceed chunk size, process current chunk
            if current_chunk and len(current_chunk) + len(separator) + len(split) > chunk_size:
                if len(current_chunk) > chunk_size:
                    # Current chunk is too big, split it further
                    result.extend(_split_text(current_chunk, separators[1:]))
                else:
                    result.append(current_chunk)
                current_chunk = split
            else:
                if current_chunk:
                    current_chunk += separator + split
                else:
                    current_chunk = split
        
        # Add the last chunk
        if current_chunk:
            if len(current_chunk) > chunk_size:
                result.extend(_split_text(current_chunk, separators[1:]))
            else:
                result.append(current_chunk)
        
        return result
    
    # Split the text
    raw_chunks = _split_text(text, separators)
    
    # Add overlap and metadata
    chunks = []
    for i, chunk_text in enumerate(raw_chunks):
        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue
        
        # Add overlap from previous chunk
        if i > 0 and chunk_overlap > 0:
            prev_chunk = raw_chunks[i-1]
            overlap = prev_chunk[-chunk_overlap:] if len(prev_chunk) > chunk_overlap else prev_chunk
            chunk_text = overlap + " " + chunk_text
        
        chunk_data = {
            "text": chunk_text,
            "index": i,
            "metadata": {
                "chunk_index": i,
                "chunk_size": len(chunk_text),
                "has_overlap": i > 0 and chunk_overlap > 0
            }
        }
        chunks.append(chunk_data)
    
    return chunks
