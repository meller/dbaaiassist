import streamlit as st
import pandas as pd
import plotly.express as px
import time
from typing import List, Dict, Any
from ..components.connection_manager import ConnectionManager

def show_query_execution():
    """Display the query execution page with EXPLAIN analysis."""
    st.title("PostgreSQL Query Execution & Analysis")
    
    # Initialize connection manager for the sidebar
    conn_manager = ConnectionManager()
    conn_manager.render_connection_status()
    
    # Check if we're connected
    connector = conn_manager.get_current_connector()
    if not connector or not connector.is_connected():
        st.warning("Please connect to a database first.")
        return
    
    # Query Editor
    st.markdown("### SQL Query Editor")
    
    # Query text area
    query = st.text_area(
        "Enter your SQL query",
        height=200,
        placeholder="SELECT * FROM pg_tables LIMIT 10;",
        key="query_editor",
        help="Enter a valid PostgreSQL query to execute"
    )
    
    # Query options
    col1, col2, col3 = st.columns(3)
    with col1:
        max_rows = st.number_input(
            "Max rows to return",
            min_value=1,
            max_value=10000,
            value=1000,
            step=100,
            help="Limit the number of rows returned to prevent memory issues"
        )
    
    with col2:
        timeout = st.number_input(
            "Query timeout (seconds)",
            min_value=1,
            max_value=300,
            value=30,
            step=5,
            help="Cancel query if it takes longer than this"
        )
        
    with col3:
        explain_type = st.selectbox(
            "EXPLAIN Type",
            options=["None", "EXPLAIN", "EXPLAIN ANALYZE", "EXPLAIN ANALYZE VERBOSE"],
            help="Choose the type of query execution plan to generate"
        )
    
    # Action buttons
    col1, col2 = st.columns(2)
    
    with col1:
        execute_button = st.button("Execute Query", type="primary", use_container_width=True)
    
    with col2:
        analyze_button = st.button("Analyze Query Performance", use_container_width=True)
    
    # Execute button logic
    if execute_button:
        if not query:
            st.error("Please enter a query to execute.")
        else:
            # Save to query history
            if "query_history" not in st.session_state:
                st.session_state["query_history"] = []
            
            # Add to history if not already present
            if query not in st.session_state["query_history"]:
                st.session_state["query_history"].append(query)
                
                # Limit history to last 10 queries
                if len(st.session_state["query_history"]) > 10:
                    st.session_state["query_history"] = st.session_state["query_history"][-10:]
            
            # Execute query
            with st.spinner("Executing query..."):
                start_time = time.time()
                
                try:
                    # Add EXPLAIN if requested
                    if explain_type != "None":
                        explain_query = f"{explain_type} {query}"
                        results = connector.execute_query(explain_query, max_rows=max_rows, timeout=timeout)
                        
                        # Display execution plan
                        st.subheader("Query Execution Plan")
                        
                        # Format the plan for better readability
                        if isinstance(results, pd.DataFrame):
                            plan_text = "\n".join([str(row[0]) for _, row in results.iterrows()])
                            st.code(plan_text, language="text")
                            
                            # Add explanation of the plan
                            with st.expander("Understand the Execution Plan"):
                                st.markdown("""
                                ### Reading PostgreSQL Execution Plans
                                
                                - **Seq Scan**: Full table scan, reading all rows
                                - **Index Scan**: Using an index to find specific rows
                                - **Bitmap Scan**: Two-pass approach using an index then fetching rows
                                - **Nested Loop**: Joining tables by looping through rows
                                - **Hash Join**: Building a hash table for one relation, then probing with the other
                                - **Merge Join**: Merging two pre-sorted inputs
                                
                                **Cost**: The first number is startup cost, the second is total cost
                                
                                **Rows**: Estimated number of rows the operation will return
                                
                                **Width**: Estimated average width of rows in bytes
                                """)
                        else:
                            st.text(str(results))
                        
                        # Now execute the actual query if it's not a DDL statement
                        if not any(keyword in query.upper() for keyword in ["CREATE", "ALTER", "DROP", "TRUNCATE"]):
                            results = connector.execute_query(query, max_rows=max_rows, timeout=timeout)
                        else:
                            # For DDL, we're done after showing the explain
                            st.info("DDL statement analyzed but not executed to prevent unintended changes.")
                            end_time = time.time()
                            st.success(f"Query analyzed in {end_time - start_time:.2f} seconds.")
                            return
                    else:
                        # Regular execution without explain
                        results = connector.execute_query(query, max_rows=max_rows, timeout=timeout)
                    
                    end_time = time.time()
                    execution_time = end_time - start_time
                    
                    # Display results
                    st.subheader("Query Results")
                    st.success(f"Query executed successfully in {execution_time:.2f} seconds.")
                    
                    if isinstance(results, pd.DataFrame):
                        # Show dataframe info
                        st.text(f"Showing {len(results)} rows, {len(results.columns)} columns")
                        
                        # Show dataframe
                        st.dataframe(results, use_container_width=True)
                        
                        # Export options
                        if not results.empty:
                            st.download_button(
                                label="Export Results (CSV)",
                                data=results.to_csv(index=False).encode('utf-8'),
                                file_name="query_results.csv",
                                mime="text/csv"
                            )
                    else:
                        st.text(str(results))
                
                except Exception as e:
                    st.error(f"Error executing query: {str(e)}")
    
    # Analyze query performance button logic
    if analyze_button:
        if not query:
            st.error("Please enter a query to analyze.")
        else:
            with st.spinner("Analyzing query performance..."):
                try:
                    # Run an EXPLAIN ANALYZE to get performance data
                    explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
                    results = connector.execute_query(explain_query, max_rows=max_rows, timeout=timeout)
                    
                    if isinstance(results, pd.DataFrame) and not results.empty:
                        # Extract the JSON plan
                        plan_json = results.iloc[0, 0]
                        
                        if isinstance(plan_json, str):
                            import json
                            plan_json = json.loads(plan_json)
                        
                        # Display plan visualization
                        st.subheader("Query Execution Plan Analysis")
                        
                        # Extract plan details
                        plan_node = plan_json[0]['Plan']
                        execution_time = plan_json[0]['Execution Time']
                        planning_time = plan_json[0]['Planning Time']
                        
                        # Summary metrics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Execution Time", f"{execution_time:.2f} ms")
                        with col2:
                            st.metric("Planning Time", f"{planning_time:.2f} ms")
                        with col3:
                            st.metric("Total Time", f"{execution_time + planning_time:.2f} ms")
                        
                        # Top operations by time
                        operations = []
                        
                        def extract_operations(node, parent=None):
                            if 'Actual Total Time' in node:
                                operations.append({
                                    'Node Type': node['Node Type'],
                                    'Relation': node.get('Relation Name', '-'),
                                    'Total Time': node['Actual Total Time'],
                                    'Rows': node['Actual Rows'],
                                    'Loops': node['Actual Loops'],
                                    'Parent': parent
                                })
                            
                            # Process child nodes
                            for child_key in ['Plans', 'Subplans']:
                                if child_key in node:
                                    for child in node[child_key]:
                                        extract_operations(child, node['Node Type'])
                        
                        extract_operations(plan_node)
                        
                        if operations:
                            operations_df = pd.DataFrame(operations)
                            operations_df = operations_df.sort_values('Total Time', ascending=False)
                            
                            st.subheader("Operations by Execution Time")
                            st.dataframe(operations_df)
                            
                            # Visualization
                            fig = px.bar(
                                operations_df.head(10), 
                                x='Node Type', 
                                y='Total Time',
                                hover_data=['Relation', 'Rows', 'Loops'],
                                title="Top 10 Operations by Execution Time",
                                height=400
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # Show the full plan in collapsible section
                        with st.expander("View Complete Execution Plan (JSON)"):
                            st.json(plan_json)
                        
                        # Recommendations based on the plan
                        st.subheader("Performance Recommendations")
                        
                        recommendations = []
                        
                        # Check for sequential scans on large tables
                        seq_scans = [op for op in operations if op['Node Type'] == 'Seq Scan' and op['Rows'] > 1000]
                        if seq_scans:
                            for scan in seq_scans:
                                if scan['Relation'] != '-':
                                    recommendations.append(f"- Consider adding an index on table `{scan['Relation']}` to avoid sequential scan")
                        
                        # Check for expensive sorts
                        expensive_sorts = [op for op in operations if op['Node Type'] == 'Sort' and op['Total Time'] > 100]
                        if expensive_sorts:
                            recommendations.append("- Consider adding indexes to avoid expensive sort operations")
                        
                        # Check for nested loops with many rows
                        nested_loops = [op for op in operations if op['Node Type'] == 'Nested Loop' and op['Rows'] > 1000]
                        if nested_loops:
                            recommendations.append("- Large nested loops detected. Consider optimizing join conditions or adding indexes on join columns")
                        
                        if recommendations:
                            for rec in recommendations:
                                st.markdown(rec)
                        else:
                            st.info("No specific recommendations for this query. The execution plan looks efficient.")
                    
                    else:
                        st.warning("Could not obtain a valid execution plan for analysis.")
                
                except Exception as e:
                    st.error(f"Error analyzing query: {str(e)}")
    
    # Show query history
    with st.expander("Query History"):
        query_history = st.session_state.get("query_history", [])
        
        if not query_history:
            st.info("No queries executed yet.")
        else:
            for i, hist_query in enumerate(reversed(query_history)):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.text_area(
                        f"Query {len(query_history) - i}",
                        value=hist_query,
                        height=100,
                        key=f"history_{i}",
                        disabled=True
                    )
                
                with col2:
                    if st.button("Load", key=f"load_{i}"):
                        st.session_state["query_editor"] = hist_query
                        st.experimental_rerun()
