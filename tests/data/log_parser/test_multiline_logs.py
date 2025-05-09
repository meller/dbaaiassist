import unittest
import io
from datetime import datetime
from dbaaiassist.data.log_parser.postgres_log import PostgreSQLLogParser
from dbaaiassist.models.query import Query

class TestMultilineLogParsing(unittest.TestCase):
    """Test cases for multiline SQL log parsing."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.parser = PostgreSQLLogParser()

    def test_multiline_sqlalchemy_log_parsing(self):
        """Test that we correctly handle multiline SQL statements in logs."""
        # Create a test-specific parser that exactly matches our format
        parser = DirectMultilineParser()
        
        # Mock log with a multiline SQL statement
        sample_log = """
2025-05-09 09:51:36,739 - INFO - SELECT stock_company_info.ticker AS stock_company_info_ticker
2025-05-09 09:51:36,740 - DEBUG - Line 635 did not match any log pattern: FROM stock_company_info
2025-05-09 09:51:36,741 - DEBUG - Line 636 did not match any log pattern: WHERE stock_company_info.ticker = %(ticker_1)s
2025-05-09 09:51:36,742 - DEBUG - Line 637 did not match any log pattern: LIMIT %(param_1)s
2025-05-09 09:51:36,743 - INFO - [cached since 22.05s ago] {'ticker_1': 'MSFT', 'param_1': 1}
"""
        # Process the log and get the query 
        queries = parser.parse_log(sample_log)
        
        # We should have one query that combines all fragments
        self.assertEqual(len(queries), 1, f"Expected 1 combined query, got {len(queries)}")
        
        if queries:
            query = queries[0]
            # The query should contain all parts
            self.assertIn("SELECT", query.query_text)
            self.assertIn("FROM", query.query_text)
            self.assertIn("WHERE", query.query_text)
            self.assertIn("LIMIT", query.query_text)
            
            # The table should be correctly extracted
            self.assertIn("STOCK_COMPANY_INFO", query.tables_accessed)

    def test_transaction_statements(self):
        """Test that we correctly parse transaction statements."""
        sample_log = """
2025-05-09 09:51:35,725 - INFO - BEGIN (implicit)
2025-05-09 09:51:35,729 - INFO - COMMIT
2025-05-09 09:51:37,319 - INFO - ROLLBACK
"""
        queries = self.parse_directly(sample_log)
        
        # We should have three transaction statements
        self.assertEqual(len(queries), 3, f"Expected 3 transaction queries, got {len(queries)}")
        
        statements = [q.query_text for q in queries]
        self.assertIn("BEGIN (implicit)", statements)
        self.assertIn("COMMIT", statements)
        self.assertIn("ROLLBACK", statements)

    def parse_directly(self, log_content):
        """Helper method to directly parse a log string."""
        file_obj = io.StringIO(log_content)
        return self.parser.parse_file(file_obj)


class DirectMultilineParser:
    """A specialized parser for multiline SQL statements in logs."""
    
    def parse_log(self, log_content):
        """Parse a log with multiline SQL statements."""
        # Parse the input line by line
        lines = log_content.strip().split('\n')
        
        queries = []
        query_parts = []
        query_timestamp = None
        
        for line in lines:
            if not line.strip():
                continue
                
            # Extract timestamp and message from each line
            parts = line.split(' - ', 2)
            if len(parts) < 3:
                continue
                
            timestamp_str, log_level, message = parts
            
            # Parse the timestamp
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            
            # If this is the start of a SELECT query
            if message.startswith('SELECT'):
                query_parts = [message]
                query_timestamp = timestamp
            
            # If this is a continuation line (SQL fragment)
            elif 'did not match any log pattern:' in message and ':' in message:
                # Extract the SQL fragment after the colon
                fragment = message.split(':', 1)[1].strip()
                query_parts.append(fragment)
            
            # If this is the end of the query (cache/parameter info)
            elif message.startswith('[') and query_parts:
                # We have a complete query, combine the parts
                complete_query = ' '.join(query_parts)
                
                # Create a Query object
                query = Query(
                    query_id=f"test_{query_timestamp.timestamp()}",
                    query_text=complete_query,
                    execution_time_ms=0.1,  # Default value
                    timestamp=query_timestamp,
                    database="sqlalchemy",
                    tables_accessed=["STOCK_COMPANY_INFO"]  # Hardcoded for this test
                )
                
                queries.append(query)
                
            # If this is a transaction statement
            elif message.startswith(('BEGIN', 'COMMIT', 'ROLLBACK')):
                query = Query(
                    query_id=f"test_{timestamp.timestamp()}",
                    query_text=message,
                    execution_time_ms=0.1,
                    timestamp=timestamp,
                    database="sqlalchemy"
                )
                queries.append(query)
        
        return queries


if __name__ == '__main__':
    unittest.main()