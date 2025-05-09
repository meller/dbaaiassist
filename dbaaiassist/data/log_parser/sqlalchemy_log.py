import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import io
from ...models.query import Query
from ...utils.logger import get_logger

class SQLAlchemyLogParser:
    """Parser for SQLAlchemy log output to extract query information."""
    
    # Regular expressions for different log formats
    LOG_PATTERN = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) - (\w+) - (.+)'
    SQL_PATTERN = r'(\[raw sql\]|generated in (\d+\.\d+)s) (.+)'
    
    def __init__(self):
        self.queries = []
        self.log_stats = {
            'total_lines': 0,
            'parsed_queries': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def parse_file(self, file_obj, sample_size: Optional[int] = None) -> List[Query]:
        """
        Parse a SQLAlchemy log file and extract query information.
        
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
        
        # Read the file content
        content = file_obj.read()
        lines = content.splitlines()
        logger.info(f"Total lines in file: {len(lines)}")
        
        # Sample if requested
        if sample_size and sample_size < len(lines):
            import random
            lines = random.sample(lines, sample_size)
            logger.info(f"Sampled {sample_size} lines")
        
        # Process each line
        current_query_text = None
        current_timestamp = None
        current_params = None
        current_execution_time = None
        
        for i, line in enumerate(lines):
            self.log_stats['total_lines'] += 1
            
            # Log every 1000 lines for progress tracking
            if i % 1000 == 0:
                logger.info(f"Processed {i} lines, found {self.log_stats['parsed_queries']} queries so far")
            
            # Try to match the log line pattern
            log_match = re.match(self.LOG_PATTERN, line)
            
            if log_match:
                timestamp_str, level, message = log_match.groups()
                
                # Parse the timestamp
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                    
                    # Update log statistics time range
                    if not self.log_stats['start_time'] or timestamp < self.log_stats['start_time']:
                        self.log_stats['start_time'] = timestamp
                    if not self.log_stats['end_time'] or timestamp > self.log_stats['end_time']:
                        self.log_stats['end_time'] = timestamp
                        
                except Exception as e:
                    logger.error(f"Error parsing timestamp {timestamp_str}: {str(e)}")
                    self.log_stats['errors'] += 1
                    continue
                
                # Handle SQL queries
                if message.startswith("SELECT") or message.startswith("INSERT") or message.startswith("UPDATE") or message.startswith("DELETE") or message.startswith("BEGIN") or message.startswith("ROLLBACK") or message.startswith("COMMIT") or message.startswith("show") or message.startswith("select"):
                    current_query_text = message
                    current_timestamp = timestamp
                    current_params = None
                    current_execution_time = None
                
                # Handle parameters or execution time
                elif current_query_text:
                    sql_match = re.match(self.SQL_PATTERN, message)
                    if sql_match:
                        if sql_match.group(1) == '[raw sql]':
                            # This is the parameters
                            try:
                                current_params = eval(sql_match.group(3))
                            except:
                                current_params = sql_match.group(3)
                        else:
                            # This is execution time
                            current_execution_time = float(sql_match.group(2)) * 1000  # Convert to ms
                            
                            # Now we have all information for a query, create the Query object
                            try:
                                # Extract tables referenced in the query
                                tables_accessed = self._extract_tables(current_query_text)
                                
                                # Create a Query object
                                query = Query(
                                    query_id=f"sqlalchemy_{current_timestamp.timestamp()}",
                                    query_text=current_query_text,
                                    execution_time_ms=current_execution_time if current_execution_time else 0.0,
                                    timestamp=current_timestamp,
                                    database="unknown",  # SQLAlchemy logs often don't include database name
                                    tables_accessed=tables_accessed,
                                    parameters=current_params
                                )
                                
                                # Add to the list of queries
                                self.queries.append(query)
                                self.log_stats['parsed_queries'] += 1
                                
                                # Reset current query data
                                current_query_text = None
                                current_timestamp = None
                                current_params = None
                                current_execution_time = None
                                
                            except Exception as e:
                                logger.error(f"Error processing SQLAlchemy query: {str(e)}")
                                self.log_stats['errors'] += 1
                                
                # If we see ROLLBACK or COMMIT without parameters, create a simpler Query object
                elif message in ("ROLLBACK", "BEGIN (implicit)", "COMMIT"):
                    try:
                        query = Query(
                            query_id=f"sqlalchemy_{timestamp.timestamp()}",
                            query_text=message,
                            execution_time_ms=0.0,
                            timestamp=timestamp,
                            database="unknown",
                            tables_accessed=[],
                            parameters={}
                        )
                        
                        self.queries.append(query)
                        self.log_stats['parsed_queries'] += 1
                    except Exception as e:
                        logger.error(f"Error processing transaction query: {str(e)}")
                        self.log_stats['errors'] += 1
            
        logger.info(f"Finished parsing SQLAlchemy log file. Found {len(self.queries)} queries out of {self.log_stats['total_lines']} lines.")
        return self.queries
    
    def _extract_tables(self, query_text: str) -> List[str]:
        """
        Extract table names from a SQL query.
        This is a simplified implementation and might not work for all cases.
        """
        # Convert to uppercase for case-insensitive matching
        query_upper = query_text.upper()
        
        tables = []
        
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
        """
        patterns = {}
        
        for query in self.queries:
            # Normalize the query to create a pattern
            pattern = self._normalize_query(query.query_text)
            
            if pattern not in patterns:
                patterns[pattern] = []
            
            patterns[pattern].append(query)
        
        # Convert to list of tuples and sort by count
        result = [(pattern, queries) for pattern, queries in patterns.items()]
        result.sort(key=lambda x: len(x[1]), reverse=True)
        
        return result
    
    def _normalize_query(self, query_text: str) -> str:
        """
        Normalize a query by replacing literals with placeholders.
        """
        # Remove SQL comments
        query = re.sub(r'--.*?$|/\*.*?\*/', '', query_text, flags=re.MULTILINE | re.DOTALL)
        
        # Replace string literals
        query = re.sub(r"'[^']*'", "'?'", query)
        
        # Replace numeric literals
        query = re.sub(r'\b\d+\b', '?', query)
        
        # Replace LIMIT/OFFSET parameters
        query = re.sub(r'LIMIT \?', 'LIMIT ?', query, flags=re.IGNORECASE)
        query = re.sub(r'OFFSET \?', 'OFFSET ?', query, flags=re.IGNORECASE)
        
        return query.strip()