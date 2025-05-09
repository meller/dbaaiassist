import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any
import io
import time
from ..components.file_uploader import FileUploader
from ..components.connection_manager import ConnectionManager
from ..data.log_parser.postgres_log import PostgreSQLLogParser
from ..services.recommender.index_recommender import IndexRecommender
from ..models.query import Query

def extract_table_names(query_text):
    """
    Extract table names from SQL query to help resolve "tables unknown" issue
    """
    import re
    
    # Convert query to lowercase for easier pattern matching
    query_lower = query_text.lower()
    
    # Common SQL patterns to find table names
    patterns = [
        r'from\s+([a-zA-Z0-9_\.]+)', 
        r'join\s+([a-zA-Z0-9_\.]+)',
        r'into\s+([a-zA-Z0-9_\.]+)',
        r'update\s+([a-zA-Z0-9_\.]+)'
    ]
    
    tables = set()
    for pattern in patterns:
        matches = re.findall(pattern, query_lower)
        for match in matches:
            # Remove any schema prefixes (e.g., "schema." from "schema.table")
            table = match.split('.')[-1].strip()
            tables.add(table)
    
    return list(tables)

def format_query_for_display(query_text):
    """
    Format SQL query for proper display without truncation
    """
    import textwrap
    if not query_text:
        return "No query available"
    
    # Clean up the query: remove extra whitespace and format nicely
    query_text = ' '.join(query_text.split())
    
    # Add line breaks for common SQL keywords to improve readability
    keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 
                'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'OFFSET', 'UNION']
    
    formatted_query = query_text
    for keyword in keywords:
        formatted_query = formatted_query.replace(f" {keyword} ", f"\n{keyword} ")
    
    # Detect tables used in the query
    tables = extract_table_names(query_text)
    
    return formatted_query, tables

def generate_query_recommendations(query_text, detected_tables=None):
    """
    Generate optimization recommendations for a slow query
    """
    # Check if query is empty
    if not query_text:
        return "No query provided for analysis."
    
    # Basic recommendations based on query content
    recommendations = []
    
    # Add table-specific recommendations
    if detected_tables:
        recommendations.append(f"### Table-specific recommendations for: {', '.join(detected_tables)}")
        
        for table in detected_tables:
            if table == 'users':
                recommendations.append(f"- For the `{table}` table:")
                recommendations.append("  - Consider adding an index on the `username` column for faster lookups")
                recommendations.append("  - Ensure the primary key is properly indexed")
            # Add more table-specific recommendations as needed
    else:
        recommendations.append("*Tables could not be detected - recommendations may be limited*")
    
    # General recommendations based on query patterns
    recommendations.append("### General query recommendations:")
    
    # Check for potential join issues
    if " JOIN " in query_text.upper() and "ON" in query_text.upper():
        recommendations.append("- Consider adding indexes on join columns")
    
    # Check for potential WHERE clause optimizations
    if " WHERE " in query_text.upper():
        recommendations.append("- Add indexes on columns used in WHERE clauses")
        # Look for specific patterns in WHERE clause
        if "=" in query_text and "username" in query_text.lower():
            recommendations.append("- The query is filtering on username - ensure this column is indexed")
    
    # Check for LIMIT clause
    if " LIMIT " in query_text.upper():
        recommendations.append("- The query uses LIMIT - ensure proper ordering for consistent results")
    
    # Add explanation about any remaining "tables unknown" issues
    if not detected_tables:
        recommendations.append("\n### Note on 'Tables Unknown':")
        recommendations.append("The system couldn't detect the tables in your query. This might be because:")
        recommendations.append("1. The query syntax is complex or non-standard")
        recommendations.append("2. The system doesn't have access to the database schema")
        recommendations.append("3. The query might be using dynamic SQL or prepared statements")
    
    if not recommendations:
        recommendations.append("- No specific optimizations identified. Consider analyzing the execution plan for deeper insights.")
    
    return "\n".join(recommendations)

def show_log_analysis():
    """Display the log analysis page."""
    st.title("PostgreSQL Log Analysis")
    
    # Initialize connection manager for the sidebar
    conn_manager = ConnectionManager()
    conn_manager.render_connection_status()
    
    # Initialize file uploader component
    file_uploader = FileUploader(key="log_analysis")
    
    # Upload log files section
    st.markdown("### 1. Upload PostgreSQL Log Files")
    st.markdown("""
    Upload your PostgreSQL log files to analyze query performance.
    Configure PostgreSQL logging with `log_min_duration_statement` to capture slow queries.
    """)
    
    # File uploader component
    uploaded_files = file_uploader.upload_log_files(
        title="",
        help_text="Upload one or more PostgreSQL log files (.log, .txt, or .gz)"
    )
    
    if not uploaded_files:
        st.info("Please upload PostgreSQL log files to begin analysis.")
        
        # Show sample log format for reference
        with st.expander("Sample PostgreSQL Log Format"):
            st.code("""
2023-05-09 14:25:32.123 UTC [12345] postgres@mydb LOG:  duration: 1532.312 ms  statement: SELECT * FROM large_table WHERE created_at > '2023-01-01' AND status = 'active';
2023-05-09 14:26:15.456 UTC [12345] postgres@mydb LOG:  duration: 3245.678 ms  statement: SELECT t1.*, t2.name FROM table1 t1 JOIN table2 t2 ON t1.id = t2.id WHERE t1.value > 1000;
2023-05-09 14:27:01.789 UTC [12346] postgres@mydb LOG:  duration: 892.123 ms  statement: UPDATE users SET last_login = NOW() WHERE user_id = 12345;
            """, language="text")
        return
    
    # Optional: Show log sample
    if uploaded_files:
        file_uploader.show_sample_logs(uploaded_files, num_lines=5)
    
    # Log parsing configuration
    st.markdown("### 2. Parse Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        slow_query_threshold = st.slider(
            "Slow Query Threshold (ms)", 
            min_value=0, 
            max_value=5000, 
            value=100,
            step=50,
            help="Queries taking longer than this threshold will be considered slow"
        )
    
    with col2:
        sample_size = st.number_input(
            "Sample Size (lines)",
            min_value=0,
            max_value=1000000,
            value=0,
            step=1000,
            help="Number of log lines to sample (0 for all lines)"
        )
    
    # Parse and analyze button
    if st.button("Parse and Analyze Logs", type="primary", use_container_width=True):
        if not uploaded_files:
            st.error("Please upload log files first.")
            return
            
        # Create log parser
        log_parser = PostgreSQLLogParser()
        
        # Use spinner to show progress
        with st.spinner("Parsing log files..."):
            # Process each uploaded file
            all_queries = []
            for file in uploaded_files:
                # Reset file pointer
                file.seek(0)
                
                # Parse with optional sampling
                sample = sample_size if sample_size > 0 else None
                queries = log_parser.parse_file(file, sample_size=sample)
                all_queries.extend(queries)
            
            # Store in session state
            st.session_state["analyzed_queries"] = all_queries
            
            # Get statistics
            log_stats = log_parser.get_stats()
            slow_queries = log_parser.get_slow_queries(threshold_ms=slow_query_threshold)
            query_patterns = log_parser.get_query_patterns()
            
            # Store in session state for this page
            st.session_state["log_stats"] = log_stats
            st.session_state["slow_queries"] = slow_queries
            st.session_state["query_patterns"] = query_patterns
        
        st.success(f"✅ Successfully parsed {log_stats['parsed_queries']} queries from {len(uploaded_files)} log files.")
        
        # Generate recommendations if we have a database connection
        connector = conn_manager.get_current_connector()
        if connector and connector.is_connected():
            with st.spinner("Generating optimization recommendations..."):
                # Initialize recommender
                index_recommender = IndexRecommender()
                
                # Analyze queries and generate recommendations
                recommendations = index_recommender.analyze_queries(all_queries)
                
                # Store recommendations in session state
                st.session_state["recommendations"] = recommendations
                
                st.success(f"✅ Generated {len(recommendations)} optimization recommendations.")
    
    # Only show results if we have analyzed queries
    if "analyzed_queries" not in st.session_state:
        return
    
    # Results section
    st.markdown("### 3. Analysis Results")
    
    queries = st.session_state["analyzed_queries"]
    log_stats = st.session_state.get("log_stats", {})
    slow_queries = st.session_state.get("slow_queries", [])
    query_patterns = st.session_state.get("query_patterns", [])
    
    # Summary statistics
    st.subheader("Summary Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Queries", len(queries))
    
    with col2:
        st.metric("Slow Queries", len(slow_queries))
    
    with col3:
        if queries:
            avg_time = sum(q.execution_time_ms for q in queries) / len(queries)
            st.metric("Avg Execution Time", f"{avg_time:.2f} ms")
        else:
            st.metric("Avg Execution Time", "N/A")
    
    with col4:
        if queries:
            max_time = max(q.execution_time_ms for q in queries)
            st.metric("Max Execution Time", f"{max_time:.2f} ms")
        else:
            st.metric("Max Execution Time", "N/A")
    
    # Tabs for different analysis views
    tab1, tab2, tab3 = st.tabs(["Slow Queries", "Query Patterns", "Tables Accessed"])
    
    with tab1:
        if not slow_queries:
            st.info(f"No queries exceeded the threshold of {slow_query_threshold} ms.")
        else:
            st.markdown(f"Found **{len(slow_queries)}** queries exceeding the threshold of **{slow_query_threshold} ms**.")
            
            # Prepare dataframe for display
            slow_query_data = []
            for q in slow_queries:
                formatted_sql, detected_tables = format_query_for_display(q.query_text)
                
                slow_query_data.append({
                    "Execution Time (ms)": q.execution_time_ms,
                    "Query": formatted_sql,
                    "Tables": ", ".join(detected_tables) if detected_tables else "Unknown",
                    "Timestamp": q.timestamp
                })
            
            # Sort by execution time
            slow_query_df = pd.DataFrame(slow_query_data)
            slow_query_df = slow_query_df.sort_values("Execution Time (ms)", ascending=False)
            
            # Display table
            st.dataframe(slow_query_df, use_container_width=True)
            
            # Visualization
            fig = px.bar(
                slow_query_df.head(10), 
                x="Query", 
                y="Execution Time (ms)",
                title="Top 10 Slowest Queries",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Add a button to generate recommendations
            if st.button("Generate Recommendation"):
                if 'slow_queries' in st.session_state and st.session_state.slow_queries:
                    # Get the selected slow query
                    selected_query = st.session_state.slow_queries[0]  # Assuming first query is the slowest
                    st.session_state.selected_slow_query = selected_query.query_text  # Store the query text
                    st.session_state.generate_recommendation = True
                    st.rerun()  # Updated from st.experimental_rerun()
                else:
                    st.warning("No slow queries available for analysis.")
    
    with tab2:
        if not query_patterns:
            st.info("No query patterns were identified.")
        else:
            st.markdown(f"Identified **{len(query_patterns)}** distinct query patterns.")
            
            # Prepare data for patterns display
            pattern_data = []
            for pattern, pattern_queries in query_patterns:
                if len(pattern) > 100:
                    pattern_short = pattern[:97] + "..."
                else:
                    pattern_short = pattern
                
                avg_time = sum(q.execution_time_ms for q in pattern_queries) / len(pattern_queries)
                max_time = max(q.execution_time_ms for q in pattern_queries)
                
                pattern_data.append({
                    "Pattern": pattern_short,
                    "Count": len(pattern_queries),
                    "Avg Time (ms)": avg_time,
                    "Max Time (ms)": max_time
                })
            
            # Display patterns
            pattern_df = pd.DataFrame(pattern_data)
            st.dataframe(pattern_df, use_container_width=True)
            
            # Visualization
            fig = px.scatter(
                pattern_df.head(15), 
                x="Count", 
                y="Avg Time (ms)",
                size="Max Time (ms)",
                hover_name="Pattern",
                log_x=True,
                title="Query Patterns by Frequency and Execution Time",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        # Extract tables accessed by all queries
        table_stats = {}
        for query in queries:
            if not query.tables_accessed:
                continue
                
            for table in query.tables_accessed:
                if table not in table_stats:
                    table_stats[table] = {
                        "count": 0,
                        "total_time": 0,
                        "avg_time": 0,
                        "max_time": 0
                    }
                
                table_stats[table]["count"] += 1
                table_stats[table]["total_time"] += query.execution_time_ms
                table_stats[table]["max_time"] = max(
                    table_stats[table]["max_time"], 
                    query.execution_time_ms
                )
        
        # Calculate averages
        for table in table_stats:
            table_stats[table]["avg_time"] = (
                table_stats[table]["total_time"] / table_stats[table]["count"]
            )
        
        if not table_stats:
            st.info("No tables were identified in the queries.")
        else:
            st.markdown(f"Identified **{len(table_stats)}** tables accessed in the analyzed queries.")
            
            # Prepare dataframe
            table_data = [
                {
                    "Table": table,
                    "Query Count": stats["count"],
                    "Avg Time (ms)": stats["avg_time"],
                    "Max Time (ms)": stats["max_time"],
                    "Total Time (ms)": stats["total_time"]
                }
                for table, stats in table_stats.items()
            ]
            
            # Sort by total time
            table_df = pd.DataFrame(table_data)
            table_df = table_df.sort_values("Total Time (ms)", ascending=False)
            
            # Display table data
            st.dataframe(table_df, use_container_width=True)
            
            # Visualization
            fig = px.bar(
                table_df.head(10), 
                x="Table", 
                y=["Avg Time (ms)", "Max Time (ms)"],
                title="Top 10 Tables by Query Time",
                height=400,
                barmode="group"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Add explanation for "tables unknown" message
    with st.expander("What does 'tables unknown' mean?"):
        st.markdown("""
        The 'tables unknown' message indicates that the system doesn't have access to the database schema information for the tables in your query. This happens when:
        
        1. The query analysis is performed without connecting to the database
        2. The tables mentioned in the query don't exist in the connected database
        3. The system doesn't have permission to access the table definitions
        
        To get more detailed recommendations, ensure that your database connection is properly configured and that the system has access to the table schemas.
        """)
    
    # Generate recommendations section
    st.markdown("### 4. Generate Recommendations")
    
    if "recommendations" in st.session_state and st.session_state["recommendations"]:
        rec_count = len(st.session_state["recommendations"])
        st.success(f"✅ {rec_count} recommendations generated. Go to the Recommendations page to view them.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Generate Recommendations", use_container_width=True):
            if not queries:
                st.error("No queries to analyze. Please upload and parse log files first.")
                return
                
            # Check if we have a database connection
            connector = conn_manager.get_current_connector()
            if not connector or not connector.is_connected():
                st.error("Database connection required for recommendations. Please connect to a database first.")
                return
            
            with st.spinner("Generating optimization recommendations..."):
                # Initialize recommender
                index_recommender = IndexRecommender()
                
                # Analyze queries and generate recommendations
                recommendations = index_recommender.analyze_queries(queries)
                
                # Store in session state
                st.session_state["recommendations"] = recommendations
                
                st.success(f"✅ Generated {len(recommendations)} optimization recommendations.")
    
    with col2:
        if st.button("View Recommendations", use_container_width=True):
            if "recommendations" not in st.session_state or not st.session_state["recommendations"]:
                st.error("No recommendations available. Please generate recommendations first.")
            else:
                st.switch_page("pages/3_Recommendations.py")
    
    # Add a section for query recommendations
    if 'generate_recommendation' in st.session_state and st.session_state.generate_recommendation:
        with st.spinner("Generating recommendations..."):
            # Get the selected slow query
            if 'selected_slow_query' in st.session_state and st.session_state.selected_slow_query:
                query_text = st.session_state.selected_slow_query
                
                # Format the query and display it fully
                formatted_query, detected_tables = format_query_for_display(query_text)
                
                st.subheader("Full Query")
                st.code(formatted_query, language="sql")
                
                # Show detected tables
                if detected_tables:
                    st.write("**Detected tables:**", ", ".join(detected_tables))
                
                # Generate recommendations using the detected tables
                recommendations = generate_query_recommendations(query_text, detected_tables)
                st.subheader("Query Optimization Recommendations")
                st.markdown(recommendations)
                
                # Reset the flag after displaying recommendations
                st.session_state.generate_recommendation = False
            else:
                st.warning("Please select a query first.")