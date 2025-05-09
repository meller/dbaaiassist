import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any
from dbaaiassist.components.connection_manager import ConnectionManager

def show_home():
    """Display the home dashboard page."""
    st.title("PostgreSQL DBA Assistant Dashboard")
    
    # Initialize connection manager for the sidebar
    conn_manager = ConnectionManager()
    conn_manager.render_connection_status()
    
    # Check for analyzed queries in session state
    queries = st.session_state.get("analyzed_queries", [])
    recommendations = st.session_state.get("recommendations", [])
    
    # Display welcome message if no data
    if not queries and not recommendations:
        st.markdown("""
        ## Welcome to PostgreSQL DBA Assistant! 👋
        
        This tool helps you optimize your PostgreSQL database performance by analyzing:
        
        - Query execution logs
        - Database schema and statistics
        - Index usage patterns
        
        ### Getting Started
        
        1. Upload PostgreSQL log files in the **Log Analysis** page
        2. Connect to your PostgreSQL database in the **Database Insights** page
        3. View optimization recommendations in the **Recommendations** page
        
        ### Features
        
        - Identify slow-running queries
        - Detect missing indexes
        - Analyze query patterns
        - Generate optimization scripts
        """)
        
        # Quick action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Analyze Logs", use_container_width=True):
                st.switch_page("1_Log_Analysis.py")
        with col2:
            if st.button("🔌 Connect to Database", use_container_width=True):
                st.switch_page("2_Database_Insights.py")
                
        return
    
    # Display dashboard with metrics and visualizations
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Queries Analyzed", 
            value=len(queries) if queries else 0
        )
    
    with col2:
        st.metric(
            label="Recommendations", 
            value=len(recommendations) if recommendations else 0
        )
    
    with col3:
        if queries:
            avg_time = sum(q.execution_time_ms for q in queries) / len(queries)
            st.metric(
                label="Avg Query Time", 
                value=f"{avg_time:.2f} ms"
            )
        else:
            st.metric(label="Avg Query Time", value="N/A")
    
    # Display top slow queries if available
    if queries:
        st.subheader("Top 5 Slowest Queries")
        
        # Sort queries by execution time
        sorted_queries = sorted(
            queries, 
            key=lambda q: q.execution_time_ms, 
            reverse=True
        )[:5]
        
        # Create dataframe for display
        query_data = []
        for q in sorted_queries:
            query_text = q.query_text
            if len(query_text) > 100:
                query_text = query_text[:97] + "..."
                
            query_data.append({
                "Query": query_text,
                "Execution Time (ms)": q.execution_time_ms,
                "Tables": ", ".join(q.tables_accessed) if q.tables_accessed else "Unknown"
            })
        
        if query_data:
            df = pd.DataFrame(query_data)
            st.dataframe(df, use_container_width=True)
            
            # Create a bar chart
            fig = px.bar(
                df, 
                x="Query", 
                y="Execution Time (ms)",
                title="Top 5 Slowest Queries",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Display recent recommendations
    if recommendations:
        st.subheader("Recent Recommendations")
        
        # Sort recommendations by impact score
        sorted_recommendations = sorted(
            recommendations, 
            key=lambda r: r.impact_score, 
            reverse=True
        )[:5]
        
        # Create cards for each recommendation
        for rec in sorted_recommendations:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.markdown(f"### {rec.title}")
                    st.markdown(rec.description)
                    
                with col2:
                    impact_color = "green" if rec.impact_score >= 70 else "orange" if rec.impact_score >= 40 else "red"
                    st.markdown(f"""
                    <div style='background-color: {impact_color}; padding: 10px; border-radius: 5px; text-align: center; color: white;'>
                        <h1 style='margin: 0;'>{int(rec.impact_score)}</h1>
                        <p style='margin: 0;'>Impact</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.caption(f"Type: {rec.type.value.capitalize()}")
                
                if rec.sql_script:
                    with st.expander("View SQL Script"):
                        st.code(rec.sql_script, language="sql")
        
        # Show button to view all recommendations
        if st.button("View All Recommendations", use_container_width=True):
            st.switch_page("pages/3_Recommendations.py")