import os
import google.generativeai as genai
from typing import Optional
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model: Optional[genai.GenerativeModel] = None
        
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("Gemini API key not found. Please add GEMINI_API_KEY to your .env file.")
        else:
            genai.configure(api_key=self.api_key)
            # Using Gemini 1.5 Flash
            self.model = genai.GenerativeModel('gemini-1.5-flash')

    def generate_with_gemini(self, prompt: str) -> str:
        if self.model is None:
            return "Error: Gemini client not initialized due to missing API key."
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error calling Gemini API: {str(e)}"

# Reusable function as requested
def generate_with_gemini(prompt: str) -> str:
    client = GeminiClient()
    return client.generate_with_gemini(prompt)
