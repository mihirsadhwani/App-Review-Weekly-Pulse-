import os
import streamlit as st

def get_config(key: str, default: str = None) -> str:
    """
    Priority: 1. os.getenv (for local .env)
             2. st.secrets (for Streamlit Cloud)
    """
    value = os.getenv(key) or st.secrets.get(key)
    if not value:
        # Check if we are in streamlit and it might be in a nested dict, 
        # but the request asks for direct st.secrets.get(key) or os.getenv(key)
        pass
    
    if not value and default is not None:
        return default
        
    if not value:
        print(f"WARNING: Configuration key '{key}' is missing from both environment variables and st.secrets.")
        
    return value
