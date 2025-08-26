"""
Minimal test to verify the _has_meaningful_content function works correctly.
"""

def _has_meaningful_content(content) -> bool:
    """
    Check if content has meaningful data (not empty, None, or whitespace-only).
    
    Args:
        content: Content to check (list, string, dict, etc.)
        
    Returns:
        True if content is meaningful, False otherwise
    """
    if not content:
        return False
    
    if isinstance(content, list):
        # Check if list has any non-empty, non-whitespace items
        for item in content:
            if isinstance(item, str) and item.strip():
                return True
            elif isinstance(item, dict):
                # For improvement suggestions, check if both original and suggested have content
                original = item.get('original', '').strip() if item.get('original') else ''
                suggested = item.get('suggested', '').strip() if item.get('suggested') else ''
                if original and suggested:
                    return True
        return False
    
    if isinstance(content, str):
        return bool(content.strip())
    
    if isinstance(content, dict):
        # For single improvement suggestion dict
        original = content.get('original', '').strip() if content.get('original') else ''
        suggested = content.get('suggested', '').strip() if content.get('suggested') else ''
        return bool(original and suggested)
    
    return bool(content)


def test_has_meaningful_content():
    """Test the _has_meaningful_content function"""
    
    # Test empty cases
    assert not _has_meaningful_content(None)
    assert not _has_meaningful_content([])
    assert not _has_meaningful_content("")
    assert not _has_meaningful_content("   ")
    assert not _has_meaningful_content({})
    
    # Test good sentences
    assert _has_meaningful_content(["Good sentence"])
    assert not _has_meaningful_content([""])
    assert not _has_meaningful_content(["", "  ", ""])
    assert _has_meaningful_content(["", "Good sentence", ""])
    
    # Test improvement suggestions
    assert _has_meaningful_content([{"original": "old", "suggested": "new"}])
    assert not _has_meaningful_content([{"original": "", "suggested": ""}])
    assert not _has_meaningful_content([{"original": "  ", "suggested": "  "}])
    assert not _has_meaningful_content([{"original": "old", "suggested": ""}])
    assert not _has_meaningful_content([{"original": "", "suggested": "new"}])
    
    # Mixed cases
    assert _has_meaningful_content([
        {"original": "", "suggested": ""},
        {"original": "old", "suggested": "new"}
    ])
    
    assert not _has_meaningful_content([
        {"original": "", "suggested": ""},
        {"original": "  ", "suggested": "  "}
    ])
    
    print("✓ All _has_meaningful_content tests passed!")


if __name__ == "__main__":
    test_has_meaningful_content()
    print("Helper function tests completed successfully!")