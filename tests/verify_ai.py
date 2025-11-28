import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.dirname(__file__))

from src.backend.gemini_service import GeminiService

class TestGeminiService(unittest.TestCase):
    def test_service_initialization(self):
        service = GeminiService()
        if service.model:
            print("GeminiService initialized successfully with API key.")
        else:
            print("GeminiService initialized without API key (or key invalid).")
            
    def test_generate_summary(self):
        service = GeminiService()
        if not service.model:
            print("Skipping generation test due to missing key.")
            return

        pgn = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6"
        summary_data = "{'white': {'accuracy': 90}, 'black': {'accuracy': 85}}"
        
        print("Requesting summary from Gemini...")
        summary = service.generate_summary(pgn, summary_data)
        print(f"Generated Summary: {summary[:100]}...")
        
        self.assertNotEqual(summary, "Error: Gemini API key not configured or invalid.")
        self.assertTrue(len(summary) > 10)

if __name__ == '__main__':
    unittest.main()
