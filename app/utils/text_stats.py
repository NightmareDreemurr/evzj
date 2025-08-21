"""
Text statistics utilities, particularly for Chinese text processing.
"""
import re
import logging

logger = logging.getLogger(__name__)


def count_words_zh(text: str) -> int:
    """
    Count words in Chinese text more accurately than simple character count.
    
    For Chinese text, this function:
    1. Counts CJK (Chinese, Japanese, Korean) characters
    2. Collapses whitespace and punctuation 
    3. For mixed Chinese/English text, counts English words separately
    
    Args:
        text: The text to count words in
        
    Returns:
        Word count as integer
    """
    if not text:
        return 0
        
    try:
        # Remove excessive whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Count CJK characters (Chinese, Japanese, Korean)
        # CJK ranges: 4E00-9FFF (main), 3400-4DBF (extension A), F900-FAFF (compatibility)
        cjk_pattern = r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]'
        cjk_chars = re.findall(cjk_pattern, text)
        cjk_count = len(cjk_chars)
        
        # Remove CJK characters to count English/Western words
        text_without_cjk = re.sub(cjk_pattern, ' ', text)
        
        # Count English words (sequences of letters)
        english_words = re.findall(r'\b[a-zA-Z]+\b', text_without_cjk)
        english_count = len(english_words)
        
        # For pure Chinese text, return CJK character count
        # For mixed text, return CJK characters + English words
        total_count = cjk_count + english_count
        
        # Fallback: if no CJK or English detected, count non-whitespace characters
        if total_count == 0:
            non_whitespace = re.sub(r'\s+', '', text)
            total_count = len(non_whitespace)
            
        logger.debug(f"Word count: {total_count} (CJK: {cjk_count}, EN: {english_count})")
        return total_count
        
    except Exception as e:
        logger.error(f"Error counting words: {e}")
        # Fallback to character count minus whitespace
        return len(text.replace(' ', '').replace('\n', '').replace('\t', ''))


def get_text_stats(text: str) -> dict:
    """
    Get comprehensive text statistics.
    
    Args:
        text: The text to analyze
        
    Returns:
        Dictionary with various text statistics
    """
    if not text:
        return {
            'word_count': 0,
            'char_count': 0,
            'char_count_no_spaces': 0,
            'line_count': 0,
            'paragraph_count': 0
        }
        
    try:
        word_count = count_words_zh(text)
        char_count = len(text)
        char_count_no_spaces = len(text.replace(' ', '').replace('\n', '').replace('\t', ''))
        line_count = len(text.splitlines())
        
        # Count paragraphs (separated by double newlines or single newlines with content)
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        paragraph_count = len(paragraphs)
        
        return {
            'word_count': word_count,
            'char_count': char_count,
            'char_count_no_spaces': char_count_no_spaces,
            'line_count': line_count,
            'paragraph_count': paragraph_count
        }
        
    except Exception as e:
        logger.error(f"Error getting text stats: {e}")
        return {
            'word_count': 0,
            'char_count': len(text) if text else 0,
            'char_count_no_spaces': 0,
            'line_count': 0,
            'paragraph_count': 0
        }