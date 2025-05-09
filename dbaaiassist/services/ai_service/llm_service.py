"""
LLM Service implementation for PostgreSQL DBA Assistant.
Supports Google Gemini models for AI assistance.
"""

import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional

class LLMService:
    """Service for interacting with Google Gemini LLMs."""
    
    def __init__(self, api_key: str, model_provider: str = "gemini", model_name: str = "gemini-pro"):
        """
        Initialize the LLM service.
        
        Args:
            api_key: API key for the Google Gemini API
            model_provider: Only "gemini" is supported
            model_name: Model name (e.g., "gemini-pro")
        """
        if model_provider.lower() != "gemini":
            raise ValueError("Only 'gemini' model provider is supported")
            
        # Configure the Google Gemini API
        genai.configure(api_key=api_key)
        
        # Use Gemini 2 model directly
        gemini2_model = "gemini-1.5-pro"
        print(f"Using Gemini 2 model: {gemini2_model}")
        
        # Store the model name
        self.model_name = gemini2_model
        
        # Initialize the model - no need for the substring matching logic since we're directly specifying the model
        try:
            self.model = genai.GenerativeModel(gemini2_model)
            print(f"Successfully initialized Gemini 2 model: {gemini2_model}")
        except Exception as e:
            # Fall back to standard Gemini model format
            fallback_model = "models/gemini-pro"
            print(f"Error initializing Gemini 2 model: {e}. Falling back to {fallback_model}")
            self.model_name = fallback_model
            self.model = genai.GenerativeModel(fallback_model)
        
        # Initialize conversation history
        self.conversation = self.model.start_chat(history=[])
    
    def reset_conversation(self):
        """Reset the conversation history."""
        self.conversation = self.model.start_chat(history=[])
    
    def get_postgres_help(self, query: str) -> str:
        """
        Get PostgreSQL help from the LLM.
        
        Args:
            query: The user's query about PostgreSQL
            
        Returns:
            The LLM's response
        """
        try:
            # Add PostgreSQL context to the prompt
            prompt = f"As a PostgreSQL database expert, please help with this question: {query}"
            
            # Get the response from the model
            response = self.conversation.send_message(prompt)
            
            return response.text
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def generate_sql(self, description: str, schema_context: Optional[str] = None) -> str:
        """
        Generate SQL from a natural language description.
        
        Args:
            description: Natural language description of the query
            schema_context: Optional schema context to improve generation
            
        Returns:
            Generated SQL query
        """
        try:
            if schema_context:
                prompt = f"""Generate a PostgreSQL SQL query for the following request:
                {description}
                
                Schema information:
                {schema_context}
                
                Return only the SQL code without explanations."""
            else:
                prompt = f"""Generate a PostgreSQL SQL query for the following request:
                {description}
                
                Return only the SQL code without explanations."""
            
            response = self.model.generate_content(prompt)
            
            # Extract the SQL code
            return response.text.strip().replace("```sql", "").replace("```", "").strip()
        except Exception as e:
            return f"-- Error generating SQL: {str(e)}"
    
    def get_query_explanation(self, query: str, schema_context: Optional[str] = None) -> str:
        """
        Explain a SQL query in plain language.
        
        Args:
            query: The SQL query to explain
            schema_context: Optional schema context to improve explanation
            
        Returns:
            Plain language explanation of the query
        """
        if schema_context:
            prompt = f"""Explain this PostgreSQL query in simple terms:
            ```sql
            {query}
            ```
            
            Schema information:
            {schema_context}
            
            Provide a clear step-by-step explanation of what this query does."""
        else:
            prompt = f"""Explain this PostgreSQL query in simple terms:
            ```sql
            {query}
            ```
            
            Provide a clear step-by-step explanation of what this query does."""
        
        response = self.model.generate_content(prompt)
        
        return response.text
    
    def get_index_recommendations(self, query: str, schema_context: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get index recommendations for a SQL query.
        
        Args:
            query: The SQL query to analyze
            schema_context: Optional schema context to improve recommendations
            
        Returns:
            List of index recommendations as dictionaries
        """
        if schema_context:
            prompt = f"""Analyze this PostgreSQL query and suggest indexes that would improve its performance:
            ```sql
            {query}
            ```
            
            Schema information:
            {schema_context}
            
            Return the recommendations as a JSON array, where each item has these fields:
            - table: the table name
            - columns: array of column names for the index
            - index_type: index type (btree, hash, gin, etc.)
            - reason: why this index would help
            
            Format the response as valid JSON only."""
        else:
            prompt = f"""Analyze this PostgreSQL query and suggest indexes that would improve its performance:
            ```sql
            {query}
            ```
            
            Return the recommendations as a JSON array, where each item has these fields:
            - table: the table name
            - columns: array of column names for the index
            - index_type: index type (btree, hash, gin, etc.)
            - reason: why this index would help
            
            Format the response as valid JSON only."""
        
        response = self.model.generate_content(prompt)
        
        try:
            # Parse the JSON response
            return json.loads(response.text)
        except json.JSONDecodeError:
            # If parsing fails, return an error
            return [{"error": "Failed to parse index recommendations"}]