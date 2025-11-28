import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv
from ..utils.logger import logger

class GeminiService:
    def __init__(self, api_key=None):
        self.model = None
        self.api_key = api_key
        
        # Try to load from .env if not provided
        if not self.api_key:
            try:
                if getattr(sys, 'frozen', False):
                    # If running as executable, load from bundled env.sample
                    base_path = sys._MEIPASS
                    load_dotenv(dotenv_path=os.path.join(base_path, '.env.sample'))
                else:
                    # If running from source, load from local .env
                    load_dotenv()
                
                self.api_key = os.getenv("GEMINI_KEY")
            except Exception:
                pass
                
        if self.api_key:
            self.configure(self.api_key)

    def configure(self, api_key):
        self.api_key = api_key
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-flash-latest')
        except Exception as e:
            logger.error(f"Failed to configure Gemini: {e}")
            self.model = None

    def generate_summary(self, pgn_text, analysis_summary):
        """
        Generates a game summary using Gemini.
        """
        if not self.model:
            return "Error: Gemini API key not configured or invalid."

        try:
            prompt = f"""
            You are a chess expert. Analyze the following chess game and the provided analysis summary.
            Provide a concise, insightful summary of the match (max 200 words).
            Highlight key turning points, brilliant moves, and major mistakes.
            
            Analysis Summary:
            {analysis_summary}
            
            PGN:
            {pgn_text}
            """
            
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return f"Error generating summary: {e}"
