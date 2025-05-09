"""
Streamlit page for AI Assistant.
This file makes the AI Assistant accessible from the Streamlit navigation menu.
"""

import sys
import os

# Add parent directory to path to allow imports from dbaaiassist
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the actual page implementation
from dbaaiassist.pages.ai_assistant import show

# Set page title and icon
import streamlit as st
st.set_page_config(
    page_title="AI Assistant - PostgreSQL DBA Assistant",
    page_icon="🤖",
    layout="wide"
)

# Display the page
show()