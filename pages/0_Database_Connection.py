import streamlit as st
import sys
import os

# Add the parent directory to the path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dbaaiassist.pages.database_connection import show_database_connection

# Set page config
st.set_page_config(
    page_title="DBA AI Assistant - Database Connection",
    page_icon="🔌",
    layout="wide"
)

# Display the database connection page
show_database_connection()