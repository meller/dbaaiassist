import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any
from ..components.connection_manager import ConnectionManager
from ..models.recommendation import Recommendation, RecommendationStatus

def show_recommendations():
    """Display the recommendations page."""
    st.title("PostgreSQL Optimization Recommendations")
    
    # Initialize connection manager for the sidebar
    conn_manager = ConnectionManager()
    conn_manager.render_connection_status()
    
    # Get recommendations from session state
    recommendations = st.session_state.get("recommendations", [])
    
    if not recommendations:
        st.info("No recommendations available yet. Analyze logs or database to generate recommendations.")
        
        # Show guidance on how to get recommendations
        st.markdown("""
        ### How to get recommendations:
        
        1. **Upload and analyze PostgreSQL log files** in the Log Analysis page
        2. **Connect to your database** in the Database Insights page
        3. The system will analyze query patterns and provide optimization suggestions
        
        Recommendations will help you improve performance by suggesting:
        - Missing indexes
        - Table structure improvements
        - Query optimizations
        """)
        
        # Quick action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Analyze Logs", use_container_width=True):
                st.switch_page("../pages/1_Log_Analysis.py")
        with col2:
            if st.button("🔍 Database Insights", use_container_width=True):
                st.switch_page("Database Insights")
        
        return
    
    # Filter and sort options
    st.markdown("### Recommendation Filters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filter by type
        all_types = sorted(list(set(r.type.value for r in recommendations)))
        selected_types = st.multiselect(
            "Recommendation Type",
            options=all_types,
            default=all_types,
            format_func=lambda x: x.capitalize()
        )
    
    with col2:
        # Filter by status
        all_statuses = sorted(list(set(r.status.value for r in recommendations)))
        selected_statuses = st.multiselect(
            "Status",
            options=all_statuses,
            default=all_statuses,
            format_func=lambda x: x.capitalize()
        )
    
    with col3:
        # Filter by impact score
        min_impact = st.slider(
            "Minimum Impact Score",
            min_value=0,
            max_value=100,
            value=0,
            step=10
        )
    
    # Sort options
    sort_by = st.radio(
        "Sort by",
        options=["Impact Score", "Created Date"],
        horizontal=True
    )
    
    # Apply filters
    filtered_recommendations = [
        r for r in recommendations
        if r.type.value in selected_types
        and r.status.value in selected_statuses
        and r.impact_score >= min_impact
    ]
    
    # Sort recommendations
    if sort_by == "Impact Score":
        filtered_recommendations.sort(key=lambda r: r.impact_score, reverse=True)
    else:  # Created Date
        filtered_recommendations.sort(key=lambda r: r.created_at, reverse=True)
    
    # Show results summary
    st.markdown(f"### {len(filtered_recommendations)} Recommendations")
    
    if not filtered_recommendations:
        st.warning("No recommendations match your filter criteria.")
        return
    
    # Display recommendations
    for rec in filtered_recommendations:
        with st.container(border=True):
            # Two-column layout: details and actions
            col1, col2 = st.columns([4, 1])
            
            with col1:
                # Title and description
                st.markdown(f"### {rec.title}")
                st.markdown(rec.description)
                
                # Tags
                st.caption(f"**Type**: {rec.type.value.capitalize()} | **Status**: {rec.status.value.capitalize()}")
                
                # Details expandable section
                with st.expander("View Details"):
                    # Related objects
                    if rec.related_objects:
                        st.markdown("**Related Objects**")
                        st.markdown(", ".join(rec.related_objects))
                    
                    # SQL script
                    if rec.sql_script:
                        st.markdown("**Implementation Script**")
                        st.code(rec.sql_script, language="sql")
                    
                    # Estimated improvement
                    if rec.estimated_improvement:
                        st.markdown("**Estimated Improvement**")
                        st.markdown(rec.estimated_improvement)
            
            with col2:
                # Impact score display
                impact_color = "green" if rec.impact_score >= 70 else "orange" if rec.impact_score >= 40 else "red"
                st.markdown(f"""
                <div style='background-color: {impact_color}; padding: 10px; border-radius: 5px; text-align: center; color: white;'>
                    <h1 style='margin: 0;'>{int(rec.impact_score)}</h1>
                    <p style='margin: 0;'>Impact</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Action buttons
                if rec.status == RecommendationStatus.PENDING:
                    if st.button("Implement", key=f"impl_{rec.recommendation_id}", use_container_width=True):
                        # In a full implementation, this would connect to the database and execute the SQL script
                        # For the MVP, we'll just update the status
                        rec.implement()
                        st.success("Recommendation marked as implemented!")
                        st.experimental_rerun()
                    
                    if st.button("Dismiss", key=f"dismiss_{rec.recommendation_id}", use_container_width=True):
                        rec.dismiss()
                        st.info("Recommendation dismissed.")
                        st.experimental_rerun()
                elif rec.status == RecommendationStatus.IMPLEMENTED:
                    st.success("Implemented")
                    implemented_date = rec.implemented_at.strftime("%Y-%m-%d") if rec.implemented_at else "Unknown"
                    st.caption(f"Date: {implemented_date}")
                elif rec.status == RecommendationStatus.DISMISSED:
                    st.info("Dismissed")
                    if st.button("Restore", key=f"restore_{rec.recommendation_id}", use_container_width=True):
                        rec.status = RecommendationStatus.PENDING
                        rec.updated_at = rec.created_at.__class__.now()
                        st.info("Recommendation restored.")
                        st.experimental_rerun()
    
    # Export options
    st.markdown("### Export Recommendations")
    
    export_format = st.radio(
        "Export Format",
        options=["SQL Script", "Summary Report"],
        horizontal=True
    )
    
    if st.button("Export", type="primary", use_container_width=True):
        if export_format == "SQL Script":
            # Generate script with all SQL statements
            sql_statements = []
            for rec in filtered_recommendations:
                if rec.sql_script and rec.status == RecommendationStatus.PENDING:
                    sql_statements.append(f"-- {rec.title}")
                    sql_statements.append(f"-- Impact Score: {rec.impact_score}")
                    sql_statements.append(rec.sql_script)
                    sql_statements.append("\n")
            
            if sql_statements:
                script = "\n".join(sql_statements)
                st.download_button(
                    label="Download SQL Script",
                    data=script,
                    file_name="postgres_optimization.sql",
                    mime="text/plain"
                )
            else:
                st.warning("No SQL scripts available in the filtered recommendations.")
        else:
            # Generate a summary report
            report_lines = ["# PostgreSQL Optimization Recommendations", "\n"]
            
            for rec in filtered_recommendations:
                report_lines.append(f"## {rec.title}")
                report_lines.append(f"Type: {rec.type.value.capitalize()}")
                report_lines.append(f"Impact Score: {rec.impact_score}")
                report_lines.append(f"Status: {rec.status.value.capitalize()}")
                report_lines.append("\n")
                report_lines.append(rec.description)
                report_lines.append("\n")
                
                if rec.sql_script:
                    report_lines.append("Implementation Script:")
                    report_lines.append("```sql")
                    report_lines.append(rec.sql_script)
                    report_lines.append("```")
                
                report_lines.append("\n---\n")
            
            report = "\n".join(report_lines)
            st.download_button(
                label="Download Report",
                data=report,
                file_name="postgres_recommendations.md",
                mime="text/plain"
            )