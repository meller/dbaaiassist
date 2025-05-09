import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import io
import gzip
from ...models.query import Query
from ...utils.logger import get_logger

class PostgreSQLLogParser:
    """Parser for PostgreSQL log files to extract query information."""
    
    # Regular expressions for different log formats
    DEFAULT_LOG_PATTERN = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d+) \w+ \[(\d+)\] (?:\w+@\w+:)?(\w+) \[(\w+)\] (?:LOG|ERROR|WARNING):  (.*)'
    DURATION_PATTERN = r'duration: (\d+\.\d+) ms  (?:statement|execute <unnamed>): (.+)'
    
    # SQLAlchemy log patterns
    SQLALCHEMY_LOG_PATTERN = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) - (\w+) - (.+)'
    SQLALCHEMY_QUERY_PATTERN = r'(SELECT|INSERT|UPDATE|DELETE|BEGIN|COMMIT|ROLLBACK)(.+)'
    SQLALCHEMY_DURATION_PATTERN = r'\[generated in (\d+\.\d+)s\]'
    
    # SQL fragment pattern to identify continuation lines
    SQL_FRAGMENT_PATTERN = r'did not match any log pattern: (.+)'
    
    def __init__(self):
        self.queries = []
        self.log_stats = {
            'total_lines': 0,
            'parsed_queries': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
        
        # State variables for tracking multiline SQL statements
        self.is_collecting_sql = False
        self.sql_parts = []
        self.current_timestamp = None
    
    def parse_file(self, file_obj, sample_size: Optional[int] = None) -> List[Query]:
        """
        Parse a PostgreSQL or SQLAlchemy log file and extract query information.
        
        Args:
            file_obj: File object or file-like object containing the log data
            sample_size: Optional number of lines to sample from the file
            
        Returns:
            List of Query objects extracted from the log
        """
        logger = get_logger(__name__)
        
        self.queries = []
        self.log_stats = {
            'total_lines': 0,
            'parsed_queries': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Reset multiline SQL collection state
        self.is_collecting_sql = False
        self.sql_parts = []
        self.current_timestamp = None
        
        # Handle various file types
        if hasattr(file_obj, 'name') and file_obj.name.endswith('.gz'):
            file_obj = gzip.open(file_obj, 'rt')
        
        # Log the file being processed
        logger.info(f"Starting to parse log file: {getattr(file_obj, 'name', 'unknown')}")
        
        # Read the file content
        content = file_obj.read()
        
        # Handle bytes vs string content
        if isinstance(content, bytes):
            content = content.decode('utf-8')
            
        lines = content.splitlines()
        logger.info(f"Total lines in file: {len(lines)}")
        
        # Sample if requested
        if sample_size and sample_size < len(lines):
            import random
            lines = random.sample(lines, sample_size)
            logger.info(f"Sampled {sample_size} lines")
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue  # Skip empty lines
                
            self.log_stats['total_lines'] += 1
            
            # Log every 1000 lines for progress tracking
            if i % 1000 == 0:
                logger.info(f"Processed {i} lines, found {self.log_stats['parsed_queries']} queries so far")
            
            # Try to match PostgreSQL log pattern
            pg_match = re.match(self.DEFAULT_LOG_PATTERN, line)
            # Try to match SQLAlchemy log pattern
            sa_match = re.match(self.SQLALCHEMY_LOG_PATTERN, line)
            
            if pg_match:
                # PostgreSQL log parsing (unchanged)
                timestamp_str, pid, user_db, session_id, message = pg_match.groups()
                logger.debug(f"Matched PostgreSQL log line: {timestamp_str} | {message[:50]}...")
                
                # Process as before...
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                    self._update_time_stats(timestamp)
                        
                    # Look for query duration information
                    duration_match = re.search(self.DURATION_PATTERN, message)
                    if duration_match:
                        duration_ms, query_text = duration_match.groups()
                        
                        # Create and add Query object
                        self._add_query(
                            query_id=f"{pid}_{timestamp.timestamp()}",
                            query_text=query_text,
                            execution_time_ms=float(duration_ms),
                            timestamp=timestamp,
                            database=user_db.split('@')[-1] if '@' in user_db else user_db
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing query: {str(e)}")
                    self.log_stats['errors'] += 1
                    continue
            
            elif sa_match:
                # SQLAlchemy log parsing
                timestamp_str, log_level, message = sa_match.groups()
                logger.debug(f"Matched SQLAlchemy log line: {timestamp_str} | {message[:50]}...")
                
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                    self._update_time_stats(timestamp)
                    
                    # Check if this is a SQL statement
                    if message.startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE')):
                        # Start collecting a SQL statement
                        self.is_collecting_sql = True
                        self.sql_parts = [message]
                        self.current_timestamp = timestamp
                    
                    # Check for transaction statements
                    elif message.startswith(('BEGIN', 'COMMIT', 'ROLLBACK')):
                        # If we're collecting a SQL statement, finalize it
                        if self.is_collecting_sql and self.sql_parts:
                            complete_query = ' '.join(self.sql_parts)
                            self._add_query(
                                query_id=f"sqlalchemy_{self.current_timestamp.timestamp()}",
                                query_text=complete_query,
                                execution_time_ms=0.1,  # Default value
                                timestamp=self.current_timestamp,
                                database="sqlalchemy"
                            )
                            # Reset collection
                            self.is_collecting_sql = False
                            self.sql_parts = []
                        
                        # Add the transaction statement
                        self._add_query(
                            query_id=f"sqlalchemy_{timestamp.timestamp()}",
                            query_text=message,
                            execution_time_ms=0.1,  # Nominal value
                            timestamp=timestamp,
                            database="sqlalchemy"
                        )
                    
                    # Check for query completion (cache/timing info)
                    elif message.startswith('[') and self.is_collecting_sql:
                        # Finalize the current SQL statement
                        if self.sql_parts:
                            complete_query = ' '.join(self.sql_parts)
                            self._add_query(
                                query_id=f"sqlalchemy_{self.current_timestamp.timestamp()}",
                                query_text=complete_query,
                                execution_time_ms=0.1,  # Default value
                                timestamp=self.current_timestamp,
                                database="sqlalchemy"
                            )
                        
                        # Reset collection
                        self.is_collecting_sql = False
                        self.sql_parts = []
                        
                except Exception as e:
                    logger.error(f"Error processing SQLAlchemy log: {str(e)}")
                    self.log_stats['errors'] += 1
                    continue
            
            else:
                # This section is key for handling SQL fragments in multiline statements
                # Check if this is a fragment line from a multiline SQL statement
                if self.is_collecting_sql:
                    fragment_identified = False
                    
                    # Check for lines containing SQL fragments after "did not match any log pattern:"
                    if "did not match any log pattern:" in line and ":" in line:
                        # Extract fragment after the colon
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            sql_fragment = parts[1].strip()
                            self.sql_parts.append(sql_fragment)
                            logger.debug(f"Identified SQL fragment: {sql_fragment}")
                            fragment_identified = True
                    
                    # If not already identified, check for common SQL clauses that might be fragments
                    if not fragment_identified:
                        for clause in ['FROM', 'WHERE', 'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT', 'JOIN', 'UNION']:
                            if line.strip().upper().startswith(clause):
                                self.sql_parts.append(line.strip())
                                logger.debug(f"Identified SQL clause fragment: {line.strip()}")
                                fragment_identified = True
                                break
                    
                    # If we identified a fragment, continue to the next line
                    if fragment_identified:
                        continue
                
                # If we didn't find a SQL fragment, just log the line
                logger.debug(f"Line {i} did not match any log pattern: {line[:50]}...")
        
        # Process any remaining incomplete SQL statement
        if self.is_collecting_sql and self.sql_parts and self.current_timestamp:
            complete_query = ' '.join(self.sql_parts)
            self._add_query(
                query_id=f"sqlalchemy_{self.current_timestamp.timestamp()}",
                query_text=complete_query,
                execution_time_ms=0.1,  # Default value
                timestamp=self.current_timestamp,
                database="sqlalchemy"
            )
        
        logger.info(f"Finished parsing log file. Found {len(self.queries)} queries out of {self.log_stats['total_lines']} lines.")
        return self.queries
    
    def _process_postgres_log(self, match):
        """Process a standard PostgreSQL log line."""
        logger = get_logger(__name__)
        timestamp_str, pid, user_db, session_id, message = match.groups()
        
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
            self._update_time_stats(timestamp)
            
            # Look for query duration information
            duration_match = re.search(self.DURATION_PATTERN, message)
            if duration_match:
                duration_ms, query_text = duration_match.groups()
                
                # Create and add Query object
                self._add_query(
                    query_id=f"{pid}_{timestamp.timestamp()}",
                    query_text=query_text,
                    execution_time_ms=float(duration_ms),
                    timestamp=timestamp,
                    database=user_db.split('@')[-1] if '@' in user_db else user_db
                )
                
        except Exception as e:
            logger.error(f"Error processing PostgreSQL log: {str(e)}")
            self.log_stats['errors'] += 1
    
    def _process_sql_message(self, message, timestamp):
        """Process an SQL-related log message."""
        # Check if this is a SQL statement or transaction
        if message.startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE')):
            # Start a new SQL statement collection
            self.is_collecting_sql = True
            self.sql_parts = [message]
            self.current_timestamp = timestamp
            
        elif message.startswith(('BEGIN', 'COMMIT', 'ROLLBACK')):
            # Handle any in-progress SQL statement
            if self.is_collecting_sql and self.sql_parts:
                complete_query = ' '.join(self.sql_parts)
                self._add_query(
                    query_id=f"sqlalchemy_{self.current_timestamp.timestamp()}",
                    query_text=complete_query,
                    execution_time_ms=0.1,
                    timestamp=self.current_timestamp,
                    database="sqlalchemy"
                )
                self.is_collecting_sql = False
                self.sql_parts = []
            
            # Add the transaction statement as a separate query
            self._add_query(
                query_id=f"sqlalchemy_{timestamp.timestamp()}",
                query_text=message,
                execution_time_ms=0.1,
                timestamp=timestamp,
                database="sqlalchemy"
            )
            
        elif message.startswith('[') and self.is_collecting_sql and self.sql_parts:
            # End of a SQL statement with timing/caching info
            complete_query = ' '.join(self.sql_parts)
            
            # Extract execution time if available
            duration_ms = 0.1  # Default
            
            # Check for cached query timing
            if 'cached since' in message:
                cache_match = re.search(r'cached since (\d+\.\d+)s ago', message)
                if cache_match:
                    # For cached queries, we use the cache age as an approximation of execution time
                    cache_age_s = float(cache_match.group(1))
                    # Convert to milliseconds with a reduction factor since cache age != execution time
                    # Using a nominal factor to represent that execution was likely faster than cache age
                    duration_ms = min(cache_age_s * 100, 10.0)  # Cap at 10ms for cached queries
            
            # Check for generated time (this is more accurate when available)
            elif 'generated in' in message:
                duration_match = re.search(r'generated in (\d+\.\d+)s', message)
                if duration_match:
                    duration_s = float(duration_match.group(1))
                    duration_ms = duration_s * 1000
            
            # Add the completed query
            self._add_query(
                query_id=f"sqlalchemy_{self.current_timestamp.timestamp()}",
                query_text=complete_query,
                execution_time_ms=duration_ms,
                timestamp=self.current_timestamp,
                database="sqlalchemy"
            )
            
            # Reset collection state
            self.is_collecting_sql = False
            self.sql_parts = []
    
    def _process_simplified_message(self, message: str, timestamp: datetime) -> None:
        """Process a simplified log message (for testing)."""
        # If it starts with SQL keywords, it's a SQL statement
        if message.startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE')):
            # Start collecting a new SQL statement
            self.is_collecting_sql = True
            self.sql_parts = [message]
            self.current_timestamp = timestamp
        
        # If it's a transaction statement, add it directly
        elif message.startswith(('BEGIN', 'COMMIT', 'ROLLBACK')):
            self._add_query(
                query_id=f"sqlalchemy_{timestamp.timestamp()}",
                query_text=message,
                execution_time_ms=0.1,
                timestamp=timestamp,
                database="sqlalchemy"
            )
        
        # If it contains cached/timing info, finalize the current SQL statement
        elif message.startswith('[') and self.is_collecting_sql:
            if self.sql_parts:
                complete_query = ' '.join(self.sql_parts)
                
                # Extract the execution time if available
                duration_ms = 0.1  # Default value
                if 'generated in' in message:
                    duration_match = re.search(r'generated in (\d+\.\d+)s', message)
                    if duration_match:
                        duration_s = float(duration_match.group(1))
                        duration_ms = duration_s * 1000
                
                # Add the completed query
                self._add_query(
                    query_id=f"sqlalchemy_{self.current_timestamp.timestamp()}",
                    query_text=complete_query,
                    execution_time_ms=duration_ms,
                    timestamp=self.current_timestamp,
                    database="sqlalchemy"
                )
                
                # Reset collection
                self.is_collecting_sql = False
                self.sql_parts = []
    
    def _update_time_stats(self, timestamp: datetime) -> None:
        """Update the start and end time statistics based on the timestamp."""
        if not self.log_stats['start_time'] or timestamp < self.log_stats['start_time']:
            self.log_stats['start_time'] = timestamp
        if not self.log_stats['end_time'] or timestamp > self.log_stats['end_time']:
            self.log_stats['end_time'] = timestamp
    
    def _add_query(self, query_id: str, query_text: str, execution_time_ms: float, 
                  timestamp: datetime, database: str) -> None:
        """Create and add a Query object to the queries list."""
        # Extract tables referenced in the query
        tables_accessed = self._extract_tables(query_text)
        
        # Create a Query object
        query = Query(
            query_id=query_id,
            query_text=query_text,
            execution_time_ms=execution_time_ms,
            timestamp=timestamp,
            database=database,
            tables_accessed=tables_accessed
        )
        
        # Add to the list of queries
        self.queries.append(query)
        self.log_stats['parsed_queries'] += 1
    
    def _extract_tables(self, query_text: str) -> List[str]:
        """
        Extract table names from a SQL query.
        This handles both PostgreSQL and SQLAlchemy query formats.
        """
        # Convert to uppercase for case-insensitive matching
        query_upper = query_text.upper()
        
        tables = []
        
        # Skip non-query statements
        if query_upper.startswith(('BEGIN', 'COMMIT', 'ROLLBACK')):
            return tables
        
        # Look for FROM and JOIN clauses
        from_pos = query_upper.find('FROM')
        if from_pos != -1:
            # Extract the FROM clause
            from_clause = query_upper[from_pos + 4:]
            
            # Truncate at the next clause if present
            for clause in ['WHERE', 'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT', 'OFFSET']:
                pos = from_clause.find(clause)
                if pos != -1:
                    from_clause = from_clause[:pos]
            
            # Split the FROM clause into table references
            table_refs = from_clause.split(',')
            
            for ref in table_refs:
                # Remove any table aliases and extract the table name
                parts = ref.strip().split()
                if parts:
                    table = parts[0].strip('"\'`[]')
                    if table:
                        tables.append(table)
        
        # Look for JOIN clauses
        join_pos = 0
        while True:
            join_pos = query_upper.find('JOIN', join_pos)
            if join_pos == -1:
                break
                
            # Extract the table name after JOIN
            join_clause = query_upper[join_pos + 4:].strip()
            parts = join_clause.split()
            if parts:
                table = parts[0].strip('"\'`[]')
                if table:
                    tables.append(table)
            
            join_pos += 4
        
        # Look for INSERT INTO, UPDATE and DELETE FROM patterns
        if query_upper.startswith('INSERT INTO'):
            parts = query_upper[11:].strip().split()
            if parts:
                table = parts[0].strip('"\'`[]')
                if table:
                    tables.append(table)
        
        elif query_upper.startswith('UPDATE'):
            parts = query_upper[6:].strip().split()
            if parts:
                table = parts[0].strip('"\'`[]')
                if table:
                    tables.append(table)
        
        elif query_upper.startswith('DELETE FROM'):
            parts = query_upper[11:].strip().split()
            if parts:
                table = parts[0].strip('"\'`[]')
                if table:
                    tables.append(table)
        
        return list(set(tables))  # Return unique table names
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the parsed log."""
        return self.log_stats
    
    def get_slow_queries(self, threshold_ms: float = 100.0) -> List[Query]:
        """Get queries that exceed the specified duration threshold."""
        return [q for q in self.queries if q.execution_time_ms >= threshold_ms]
    
    def get_query_patterns(self) -> List[Tuple[str, List[Query]]]:
        """
        Group similar queries into patterns.
        Returns a list of (pattern, queries) tuples.
        """
        patterns = {}
        
        for query in self.queries:
            # Generate a simplified pattern by replacing literals
            pattern = self._generate_query_pattern(query.query_text)
            
            if pattern not in patterns:
                patterns[pattern] = []
                
            patterns[pattern].append(query)
        
        # Convert to list of tuples and sort by frequency (most common first)
        pattern_list = [(pattern, queries) for pattern, queries in patterns.items()]
        pattern_list.sort(key=lambda x: len(x[1]), reverse=True)
        
        return pattern_list
    
    def _generate_query_pattern(self, query_text: str) -> str:
        """
        Generate a simplified pattern for a query by replacing literals with placeholders.
        """
        # Replace numeric literals
        pattern = re.sub(r'\b\d+\b', 'N', query_text)
        
        # Replace string literals
        pattern = re.sub(r"'[^']*'", "'S'", pattern)
        
        # Replace UUID literals
        pattern = re.sub(r"'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'", "'UUID'", pattern)
        
        return pattern