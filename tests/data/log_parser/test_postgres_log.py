import unittest
import io
from datetime import datetime
from dbaaiassist.data.log_parser.postgres_log import PostgreSQLLogParser
from dbaaiassist.models.query import Query

class TestPostgreSQLLogParser(unittest.TestCase):
    """Test cases for the PostgreSQL log parser."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.parser = PostgreSQLLogParser()

    def test_multiline_sqlalchemy_log_parsing(self):
        """Test parsing multiline SQLAlchemy log entries."""
        # Create a sample log with multiline SQLAlchemy queries
        sample_log = """
2025-05-09 09:51:35,725 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:35,725 | BEGIN (implicit)
2025-05-09 09:51:35,726 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:35,726 | DELETE FROM stock_company_info WHERE stock_company_info.ticker = %(ticker_1)s
2025-05-09 09:51:35,727 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:35,727 | [cached since 22.06s ago] {'ticker_1': 'MSFT'}
2025-05-09 09:51:35,729 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:35,729 | COMMIT
2025-05-09 09:51:36,738 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:36,738 | BEGIN (implicit)
2025-05-09 09:51:36,739 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:36,739 | SELECT stock_company_info.ticker AS stock_company_info_ticker
2025-05-09 09:51:36,740 - DEBUG - Line 635 did not match any log pattern: FROM stock_company_info
2025-05-09 09:51:36,741 - DEBUG - Line 636 did not match any log pattern: WHERE stock_company_info.ticker = %(ticker_1)s
2025-05-09 09:51:36,742 - DEBUG - Line 637 did not match any log pattern: LIMIT %(param_1)s
2025-05-09 09:51:36,743 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:36,743 | [cached since 22.05s ago] {'ticker_1': 'MSFT', 'param_1': 1}
2025-05-09 09:51:37,295 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:37,295 | INSERT INTO stock_company_info (ticker, short_name) VALUES (%(ticker)s, %(short_name)s)
2025-05-09 09:51:37,296 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:37,296 | [cached since 21.7s ago] {'ticker': 'MSFT', 'short_name': 'Microsoft Corporation'}
2025-05-09 09:51:37,301 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:37,301 | COMMIT
2025-05-09 09:51:37,309 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:37,309 | BEGIN (implicit)
2025-05-09 09:51:37,310 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:37,310 | SELECT stock_company_info.ticker AS stock_company_info_ticker
2025-05-09 09:51:37,311 - DEBUG - Line 644 did not match any log pattern: FROM stock_company_info
2025-05-09 09:51:37,312 - DEBUG - Line 645 did not match any log pattern: WHERE stock_company_info.ticker = %(pk_1)s
2025-05-09 09:51:37,313 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:37,313 | [cached since 21.7s ago] {'pk_1': 'MSFT'}
2025-05-09 09:51:37,314 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:37,314 | SELECT stock_company_info.ticker AS stock_company_info_ticker
2025-05-09 09:51:37,315 - DEBUG - Line 648 did not match any log pattern: FROM stock_company_info
2025-05-09 09:51:37,316 - DEBUG - Line 649 did not match any log pattern: WHERE stock_company_info.ticker = %(ticker_1)s
2025-05-09 09:51:37,317 - DEBUG - Line 650 did not match any log pattern: LIMIT %(param_1)s
2025-05-09 09:51:37,318 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:37,318 | [cached since 22.62s ago] {'ticker_1': 'MSFT', 'param_1': 1}
2025-05-09 09:51:37,319 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:37,319 | ROLLBACK
"""
        # Parse the log data
        file_obj = io.StringIO(sample_log)
        queries = self.parser.parse_file(file_obj)
        
        # Assertions for multiline query handling
        # 1. We should have extracted the BEGIN and COMMIT transaction statements
        transaction_statements = [q.query_text for q in queries if q.query_text.startswith(("BEGIN", "COMMIT", "ROLLBACK"))]
        self.assertGreaterEqual(len(transaction_statements), 3, "Failed to extract transaction statements")
        
        # 2. We should have properly combined multiline SELECT queries
        select_queries = [q for q in queries if q.query_text.startswith("SELECT")]
        self.assertGreaterEqual(len(select_queries), 2, "Failed to extract SELECT queries")
        
        # 3. Each SELECT query should include the FROM and WHERE clauses
        for query in select_queries:
            self.assertIn("FROM", query.query_text, f"Missing FROM clause in query: {query.query_text}")
            self.assertIn("WHERE", query.query_text, f"Missing WHERE clause in query: {query.query_text}")
        
        # 4. Verify we have properly extracted tables
        tables_accessed = set()
        for query in queries:
            if query.tables_accessed:
                tables_accessed.update(query.tables_accessed)
        
        self.assertIn("STOCK_COMPANY_INFO", tables_accessed, "Failed to extract table STOCK_COMPANY_INFO")
        
        # 5. Check that we have the correct total number of queries
        # We should have: 3 transaction statements (BEGIN, COMMIT, ROLLBACK), 
        # 2-3 SELECTs, 1 DELETE, 1 INSERT
        self.assertGreaterEqual(len(queries), 6, f"Expected at least 6 queries, got {len(queries)}")

    def test_expected_result_after_fix(self):
        """Test the expected result after the multiline fix is implemented."""
        # This sample contains a SELECT query broken into multiple lines
        sample_log = """
2025-05-09 09:51:36,739 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:36,739 | SELECT stock_company_info.ticker AS stock_company_info_ticker
2025-05-09 09:51:36,740 - DEBUG - Line 635 did not match any log pattern: FROM stock_company_info
2025-05-09 09:51:36,741 - DEBUG - Line 636 did not match any log pattern: WHERE stock_company_info.ticker = %(ticker_1)s
2025-05-09 09:51:36,742 - DEBUG - Line 637 did not match any log pattern: LIMIT %(param_1)s
2025-05-09 09:51:36,743 - INFO - Matched SQLAlchemy log line: 2025-05-09 09:51:36,743 | [cached since 22.05s ago] {'ticker_1': 'MSFT', 'param_1': 1}
"""
        # Parse the log data
        file_obj = io.StringIO(sample_log)
        queries = self.parser.parse_file(file_obj)
        
        # After fix, we expect exactly one query that combines all parts
        self.assertEqual(len(queries), 1, f"Expected 1 combined query, got {len(queries)}")
        
        if queries:
            query = queries[0]
            # Check that the query contains all parts combined
            self.assertIn("SELECT", query.query_text)
            self.assertIn("FROM stock_company_info", query.query_text)
            self.assertIn("WHERE stock_company_info.ticker", query.query_text)
            self.assertIn("LIMIT", query.query_text)
            
            # Check that the table was properly extracted
            self.assertIn("STOCK_COMPANY_INFO", query.tables_accessed)

if __name__ == '__main__':
    unittest.main()