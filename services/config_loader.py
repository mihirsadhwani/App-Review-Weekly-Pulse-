import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Priority: 1. os.getenv (local .env)
              2. st.secrets (Streamlit Cloud)
              3. default
    """
    value = os.getenv(key)
    if value:
        return value

    try:
        import streamlit as st
        value = st.secrets.get(key)
    except Exception:
        # No secrets.toml available (CLI runs, tests)
        value = None

    return value or default
