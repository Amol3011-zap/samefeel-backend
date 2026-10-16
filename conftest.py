"""
Pytest configuration — adds the project root to sys.path
so that `from app.services.challenges_tracker import ...` resolves correctly.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
