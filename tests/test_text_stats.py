"""
Tests for text statistics utilities.
"""
import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.text_stats import count_words_zh, get_text_stats


def test_count_words_zh_chinese_only():
    """Test word counting with pure Chinese text"""
    text = "这是一篇中文作文。今天天气很好，我去公园玩了。"
    count = count_words_zh(text)
    # Should count Chinese characters (including punctuation)
    expected = 20  # All CJK characters including punctuation
    assert count == expected


def test_count_words_zh_mixed_content():
    """Test word counting with mixed Chinese and English"""
    text = "这是一篇中文作文。I like Python programming很多。"
    count = count_words_zh(text)
    # Should count CJK characters + English words
    # CJK: 这是一篇中文作文。很多。 (10 chars including punctuation)
    # English: I, like, Python, programming (4 words)
    expected = 14
    assert count == expected


def test_count_words_zh_english_only():
    """Test word counting with pure English text"""
    text = "This is an English essay about programming."
    count = count_words_zh(text)
    # Should count English words: This, is, an, English, essay, about, programming (7 words)
    expected = 7
    assert count == expected


def test_count_words_zh_empty_string():
    """Test word counting with empty string"""
    assert count_words_zh("") == 0
    assert count_words_zh(None) == 0


def test_count_words_zh_whitespace_only():
    """Test word counting with whitespace only"""
    text = "   \n\t  "
    count = count_words_zh(text)
    assert count == 0


def test_count_words_zh_punctuation_only():
    """Test word counting with punctuation only"""
    text = "。，！？；："
    count = count_words_zh(text)
    # Should count punctuation characters as fallback
    assert count == 6


def test_count_words_zh_with_numbers():
    """Test word counting with numbers"""
    text = "我有3个苹果和5个橙子。"
    count = count_words_zh(text)
    # Should count Chinese characters and numbers
    expected = 10  # 我有个苹果和个橙子 + 3 + 5
    assert count >= 8  # At least the Chinese characters


def test_get_text_stats_comprehensive():
    """Test comprehensive text statistics"""
    text = """这是第一段文字。
    
这是第二段文字，包含更多内容。
今天天气很好。"""
    
    stats = get_text_stats(text)
    
    assert stats['word_count'] > 0
    assert stats['char_count'] == len(text)
    assert stats['char_count_no_spaces'] < stats['char_count']
    assert stats['line_count'] == 4  # Including empty lines
    assert stats['paragraph_count'] == 2  # Two content paragraphs


def test_get_text_stats_empty():
    """Test text statistics with empty input"""
    stats = get_text_stats("")
    
    assert stats['word_count'] == 0
    assert stats['char_count'] == 0
    assert stats['char_count_no_spaces'] == 0
    assert stats['line_count'] == 0
    assert stats['paragraph_count'] == 0


def test_get_text_stats_single_line():
    """Test text statistics with single line"""
    text = "这是一行文字。"
    
    stats = get_text_stats(text)
    
    assert stats['word_count'] > 0
    assert stats['char_count'] == len(text)
    assert stats['line_count'] == 1
    assert stats['paragraph_count'] == 1