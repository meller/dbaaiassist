import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any
from ..components.connection_manager import ConnectionManager

def show_database_insights():
    """Display the database insights page."""
    st.title("PostgreSQL Database Overview")
    
    # Initialize connection manager
    conn_manager = ConnectionManager()
    
    # Show connection status in sidebar
    conn_manager.render_connection_status()
    
    # Exit early if not connected
    connector = conn_manager.get_current_connector()
    if not connector or not connector.is_connected():
        st.warning("Please connect to a PostgreSQL database to view insights.")
        st.info("Go to the Database Connection page to establish a connection.")
        return
    
    # Now display database insights since we're connected
    st.header("Database Overview")
    
    # Get database tables
    with st.spinner("Loading database schema..."):
        tables = connector.get_tables()
        indexes = connector.get_indexes()
        unused_indexes = connector.get_unused_indexes()
    
    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Tables", len(tables))
    with col2:
        st.metric("Indexes", len(indexes))
    with col3:
        st.metric("Unused Indexes", len(unused_indexes))
    
    # Create tabs for different insights
    tab1, tab2 = st.tabs(["Tables", "Indexes"])
    
    with tab1:
        if not tables:
            st.info("No tables found in the database.")
        else:
            st.subheader("Tables")
            
            # Convert to DataFrame for display
            tables_df = pd.DataFrame(tables)
            
            # Display table
            st.dataframe(tables_df, use_container_width=True)
            
            # Generate a chart of top 10 tables by size
            if len(tables) > 0:
                # Function to convert pg_size_pretty strings to numeric values for sorting
                def extract_size_mb(size_str):
                    if not isinstance(size_str, str):
                        return 0
                    
                    try:
                        # Extract numeric part and unit
                        parts = size_str.split()
                        if len(parts) != 2:
                            return 0
                            
                        value = float(parts[0])
                        unit = parts[1].lower()
                        
                        # Convert to MB based on unit
                        if "bytes" in unit:
                            return value / (1024 * 1024)
                        elif "kb" in unit:
                            return value / 1024
                        elif "mb" in unit:
                            return value
                        elif "gb" in unit:
                            return value * 1024
                        elif "tb" in unit:
                            return value * 1024 * 1024
                        return 0
                    except (ValueError, IndexError):
                        return 0
                
                # First convert psycopg2's DictRow objects to regular dictionaries
                table_dicts = []
                for table in tables:
                    # Create a new dictionary from the DictRow
                    table_dict = dict(table)
                    # Add the size_mb field if total_size exists
                    if 'total_size' in table_dict:
                        table_dict['size_mb'] = extract_size_mb(table_dict['total_size'])
                    else:
                        table_dict['size_mb'] = 0
                    table_dicts.append(table_dict)
                
                # Create DataFrame from our regular dictionaries
                tables_df = pd.DataFrame(table_dicts)
                
                # Show a warning if size information is unavailable
                if 'total_size' not in tables_df.columns or tables_df['total_size'].isna().all():
                    st.warning("Table size information is not available.")
                    st.write("Make sure your database user has permissions to access system catalogs.")
                
                # Sort by size and take top 10
                if 'size_mb' in tables_df.columns:
                    top_tables = tables_df.sort_values('size_mb', ascending=False).head(10)
                    
                    # Make sure we have table names column
                    table_name_col = 'table_name'
                    if table_name_col not in top_tables.columns and len(top_tables.columns) > 0:
                        # Try to find a column that looks like a table name
                        for col in top_tables.columns:
                            if isinstance(col, str) and 'table' in col.lower():
                                table_name_col = col
                                break
                        else:
                            # If no suitable column found, use the first column
                            table_name_col = top_tables.columns[0]
                    
                    # Create the bar chart
                    if len(top_tables) > 0:
                        fig = px.bar(
                            top_tables,
                            x=table_name_col,
                            y='size_mb',
                            title="Top 10 Tables by Size (MB)",
                            height=400,
                            labels={table_name_col: "Table Name", 'size_mb': "Size (MB)"}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No tables with size information to display.")
                else:
                    st.error("Cannot create size chart: Unable to calculate table sizes.")
                    st.write("Available columns:", tables_df.columns.tolist())
            
            # Table detail view
            st.subheader("Table Details")
            
            # Select a table to view details
            table_names = [t["table_name"] for t in tables]
            selected_table = st.selectbox("Select a table", table_names)
            
            if selected_table:
                with st.spinner(f"Loading statistics for {selected_table}..."):
                    table_stats = connector.get_table_stats(selected_table)
                
                if not table_stats:
                    st.error(f"Could not retrieve statistics for {selected_table}")
                else:
                    # Display table information
                    st.markdown(f"### {selected_table}")
                    
                    # Basic stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Rows (estimated)", table_stats.get("n_live_tup", "N/A"))
                    with col2:
                        st.metric("Sequential Scans", table_stats.get("seq_scan", "N/A"))
                    with col3:
                        st.metric("Index Scans", table_stats.get("idx_scan", "N/A"))
                    
                    # Columns
                    if "columns" in table_stats:
                        st.subheader("Columns")
                        cols_df = pd.DataFrame(table_stats["columns"])
                        st.dataframe(cols_df, use_container_width=True)
                    
                    # Indexes for this table
                    if "indexes" in table_stats:
                        st.subheader("Indexes")
                        idx_df = pd.DataFrame(table_stats["indexes"])
                        st.dataframe(idx_df, use_container_width=True)
    
    with tab2:
        if not indexes:
            st.info("No indexes found in the database.")
        else:
            st.subheader("All Indexes")
            
            # Convert to DataFrame for display
            indexes_df = pd.DataFrame(indexes)
            
            # Display indexes
            st.dataframe(indexes_df, use_container_width=True)
            
            # Unused indexes
            st.subheader("Unused Indexes")
            
            if not unused_indexes:
                st.success("No unused indexes found. Your database is well optimized!")
            else:
                # Convert to DataFrame for display
                unused_df = pd.DataFrame(unused_indexes)
                
                # Display unused indexes
                st.dataframe(unused_df, use_container_width=True)
                
                # Generate SQL to drop unused indexes
                st.subheader("Clean Up Script")
                st.markdown("⚠️ Review carefully before executing these commands:")
                
                drop_statements = []
                for idx in unused_indexes:
                    drop_statements.append(f"DROP INDEX {idx['index_name']};")
                
                if drop_statements:
                    st.code("\n".join(drop_statements), language="sql")
    
    
    # Add a database structure visualization section (simplified for this implementation)
    st.header("Database Structure")
    
    if tables:
        st.markdown("""
        This simplified view shows table relationships based on common naming patterns.
        For a complete ERD, consider connecting to a dedicated tool.
        """)
        
        # In a real implementation, this would extract foreign keys and build a proper ERD
        # Here we're just creating a simplified visualization
        table_nodes = []
        for t in tables:
            table_nodes.append({
                "id": t["table_name"],
                "label": t["table_name"],
                "size": extract_size_mb(t["total_size"]) + 10
            })
            
        # Create a basic force-directed graph
        if len(table_nodes) > 0:
            st.markdown("**Database Tables Visualization**")
            # In a real implementation, we would use a proper graph visualization library
            st.info("Database structure visualization would be displayed here in a full implementation.")