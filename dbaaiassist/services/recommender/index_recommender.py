import uuid
from typing import List, Dict, Any, Optional
from ...models.recommendation import Recommendation, RecommendationType
from ...models.query import Query

class IndexRecommender:
    """Service for analyzing queries and recommending indexes."""
    
    def __init__(self):
        self.recommendations = []
    
    def analyze_queries(self, queries: List[Query]) -> List[Recommendation]:
        """
        Analyze a list of queries and generate index recommendations.
        
        Args:
            queries: List of Query objects to analyze
            
        Returns:
            List of Recommendation objects for indexes
        """
        self.recommendations = []
        
        # Group queries by tables they access
        table_queries = {}
        for query in queries:
            if not query.tables_accessed:
                continue
                
            for table in query.tables_accessed:
                if table not in table_queries:
                    table_queries[table] = []
                table_queries[table].append(query)
        
        # Analyze each table's queries for potential indexes
        for table, table_q in table_queries.items():
            # Sort queries by execution time (slowest first)
            table_q.sort(key=lambda q: q.execution_time_ms, reverse=True)
            
            # Use a simplified heuristic for this implementation
            # In a real implementation, we would analyze query execution plans
            potential_columns = self._identify_potential_index_columns(table, table_q)
            
            for col_set, queries_impacted in potential_columns.items():
                if len(col_set.split(',')) > 3:
                    # Skip if too many columns in the index
                    continue
                    
                # Calculate impact score (simplified for this implementation)
                # In real implementation, estimate actual impact using query plans
                total_time = sum(q.execution_time_ms for q in queries_impacted)
                frequency = len(queries_impacted)
                impact_score = min(100, (total_time * frequency) / 1000)
                
                # Generate a recommendation
                columns = col_set.split(',')
                index_name = f"idx_{table}_{'_'.join(columns)}"
                
                # Create SQL script for index creation
                sql_script = f"CREATE INDEX {index_name} ON {table} ({col_set});"
                
                # Create recommendation
                recommendation = Recommendation(
                    recommendation_id=str(uuid.uuid4()),
                    type=RecommendationType.INDEX,
                    title=f"Add index on {table}({col_set})",
                    description=f"Creating an index on {table}({col_set}) could improve the performance of {frequency} queries with a total execution time of {total_time:.2f} ms.",
                    impact_score=impact_score,
                    sql_script=sql_script,
                    related_objects=[table],
                    estimated_improvement=f"May reduce query time by up to 80% for {frequency} queries",
                    source_queries=[q.query_id for q in queries_impacted]
                )
                
                self.recommendations.append(recommendation)
        
        # Sort recommendations by impact score
        self.recommendations.sort(key=lambda r: r.impact_score, reverse=True)
        
        return self.recommendations
    
    def _identify_potential_index_columns(self, table: str, queries: List[Query]) -> Dict[str, List[Query]]:
        """
        Identify potential index columns for a table based on queries.
        
        Args:
            table: Table name
            queries: List of queries accessing this table
            
        Returns:
            Dictionary mapping column sets to lists of queries that would benefit
        """
        # This is a simplified implementation for demonstration purposes
        # In a real implementation, we would parse the SQL and extract WHERE/JOIN predicates
        
        potential_columns = {}
        
        for query in queries:
            # Very basic column extraction based on WHERE clause patterns
            # This is overly simplified! In practice, use a proper SQL parser
            query_text = query.query_text.upper()
            
            # Check if it's a SELECT query
            if not query_text.startswith('SELECT'):
                continue
                
            # Extract WHERE clause
            where_pos = query_text.find('WHERE')
            if where_pos == -1:
                continue
                
            where_clause = query_text[where_pos+5:]
            
            # Truncate at next major clause if present
            for clause in ['GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT', 'OFFSET']:
                pos = where_clause.find(clause)
                if pos != -1:
                    where_clause = where_clause[:pos]
            
            # Extract column names from WHERE clause conditions
            # This is a very basic extraction that won't work for complex queries
            conditions = where_clause.split('AND')
            columns = []
            
            for condition in conditions:
                # Look for equality and range conditions
                parts = condition.split('=')
                if len(parts) == 2:
                    col = parts[0].strip()
                    if '.' in col:
                        col = col.split('.')[-1]
                    columns.append(col)
                
                # Check for range conditions
                for op in ['>', '<', '>=', '<=']:
                    if op in condition:
                        parts = condition.split(op)
                        if len(parts) == 2:
                            col = parts[0].strip()
                            if '.' in col:
                                col = col.split('.')[-1]
                            columns.append(col)
            
            if columns:
                # Create a comma-separated list of columns as the key
                col_set = ','.join(sorted(set(columns)))
                
                if col_set not in potential_columns:
                    potential_columns[col_set] = []
                
                potential_columns[col_set].append(query)
        
        return potential_columns
    
    def get_recommendations(self) -> List[Recommendation]:
        """Get all recommendations."""
        return self.recommendations
    
    def get_recommendation_by_id(self, recommendation_id: str) -> Optional[Recommendation]:
        """Get a recommendation by ID."""
        for rec in self.recommendations:
            if rec.recommendation_id == recommendation_id:
                return rec
        return None