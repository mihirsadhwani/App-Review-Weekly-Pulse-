import os
import streamlit as st
import google.generativeai as genai
from typing import Optional
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

def get_config(key):
    return os.getenv(key) or st.secrets.get(key)

class GeminiClient:
    def __init__(self):
        self.api_key = get_config("GEMINI_API_KEY")
        self.model: Optional[genai.GenerativeModel] = None
        
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("ERROR: GEMINI_API_KEY is missing from both environment variables and st.secrets.")
        else:
            genai.configure(api_key=self.api_key)
            # Using Gemini 1.5 Flash
            self.model = genai.GenerativeModel('gemini-flash-latest')

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
