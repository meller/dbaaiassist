"""
AI Assistant page for PostgreSQL DBA Assistant.
Implements the P0 AI features interface.
"""

import streamlit as st
import json
from dbaaiassist.services.ai_service import LLMService

def show():
    """Display the AI Assistant page."""
    st.title("AI Assistant")
    
    # Get or create session state for LLM service and chat history
    if "llm_service" not in st.session_state:
        st.session_state.llm_service = None
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Sidebar for API key and model settings
    with st.sidebar:
        st.subheader("AI Settings")
        
        # API key input
        api_key = st.text_input("Google Gemini API Key", type="password", 
                                help="Your API key is stored only for the current session")
        
        # Model selection (Gemini only)
        model_name = st.selectbox(
            "Gemini Model",
            options=["gemini-1.5-pro", "gemini-pro"],
            index=0,
            help="Select which Gemini model to use"
        )
        
        # Connect button
        connect_button = st.button("Connect to AI")
        
        if connect_button:
            try:
                # Initialize LLM service with Gemini
                st.session_state.llm_service = LLMService(
                    api_key=api_key,
                    model_provider="gemini",
                    model_name=model_name
                )
                st.sidebar.success("Connected to Gemini AI")
                
                # Reset conversation
                st.session_state.messages = []
            except Exception as e:
                st.sidebar.error(f"Failed to connect: {str(e)}")
        
        # Reset conversation button
        if st.session_state.llm_service is not None:
            if st.button("Reset Conversation"):
                st.session_state.llm_service.reset_conversation()
                st.session_state.messages = []
                st.sidebar.success("Conversation reset")
    
    # Check if LLM service is initialized
    if st.session_state.llm_service is None:
        st.info("Please enter your Google Gemini API key in the sidebar and connect to AI to start.")
        
        with st.expander("About AI Features"):
            st.markdown("""
            ## PostgreSQL DBA Assistant AI Features
            
            This AI Assistant provides several helpful features for PostgreSQL database management:
            
            1. **Query Explanation**: Get plain language explanations of complex SQL queries
            2. **SQL Generation**: Generate SQL queries from natural language descriptions
            3. **Pattern Recognition**: Identify similar queries in your workload
            4. **Index Recommendations**: Get AI-assisted index suggestions for performance tuning
            5. **PostgreSQL Help**: Ask questions about PostgreSQL concepts and best practices
            
            To get started, enter your Google Gemini API key in the sidebar and click "Connect to AI".
            """)
        return
    
    # Create tabs for different AI features
    tabs = st.tabs([
        "Chat Assistant", 
        "SQL Generator", 
        "Query Explainer",
        "Index Recommendations"
    ])
    
    # Tab 1: Chat Assistant
    with tabs[0]:
        st.header("PostgreSQL Assistant")
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask about PostgreSQL..."):
            # Add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate AI response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = st.session_state.llm_service.get_postgres_help(prompt)
                    st.markdown(response)
            
            # Add assistant response to history
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Tab 2: SQL Generator
    with tabs[1]:
        st.header("SQL Generator")
        
        schema_expander = st.expander("Schema Context (Optional)")
        with schema_expander:
            schema_context = st.text_area(
                "Provide table definitions, columns, and relationships to improve SQL generation",
                height=150,
                help="Example: 'customers table with id, name, email; orders table with id, customer_id, amount, date'"
            )
        
        natural_query = st.text_area(
            "Describe what you want to query in natural language",
            height=100,
            placeholder="Example: Show me all customers who placed orders over $1000 last month",
            help="Describe the data you want to retrieve in plain English"
        )
        
        if st.button("Generate SQL") and natural_query:
            with st.spinner("Generating SQL..."):
                sql = st.session_state.llm_service.generate_sql(
                    natural_query, 
                    schema_context if schema_context else None
                )
                
                st.code(sql, language="sql")
                
                # Add copy button
                st.button("Copy to clipboard", 
                         on_click=lambda: st.write("SQL copied to clipboard"))
                
                # Add an explanation
                with st.expander("SQL Explanation"):
                    explanation = st.session_state.llm_service.get_query_explanation(sql, schema_context)
                    st.markdown(explanation)
    
    # Tab 3: Query Explainer
    with tabs[2]:
        st.header("Query Explainer")
        
        query = st.text_area(
            "Enter SQL query to explain",
            height=150,
            placeholder="SELECT * FROM ...",
            help="Paste a SQL query to get a plain-language explanation"
        )
        
        schema_context = st.text_area(
            "Schema Context (Optional)",
            height=100,
            help="Provide additional schema context to improve the explanation",
            placeholder="Example: customers(id, name, email), orders(id, customer_id, amount)"
        )
        
        if st.button("Explain Query") and query:
            with st.spinner("Analyzing query..."):
                explanation = st.session_state.llm_service.get_query_explanation(
                    query,
                    schema_context if schema_context else None
                )
                
                st.markdown(explanation)
    
    # Tab 4: Index Recommendations
    with tabs[3]:
        st.header("Index Recommendations")
        
        query = st.text_area(
            "Enter SQL query for index recommendations",
            height=150,
            placeholder="SELECT * FROM ...",
            help="Paste a SQL query to get index recommendations"
        )
        
        schema_context = st.text_area(
            "Schema Context (Optional)",
            height=100,
            help="Provide table definitions, existing indexes, and data volumes for better recommendations",
            placeholder="Example: users(id, name, email) has 1M rows; posts(id, user_id, title) has 5M rows"
        )
        
        if st.button("Get Index Recommendations") and query:
            with st.spinner("Analyzing query for index opportunities..."):
                recommendations = st.session_state.llm_service.get_index_recommendations(
                    query,
                    schema_context if schema_context else None
                )
                
                if recommendations and not (len(recommendations) == 1 and "error" in recommendations[0]):
                    st.success(f"Found {len(recommendations)} potential index recommendations")
                    
                    for i, rec in enumerate(recommendations):
                        with st.expander(f"Recommendation {i+1}: Index on {rec.get('table', 'unknown')}.{', '.join(rec.get('columns', []))}"):
                            st.json(rec)
                            
                            # Create index creation SQL
                            index_name = f"idx_{rec.get('table')}_{('_').join(rec.get('columns', []))}"
                            columns_str = ", ".join(rec.get('columns', []))
                            index_type = rec.get('index_type', 'btree')
                            
                            if index_type.lower() == 'btree':
                                sql = f"CREATE INDEX {index_name} ON {rec.get('table')} ({columns_str});"
                            else:
                                sql = f"CREATE INDEX {index_name} ON {rec.get('table')} USING {index_type} ({columns_str});"
                            
                            st.code(sql, language="sql")
                            st.text("Use CONCURRENTLY for production environments to avoid locking tables")
                else:
                    if recommendations and "error" in recommendations[0]:
                        st.error(recommendations[0]["error"])
                    else:
                        st.info("No index recommendations found for this query.")

if __name__ == "__main__":
    show()