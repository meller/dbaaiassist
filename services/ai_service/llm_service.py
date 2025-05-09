"""
Base LLM service for PostgreSQL DBA Assistant.
Implements P0 AI features:
1. Query explanation in plain language
2. Simple SQL generation from natural language
3. Basic pattern recognition for similar queries
4. AI-assisted index recommendations
5. Contextual help for PostgreSQL concepts
"""

import os
from typing import List, Dict, Any, Optional
import sqlparse
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import SystemMessage

# Support both OpenAI and Google Gemini models
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

class LLMService:
    """Service for interacting with language models for PostgreSQL assistant features."""
    
    def __init__(self, api_key=None, model_provider="gemini", model_name=None):
        """
        Initialize the LLM service.
        
        Args:
            api_key: API key for the chosen model provider
            model_provider: 'gemini' or 'openai'
            model_name: Specific model name (if None, will use defaults)
        """
        self.api_key = api_key
        self.model_provider = model_provider.lower()
        
        # Set default model names based on provider
        if model_name is None:
            if self.model_provider == "openai":
                self.model_name = "gpt-3.5-turbo"
            else:  # gemini
                self.model_name = "gemini-pro"
        else:
            self.model_name = model_name
            
        self.memory = ConversationBufferMemory()
        self._initialize_llm()
        
    def _initialize_llm(self):
        """Initialize the appropriate LLM based on provider."""
        if self.model_provider == "openai":
            if not self.api_key and "OPENAI_API_KEY" in os.environ:
                self.api_key = os.environ["OPENAI_API_KEY"]
                
            self.llm = ChatOpenAI(
                temperature=0.2,
                model_name=self.model_name,
                api_key=self.api_key
            )
        else:  # gemini
            if not self.api_key and "GOOGLE_API_KEY" in os.environ:
                self.api_key = os.environ["GOOGLE_API_KEY"]
                
            self.llm = ChatGoogleGenerativeAI(
                temperature=0.2,
                model=self.model_name,
                google_api_key=self.api_key,
                convert_system_message_to_human=True
            )
        
        # Initialize conversation chain with the LLM
        self.conversation = ConversationChain(
            llm=self.llm,
            memory=self.memory,
            verbose=False
        )
    
    def get_query_explanation(self, query_text: str, schema_context: Optional[str] = None) -> str:
        """
        Explain a SQL query in plain language.
        
        Args:
            query_text: The SQL query to explain
            schema_context: Optional database schema information for context
            
        Returns:
            Plain language explanation of the query
        """
        # Create a prompt for query explanation
        prompt = f"""
        You are a PostgreSQL expert assistant. Explain this PostgreSQL query in simple terms:
        
        ```sql
        {query_text}
        ```
        
        {f'Schema context: {schema_context}' if schema_context else ''}
        
        Explain:
        1. What the query does in plain language
        2. Which tables it accesses and how they're related
        3. Any filtering conditions 
        4. The expected results
        5. Any potential performance concerns
        
        Make your explanation clear and concise.
        """
        return self.conversation.predict(input=prompt)
    
    def generate_sql(self, natural_language_request: str, schema_context: Optional[str] = None) -> str:
        """
        Generate SQL from natural language.
        
        Args:
            natural_language_request: The natural language description of the query
            schema_context: Optional database schema information for context
            
        Returns:
            Generated SQL query
        """
        prompt = f"""
        You are a PostgreSQL expert. Generate a PostgreSQL query based on this request:
        
        "{natural_language_request}"
        
        {f'Database schema: {schema_context}' if schema_context else ''}
        
        First analyze what the user is asking for, then generate the most efficient SQL query.
        Return ONLY the SQL query without explanation or markdown formatting.
        The SQL must follow PostgreSQL syntax and best practices.
        """
        return self.conversation.predict(input=prompt)
    
    def recognize_similar_queries(self, queries: List[str]) -> Dict[str, List[str]]:
        """
        Group similar queries together based on their structure.
        
        Args:
            queries: List of SQL queries to analyze
            
        Returns:
            Dictionary mapping normalized patterns to lists of actual queries
        """
        patterns = {}
        
        for query in queries:
            normalized = self._normalize_query(query)
            if normalized not in patterns:
                patterns[normalized] = []
            patterns[normalized].append(query)
        
        # Filter to only return patterns with more than one query
        return {pattern: queries for pattern, queries in patterns.items() if len(queries) > 1}
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize a query by removing literals and standardizing whitespace.
        
        Args:
            query: The SQL query to normalize
            
        Returns:
            Normalized query pattern
        """
        # Parse the SQL query
        try:
            # Replace string literals with placeholders
            normalized = re.sub(r"'[^']*'", "'?'", query)
            
            # Replace numeric literals with placeholders
            normalized = re.sub(r'\b\d+\b', '?', normalized)
            
            # Standardize whitespace
            normalized = ' '.join(normalized.split())
            
            return normalized
        except Exception:
            # If parsing fails, return the original query
            return query
    
    def get_index_recommendations(self, query: str, schema_context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get AI-assisted index recommendations for a query.
        
        Args:
            query: The SQL query to analyze
            schema_context: Database schema information for context
            
        Returns:
            List of index recommendations
        """
        prompt = f"""
        You are a PostgreSQL performance tuning expert. Analyze this PostgreSQL query for potential index recommendations:
        
        ```sql
        {query}
        ```
        
        {f'Schema context: {schema_context}' if schema_context else ''}
        
        For each recommendation, provide information in the following JSON format:
        ```
        [
          {{
            "table": "table_name",
            "columns": ["column1", "column2"],
            "index_type": "btree|hash|gin|etc",
            "reasoning": "Why this index would help",
            "impact": "high|medium|low"
          }}
        ]
        ```
        
        Consider:
        1. WHERE clauses
        2. JOIN conditions
        3. ORDER BY clauses
        4. GROUP BY clauses
        
        Only suggest indexes that would significantly improve performance. Return only the JSON array.
        """
        
        # Use the LLM to get recommendations
        try:
            response = self.conversation.predict(input=prompt)
            
            # Parse the response to extract the JSON part
            import json
            import re
            
            # Find all text between ```...``` or the entire text if no code blocks
            json_match = re.search(r'```(?:json)?\s*(.*?)```', response, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_str = response.strip()
            
            # Parse the JSON
            recommendations = json.loads(json_str)
            return recommendations
        except Exception as e:
            # If parsing fails, return a message about the error
            return [{"error": f"Failed to parse recommendations: {str(e)}"}]
    
    def get_postgres_help(self, concept: str) -> str:
        """
        Get explanation about PostgreSQL concepts.
        
        Args:
            concept: The PostgreSQL concept to explain
            
        Returns:
            Explanation of the concept
        """
        prompt = f"""
        You are a PostgreSQL expert assistant. Explain the PostgreSQL concept "{concept}" in simple terms.
        
        Your explanation should:
        1. Define what {concept} is
        2. Explain when and why it's useful
        3. Provide a simple example if appropriate
        4. Mention any important considerations or best practices
        5. Keep the explanation clear and concise
        
        Format your response in markdown with appropriate headings and code blocks for examples.
        """
        return self.conversation.predict(input=prompt)
    
    def reset_conversation(self):
        """Reset the conversation history."""
        self.memory.clear()