import streamlit as st
import os
import sys

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import pages
from dbaaiassist.pages.home import show_home
from dbaaiassist.pages.log_analysis import show_log_analysis
from dbaaiassist.pages.database_insights import show_database_insights
from dbaaiassist.pages.recommendations import show_recommendations
from dbaaiassist.pages.settings import show_settings

# Set page configuration
st.set_page_config(
    page_title="PostgreSQL DBA Assistant",
    page_icon="🐘",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define pages
PAGES = {
    "Dashboard": show_home,
    "Log Analysis": show_log_analysis,
    "Database Insights": show_database_insights,
    "Recommendations": show_recommendations,
    "Settings": show_settings
}

# Sidebar navigation
st.sidebar.title("PostgreSQL DBA Assistant")
st.sidebar.image("https://www.postgresql.org/media/img/about/press/elephant.png", width=100)
selection = st.sidebar.radio("Navigate to", list(PAGES.keys()))
 
# Display the selected page
PAGES[selection]()

# Footer
st.sidebar.markdown("---")
st.sidebar.info(
    "PostgreSQL DBA Assistant v1.0\n\n"
    "Query optimization tool for PostgreSQL databases"
)
