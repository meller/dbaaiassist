import streamlit as st
from ..components.connection_manager import ConnectionManager

def show_database_connection():
    """Display the database connection page."""
    st.title("PostgreSQL Database Connection")
    
    # Initialize connection manager
    conn_manager = ConnectionManager()
    
    # Show connection status in sidebar
    conn_manager.render_connection_status()
    
    # Tabs for different connection options
    tab1, tab2 = st.tabs(["New Connection", "Saved Connections"])
    
    with tab1:
        connection = conn_manager.render_connection_form()
        if connection:
            st.rerun()
    
    with tab2:
        connection = conn_manager.render_connection_selector()
    
    # Show connection status
    connector = conn_manager.get_current_connector()
    if connector and connector.is_connected():
        st.success("✅ Connected to database. You can now view database insights in the Database Overview page.")
    else:
        st.warning("Please connect to a PostgreSQL database to use the application features.")