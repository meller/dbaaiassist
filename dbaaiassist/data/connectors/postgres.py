import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor
from typing import List, Dict, Any, Optional, Tuple, Union
import pandas as pd
import traceback
from ...models.database import DatabaseConnection
from ...utils.logger import app_logger, log_exception

class PostgreSQLConnector:
    """Connector for PostgreSQL databases."""
    
    def __init__(self, connection_info: DatabaseConnection):
        """
        Initialize the connector with connection information.
        
        Args:
            connection_info: DatabaseConnection object with connection details
        """
        self.connection_info = connection_info
        app_logger.info(f"Initializing PostgreSQLConnector for {connection_info.name}")
        app_logger.debug(f"Connection details: {connection_info.host}:{connection_info.port}/{connection_info.database}")
        self.conn = None
        self.cursor = None
    
    @log_exception
    def connect(self) -> bool:
        """
        Establish a connection to the PostgreSQL database.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            app_logger.info(f"Connecting to PostgreSQL database: {self.connection_info.host}:{self.connection_info.port}/{self.connection_info.database}")
            conn_params = {
                'host': self.connection_info.host,
                'port': self.connection_info.port,
                'database': self.connection_info.database,
                'user': self.connection_info.username,
                'password': self.connection_info.password
            }
            
            # Add SSL if enabled
            if self.connection_info.use_ssl:
                app_logger.debug("Using SSL for connection")
                conn_params['sslmode'] = 'require'
            
            app_logger.debug(f"Connection parameters: {conn_params}")
            self.conn = psycopg2.connect(**conn_params)
            app_logger.debug("Connection established, creating cursor")
            self.cursor = self.conn.cursor(cursor_factory=DictCursor)
            app_logger.info("Successfully connected to PostgreSQL database")
            return True
        except Exception as e:
            app_logger.exception(f"PostgreSQL connection error: {str(e)}")
            app_logger.error(traceback.format_exc())
            return False
    
    @log_exception
    def disconnect(self) -> None:
        """Close the database connection."""
        app_logger.info("Disconnecting from PostgreSQL database")
        if self.cursor:
            app_logger.debug("Closing cursor")
            self.cursor.close()
        if self.conn:
            app_logger.debug("Closing connection")
            self.conn.close()
        self.cursor = None
        self.conn = None
        app_logger.info("PostgreSQL disconnect complete")
    
    @log_exception
    def is_connected(self) -> bool:
        """Check if database is connected."""
        if self.conn is None:
            app_logger.debug("Connection check: No connection object exists")
            return False
        try:
            # Try a simple query to check connection
            app_logger.debug("Testing connection with SELECT 1 query")
            cur = self.conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            app_logger.debug("Connection is active")
            return True
        except Exception as e:
            app_logger.warning(f"Connection check failed: {str(e)}")
            # If there's a transaction error, try to rollback
            if "current transaction is aborted" in str(e):
                try:
                    app_logger.debug("Attempting to rollback aborted transaction")
                    self.conn.rollback()
                    app_logger.debug("Transaction rollback successful")
                    return True
                except Exception as rollback_error:
                    app_logger.error(f"Failed to rollback transaction: {str(rollback_error)}")
            return False
    
    @log_exception
    def execute_query(self, query: str, params: Optional[Union[Dict[str, Any], List, Tuple]] = None) -> Tuple[bool, Any]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query to execute
            params: Optional parameters for the query. Can be a dictionary for named parameters,
                    or a list/tuple for positional parameters.
                
        Returns:
            Tuple containing success status and result/error message
        """
        app_logger.debug(f"Executing query: {query[:200]}...")
        if params:
            app_logger.debug(f"With parameters: {params}")
            
        if not self.is_connected():
            app_logger.warning("Query execution failed: Not connected to database")
            return (False, "Not connected to database")
        
        try:
            # Check if the query contains SQLAlchemy-style parameters (%(......)s)
            import re
            sqlalchemy_param_pattern = r'%\(([^\)]+)\)s'
            sqlalchemy_params = re.findall(sqlalchemy_param_pattern, query)
            
            # If SQLAlchemy parameters are found but no params dictionary was provided
            if sqlalchemy_params and params is None:
                app_logger.warning("Query contains SQLAlchemy parameters but no params were provided")
                app_logger.debug(f"Extracted parameter names: {sqlalchemy_params}")
                
                # Create an empty params dictionary with NULL values for all parameters
                generated_params = {param_name: None for param_name in sqlalchemy_params}
                app_logger.debug(f"Created parameter dictionary with NULL values: {generated_params}")
                
                # Use the generated parameters
                params = generated_params
            
            # Execute the query with or without parameters
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            
            # Check if the query returns results
            if self.cursor.description:
                app_logger.debug("Query returned results, fetching...")
                results = self.cursor.fetchall()
                app_logger.debug(f"Query executed successfully, returned {len(results)} rows")
                return (True, results)
            
            app_logger.debug("Query executed successfully, no results to return")
            return (True, "Query executed successfully")
        except Exception as e:
            app_logger.exception(f"Query execution error: {str(e)}")
            # Rollback transaction on error to avoid aborted transaction state
            try:
                app_logger.debug("Attempting to rollback after query error")
                self.conn.rollback()
                app_logger.debug("Transaction rollback successful")
            except Exception as rollback_error:
                app_logger.error(f"Failed to rollback transaction: {str(rollback_error)}")
            return (False, str(e))
    
    @log_exception
    def get_query_plan(self, query: str, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any]:
        """
        Get the execution plan for a SQL query.
        
        Args:
            query: SQL query to analyze
            params: Optional parameters for the query
            
        Returns:
            Tuple containing success status and execution plan/error message
        """
        app_logger.info(f"Getting query plan for: {query[:200]}...")
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        return self.execute_query(explain_query, params)
    
    @log_exception
    def get_tables(self) -> List[Dict[str, Any]]:
        """
        Get list of tables in the database.
        
        Returns:
            List of dictionaries with table information
        """
        app_logger.info("Fetching database tables list")
        query = """
        SELECT 
            n.nspname as schema,
            c.relname as table_name,
            c.reltuples::bigint as row_estimate,
            pg_size_pretty(pg_total_relation_size(c.oid)) as total_size,
            pg_size_pretty(pg_relation_size(c.oid)) as table_size,
            pg_size_pretty(pg_total_relation_size(c.oid) - pg_relation_size(c.oid)) as index_size
        FROM pg_class c
        LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY pg_total_relation_size(c.oid) DESC;
        """
        success, result = self.execute_query(query)
        if success:
            app_logger.info(f"Retrieved {len(result)} tables")
            return result
        app_logger.warning("Failed to retrieve tables list")
        return []
    
    @log_exception
    def get_indexes(self) -> List[Dict[str, Any]]:
        """
        Get list of indexes in the database.
        
        Returns:
            List of dictionaries with index information
        """
        app_logger.info("Fetching database indexes list")
        query = """
        SELECT
            t.tablename as table_name,
            i.indexname as index_name,
            i.indexdef as index_definition,
            idx_scan as scans,
            pg_size_pretty(pg_relation_size(ui.indexrelid)) as index_size
        FROM pg_stat_user_indexes ui
        JOIN pg_indexes i ON ui.indexrelname = i.indexname AND ui.schemaname = i.schemaname
        JOIN pg_tables t ON i.tablename = t.tablename AND i.schemaname = t.schemaname
        WHERE t.schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY pg_relation_size(ui.indexrelid) DESC;
        """
        success, result = self.execute_query(query)
        if success:
            app_logger.info(f"Retrieved {len(result)} indexes")
            return result
        app_logger.warning("Failed to retrieve indexes list")
        return []
    
    @log_exception
    def get_unused_indexes(self) -> List[Dict[str, Any]]:
        """
        Get list of unused indexes in the database.
        
        Returns:
            List of dictionaries with unused index information
        """
        app_logger.info("Fetching unused indexes list")
        query = """
        SELECT
            t.tablename as table_name,
            i.indexname as index_name,
            i.indexdef as index_definition,
            idx_scan as scans,
            pg_size_pretty(pg_relation_size(ui.indexrelid)) as index_size
        FROM pg_stat_user_indexes ui
        JOIN pg_indexes i ON ui.indexrelname = i.indexname AND ui.schemaname = i.schemaname
        JOIN pg_tables t ON i.tablename = t.tablename AND i.schemaname = t.schemaname
        WHERE t.schemaname NOT IN ('pg_catalog', 'information_schema')
        AND idx_scan = 0
        ORDER BY pg_relation_size(ui.indexrelid) DESC;
        """
        success, result = self.execute_query(query)
        if success:
            app_logger.info(f"Retrieved {len(result)} unused indexes")
            return result
        app_logger.warning("Failed to retrieve unused indexes list")
        return []
    
    @log_exception
    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary with table statistics
        """
        app_logger.info(f"Fetching statistics for table: {table_name}")
        # Get basic table stats
        query = """
        SELECT
            pg_stat_user_tables.schemaname as schema,
            pg_stat_user_tables.relname as table_name,
            pg_stat_user_tables.seq_scan,
            pg_stat_user_tables.seq_tup_read,
            pg_stat_user_tables.idx_scan,
            pg_stat_user_tables.idx_tup_fetch,
            pg_stat_user_tables.n_tup_ins,
            pg_stat_user_tables.n_tup_upd,
            pg_stat_user_tables.n_tup_del,
            pg_stat_user_tables.n_live_tup,
            pg_stat_user_tables.n_dead_tup,
            pg_stat_user_tables.last_vacuum,
            pg_stat_user_tables.last_autovacuum,
            pg_stat_user_tables.last_analyze,
            pg_stat_user_tables.last_autoanalyze,
            pg_size_pretty(pg_total_relation_size(quote_ident(pg_stat_user_tables.schemaname)::text || '.' || quote_ident(pg_stat_user_tables.relname)::text)) as total_size
        FROM pg_stat_user_tables
        WHERE relname = %s;
        """
        success, result = self.execute_query(query, (table_name,))
        if not success or not result:
            app_logger.warning(f"Failed to get statistics for table: {table_name}")
            return {}
        
        app_logger.debug(f"Retrieved basic stats for table: {table_name}")
        table_stats = dict(result[0])
        
        # Get column info
        app_logger.debug(f"Fetching column information for table: {table_name}")
        column_query = """
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position;
        """
        success, cols = self.execute_query(column_query, (table_name,))
        if success:
            app_logger.debug(f"Retrieved {len(cols)} columns for table: {table_name}")
            table_stats['columns'] = [dict(col) for col in cols]
        else:
            app_logger.warning(f"Failed to retrieve column information for table: {table_name}")
        
        # Get index info for this table
        app_logger.debug(f"Fetching index information for table: {table_name}")
        index_query = """
        SELECT
            i.indexname as index_name,
            i.indexdef as index_definition,
            ui.idx_scan as scans,
            pg_size_pretty(pg_relation_size(ui.indexrelid)) as index_size
        FROM pg_stat_user_indexes ui
        JOIN pg_indexes i ON ui.indexrelname = i.indexname AND ui.schemaname = i.schemaname
        WHERE i.tablename = %s
        ORDER BY ui.idx_scan DESC;
        """
        success, indexes = self.execute_query(index_query, (table_name,))
        if success:
            app_logger.debug(f"Retrieved {len(indexes)} indexes for table: {table_name}")
            table_stats['indexes'] = [dict(idx) for idx in indexes]
        else:
            app_logger.warning(f"Failed to retrieve index information for table: {table_name}")
        
        app_logger.info(f"Completed statistics gathering for table: {table_name}")
        return table_stats