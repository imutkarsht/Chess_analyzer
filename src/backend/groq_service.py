import os
import sys
from groq import Groq
from dotenv import load_dotenv
from ..utils.logger import logger

class GroqService:
    def __init__(self, api_key=None, model_name="llama-3.3-70b-versatile"):
        self.client = None
        self.api_key = api_key
        self.model_name = model_name
        
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
                
                self.api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY")
            except Exception:
                pass
                
        if self.api_key:
            self.configure(self.api_key, self.model_name)

    def configure(self, api_key, model_name=None):
        self.api_key = api_key
        if model_name:
            self.model_name = model_name
        try:
            if self.api_key:
                self.client = Groq(api_key=self.api_key)
            else:
                self.client = None
        except Exception as e:
            logger.error(f"Failed to configure Groq: {e}")
            self.client = None

    def generate_summary(self, pgn_text, analysis_summary):
        """
        Generates a game summary using Groq.
        """
        if not self.client:
            return "Error: Groq API key not configured or invalid."

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
            
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model_name,
            )
            response_text = chat_completion.choices[0].message.content
            if response_text:
                return response_text.strip()
            return "No summary generated."
        except Exception as e:
            logger.error(f"Groq summary generation failed: {e}", exc_info=True)
            return f"Error generating summary: {e}"

    def generate_coach_insights(self, stats_text):
        """
        Generates coaching insights based on player statistics using Groq.
        """
        if not self.client:
            return "Error: Groq API key not configured."

        try:
            prompt = f"""
            You are a chess coach. Analyze the following statistics for your student:
            
            {stats_text}
            
            Provide 3 specific, actionable, and encouraging insights or tips based on this data.
            Focus on their win rate, accuracy, and any opening or phase-specific trends implied (e.g., if they win more as clear white, etc).
            Keep it concise (bullet points).
            Use emojis where appropriate.
            
            Format:
            1. [Insight 1]
            2. [Insight 2]
            3. [Insight 3]
            """
            
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model_name,
            )
            response_text = chat_completion.choices[0].message.content
            if response_text:
                return response_text.strip()
            return "No insights generated."
        except Exception as e:
            logger.error(f"Groq insight generation failed: {e}", exc_info=True)
            return f"Error generating insights: {e}"
