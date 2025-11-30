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

        # Limit PGN length to prevent token limits/crashes
        if len(pgn_text) > 10000:
            pgn_text = pgn_text[:10000] + "... (truncated)"

        try:
            prompt = f"""
            You are a chess expert. Analyze the following chess game and the provided analysis summary.
            
            First, provide a short "Game Comment" (e.g., Sharp, Tactical, Brilliant, Chaotic, Positional Masterpiece, etc.) that captures the essence of the game.
            Then, provide a concise, insightful summary of the match (max 200 words).
            Highlight key turning points, brilliant moves, and major mistakes.
            
            Format:
            Game Comment: [Your Comment]
            
            Summary:
            [Your Summary]
            
            Analysis Summary:
            {analysis_summary}
            
            PGN:
            {pgn_text}
            """
            
            response = self.model.generate_content(prompt)
            if response and response.text:
                return response.text
            else:
                return "Error: Empty response from Gemini."
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}", exc_info=True)
            return f"Error generating summary: {e}"
