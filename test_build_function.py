#!/usr/bin/env python3
"""
Test to check if build_teacher_view_evaluation properly handles 
empty data and provides fallback values
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app.reporting.service import build_teacher_view_evaluation
from app.reporting.docx_renderer import render_essay_docx

# Test the real build_teacher_view_evaluation function
# This will show us if the issue is in this function or in the data flow

def test_build_function():
    """Test the build_teacher_view_evaluation function with mock data"""
    # We need to check if the function itself provides fallbacks
    # Since we don't have a real database, we'll need to examine the function logic
    pass

if __name__ == "__main__":
    print("Testing the build function logic...")
    # We can't run this without a database, but we can examine the logic