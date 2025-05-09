import streamlit as st
import pandas as pd
import json
from typing import List, Dict, Any
from ..components.connection_manager import ConnectionManager

def show_query_explain():
    """Display the page for query execution plan analysis."""
    st.title("PostgreSQL Query Execution Plan")
    
    # Initialize connection manager for the sidebar
    conn_manager = ConnectionManager()
    conn_manager.render_connection_status()
    
    # Check if we're connected
    connector = conn_manager.get_current_connector()
    if not connector or not connector.is_connected():
        st.warning("Please connect to a database first.")
        return
    
    # Query Editor
    st.subheader("Query Execution Plan")
    st.markdown("""
    Enter a SQL query to analyze its execution plan. This helps identify performance issues
    and validate optimization recommendations.
    """)
    
    # Query input
    query = st.text_area(
        "SQL Query", 
        height=150,
        placeholder="SELECT * FROM table WHERE condition;"
    )
    
    explain_options = st.multiselect(
        "EXPLAIN options",
        ["ANALYZE", "BUFFERS", "COSTS", "TIMING"],
        default=["ANALYZE", "BUFFERS"]
    )
    
    # Execute button
    if st.button("Analyze Query Plan", type="primary", use_container_width=True):
        if not query:
            st.error("Please enter a SQL query to analyze.")
        else:
            # Create EXPLAIN query
            explain_opts = ", ".join(explain_options)
            explain_query = f"EXPLAIN (FORMAT JSON, {explain_opts}) {query}"
            
            # Execute query
            with st.spinner("Analyzing query execution plan..."):
                success, result = connector.execute_query(explain_query)
            
            # Display results
            if success:
                # Parse the explain output (JSON format)
                try:
                    plan_json = result[0][0]
                    
                    # Display as expandable JSON
                    with st.expander("Raw Execution Plan", expanded=False):
                        st.json(plan_json)
                    
                    # Extract key information from the plan
                    plan_node = plan_json[0]["Plan"]
                    
                    # Display plan summary
                    st.subheader("Plan Summary")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Plan Type", plan_node.get("Node Type", "Unknown"))
                        st.metric("Estimated Cost", plan_node.get("Total Cost", "Unknown"))
                    with col2:
                        st.metric("Actual Time (ms)", plan_node.get("Actual Total Time", "Unknown"))
                        st.metric("Rows Returned", plan_node.get("Actual Rows", "Unknown"))
                    
                    # Check for sequential scans which might need indexes
                    sequential_scans = []
                    def find_sequential_scans(node):
                        if node.get("Node Type") == "Seq Scan":
                            sequential_scans.append({
                                "Table": node.get("Relation Name", "Unknown"),
                                "Cost": node.get("Total Cost", 0),
                                "Rows": node.get("Actual Rows", 0),
                                "Filter": node.get("Filter", None)
                            })
                        
                        # Recursively check child nodes
                        for child_key in ["Plans", "Plan"]:
                            if child_key in node:
                                children = node[child_key]
                                if isinstance(children, list):
                                    for child in children:
                                        find_sequential_scans(child)
                                else:
                                    find_sequential_scans(children)
                    
                    # Find sequential scans
                    find_sequential_scans(plan_node)
                    
                    # Alert if sequential scans found
                    if sequential_scans:
                        st.warning(f"Found {len(sequential_scans)} sequential scan(s) that might benefit from indexes:")
                        
                        for scan in sequential_scans:
                            with st.container(border=True):
                                st.markdown(f"**Table**: {scan['Table']}")
                                
                                if scan['Filter']:
                                    st.markdown(f"**Filter**: `{scan['Filter']}`")
                                    
                                    # Extract potential index columns
                                    columns = []
                                    for op in ["=", "<", ">", "<=", ">="]:
                                        if op in scan['Filter']:
                                            parts = scan['Filter'].split(op)
                                            if len(parts) > 1:
                                                col = parts[0].strip()
                                                if col and col not in columns:
                                                    columns.append(col)
                                    
                                    if columns:
                                        index_cols = ", ".join(columns)
                                        st.markdown(f"**Suggested Index**: `CREATE INDEX idx_{scan['Table']}_{columns[0]} ON {scan['Table']} ({index_cols});`")
                    else:
                        st.success("No sequential scans found. Query is well optimized!")
                        
                except Exception as e:
                    st.error(f"Error parsing execution plan: {str(e)}")
            else:
                st.error(f"Error executing query: {result}")
                
                # Check if it's a permissions error and suggest read-only connection
                if "permission denied" in str(result).lower():
                    st.warning("This might be a permissions issue. Make sure your database user has appropriate permissions.")
                    
    # Add an explanation section about execution plans
    with st.expander("Understanding Execution Plans", expanded=False):
        st.markdown("""
        ### How to Read PostgreSQL Execution Plans
        
        PostgreSQL's execution plans show how the database will execute your query. Here's what to look for:
        
        #### Common Node Types
        - **Seq Scan**: Full table scan - reads every row in the table (often inefficient for large tables)
        - **Index Scan**: Uses an index to find specific rows (usually more efficient than Seq Scan)
        - **Bitmap Index Scan**: Two-step process that first creates a bitmap of matching rows
        - **Nested Loop**: Joins tables by looping through rows (good for small result sets)
        - **Hash Join**: Builds a hash table in memory for joining (good for larger joins)
        - **Merge Join**: Joins pre-sorted inputs (efficient for large sorted datasets)
        
        #### Key Metrics
        - **Cost**: Estimated processing cost (higher numbers = more expensive)
        - **Rows**: Estimated number of rows to be processed
        - **Width**: Estimated average width of rows in bytes
        - **Actual Time**: Real execution time (only with ANALYZE option)
        - **Actual Rows**: Real number of rows processed (only with ANALYZE option)
        
        #### Performance Tips
        - Look for **Seq Scan** on large tables - these usually benefit from indexes
        - Check if **estimated rows** are very different from **actual rows** - indicates statistics issues
        - Watch for **high-cost sorting operations** - might need indexes for ORDER BY
        - Examine **join strategies** - nested loops can be inefficient for large datasets
        """)
    
    # Add a section for common improvement patterns
    with st.expander("Common Query Improvements", expanded=False):
        st.markdown("""
        ### Common Ways to Improve Query Performance
        
        1. **Add indexes for WHERE clauses**:
           ```sql
           CREATE INDEX idx_table_column ON table(column);
           ```
           
        2. **Add indexes for JOIN conditions**:
           ```sql
           CREATE INDEX idx_table_join_col ON table(join_column);
           ```
           
        3. **Add composite indexes for multiple conditions**:
           ```sql
           CREATE INDEX idx_table_composite ON table(column1, column2);
           ```
           
        4. **Use EXPLAIN ANALYZE to verify improvements**:
           ```sql
           EXPLAIN ANALYZE SELECT * FROM table WHERE condition;
           ```
           
        5. **Consider partial indexes for specific conditions**:
           ```sql
           CREATE INDEX idx_partial ON table(column) WHERE condition;
           ```
           
        6. **Review table statistics**:
           ```sql
           ANALYZE table;
           ```
        """)
