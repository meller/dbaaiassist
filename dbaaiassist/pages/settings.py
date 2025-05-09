import streamlit as st
from ..components.connection_manager import ConnectionManager

def show_settings():
    """Display the settings page."""
    st.title("PostgreSQL DBA Assistant Settings")
    
    # Initialize connection manager for the sidebar
    conn_manager = ConnectionManager()
    conn_manager.render_connection_status()
    
    # Create tabs for different settings categories
    tab1, tab2, tab3 = st.tabs(["General Settings", "Analysis Settings", "About"])
    
    with tab1:
        st.header("General Settings")
        
        # Theme settings
        st.subheader("Theme")
        theme = st.radio(
            "Select theme",
            options=["Light", "Dark", "System"],
            horizontal=True,
            index=2
        )
        
        # Initialize theme in session state if not present
        if "theme" not in st.session_state:
            st.session_state["theme"] = "System"
        
        # Update theme in session state if changed
        if theme != st.session_state["theme"]:
            st.session_state["theme"] = theme
            st.success(f"Theme set to {theme}. This will apply on the next run.")
        
        # Data retention
        st.subheader("Data Retention")
        
        retention_days = st.slider(
            "Number of days to retain analysis data",
            min_value=1,
            max_value=90,
            value=30,
            help="Data older than this will be automatically purged"
        )
        
        if st.button("Clear All Session Data", use_container_width=True):
            # Keys to preserve
            preserve_keys = ["theme", f"{conn_manager.key}_saved_connections"]
            
            # Store values we want to keep
            preserved_values = {key: st.session_state[key] for key in preserve_keys if key in st.session_state}
            
            # Clear session state
            for key in list(st.session_state.keys()):
                if key not in preserve_keys:
                    del st.session_state[key]
            
            # Restore preserved values
            for key, value in preserved_values.items():
                st.session_state[key] = value
                
            st.success("Session data cleared successfully.")
    
    with tab2:
        st.header("Analysis Settings")
        
        # Query analysis settings
        st.subheader("Query Analysis")
        
        default_slow_query_threshold = st.number_input(
            "Default slow query threshold (ms)",
            min_value=0,
            max_value=10000,
            value=100,
            step=10,
            help="Queries exceeding this execution time will be flagged as slow"
        )
        
        # Save to session state
        if "default_slow_query_threshold" not in st.session_state or st.session_state["default_slow_query_threshold"] != default_slow_query_threshold:
            st.session_state["default_slow_query_threshold"] = default_slow_query_threshold
            st.success(f"Default slow query threshold set to {default_slow_query_threshold} ms")
        
        # Recommendation settings
        st.subheader("Recommendations")
        
        min_impact_score = st.slider(
            "Minimum impact score for recommendations",
            min_value=0,
            max_value=100,
            value=20,
            step=5,
            help="Only show recommendations with impact score above this threshold"
        )
        
        # Save to session state
        if "min_impact_score" not in st.session_state or st.session_state["min_impact_score"] != min_impact_score:
            st.session_state["min_impact_score"] = min_impact_score
            st.success(f"Minimum impact score set to {min_impact_score}")
        
        # Auto-generate recommendations
        auto_recommendations = st.checkbox(
            "Automatically generate recommendations after log analysis",
            value=True,
            help="Generate recommendations automatically when log files are analyzed"
        )
        
        # Save to session state
        if "auto_recommendations" not in st.session_state or st.session_state["auto_recommendations"] != auto_recommendations:
            st.session_state["auto_recommendations"] = auto_recommendations
            state_text = "enabled" if auto_recommendations else "disabled"
            st.success(f"Automatic recommendations {state_text}")
    
    with tab3:
        st.header("About PostgreSQL DBA Assistant")
        
        st.markdown("""
        ### Version: 1.0.0
        
        PostgreSQL DBA Assistant is a tool designed to help database administrators analyze and optimize 
        PostgreSQL databases with a focus on query performance.
        
        **Key Features:**
        - Log file analysis to identify slow queries
        - Database schema exploration and insights
        - Index optimization recommendations
        - Query execution plan analysis
        
        ### Documentation
        
        For detailed documentation and user guides, please refer to:
        - [User Guide](/docs/USER_GUIDE.md)
        - [Frequently Asked Questions](/docs/FAQ.md)
        - [Contributing Guidelines](/docs/CONTRIBUTING.md)
        
        ### Feedback and Support
        
        We welcome your feedback and suggestions for improving this tool. 
        Please report any issues or feature requests through our GitHub repository.
        
        ### License
        
        This project is licensed under the MIT License - see the LICENSE file for details.
        
        ### Credits
        
        This tool uses several open-source libraries including:
        - Streamlit
        - Pandas
        - Plotly
        - Psycopg2
        - SQLParse
        
        ### Acknowledgements
        
        Special thanks to the PostgreSQL community for their excellent documentation and resources.
        """)
        
        # Version information
        st.subheader("System Information")
        
        # Display dependencies and versions
        import pandas as pd
        import plotly
        import psycopg2
        import streamlit
        
        dependencies = {
            "Python": f"{__import__('sys').version.split()[0]}",
            "Streamlit": streamlit.__version__,
            "Pandas": pd.__version__,
            "Plotly": plotly.__version__,
            "Psycopg2": psycopg2.__version__
        }
        
        # Create a DataFrame for nicer display
        deps_df = pd.DataFrame(list(dependencies.items()), columns=["Dependency", "Version"])
        st.dataframe(deps_df, hide_index=True, use_container_width=True)