import streamlit as st
from typing import Optional, Dict, Any, List
import json
import os
import traceback
from dbaaiassist.models.database import DatabaseConnection
from dbaaiassist.data.connectors.postgres import PostgreSQLConnector
from dbaaiassist.utils.logger import app_logger, log_exception

class ConnectionManager:
    """Component for managing database connections."""
    
    def __init__(self, key: str = "connection_manager"):
        """
        Initialize the connection manager component.
        
        Args:
            key: Unique key for the Streamlit component
        """
        self.key = key
        app_logger.info(f"Initializing ConnectionManager with key: {key}")
        self.connections = self._load_saved_connections()
        self.current_connection = None
        self.connector = None
        app_logger.debug(f"Loaded {len(self.connections)} saved connections")
    
    @log_exception
    def render_connection_form(self) -> Optional[DatabaseConnection]:
        """
        Render a form for creating or editing a database connection.
        
        Returns:
            DatabaseConnection object if form is submitted, None otherwise
        """
        app_logger.debug("Rendering connection form")
        st.subheader("Database Connection")
        
        with st.form(key=f"{self.key}_connection_form"):
            connection_name = st.text_input("Connection Name", key=f"{self.key}_name")
            host = st.text_input("Host", key=f"{self.key}_host")
            
            col1, col2 = st.columns(2)
            with col1:
                port = st.number_input("Port", min_value=1, max_value=65535, value=5432, key=f"{self.key}_port")
            with col2:
                database = st.text_input("Database Name", key=f"{self.key}_database")
            
            col1, col2 = st.columns(2)
            with col1:
                username = st.text_input("Username", key=f"{self.key}_username")
            with col2:
                password = st.text_input("Password", type="password", key=f"{self.key}_password")
            
            use_ssl = st.checkbox("Use SSL", key=f"{self.key}_ssl")
            
            col1, col2 = st.columns(2)
            with col1:
                save = st.checkbox("Save connection", value=True, key=f"{self.key}_save")
            with col2:
                test = st.checkbox("Test connection before saving", value=True, key=f"{self.key}_test")
            
            submitted = st.form_submit_button("Connect")
            
            if submitted:
                app_logger.info(f"Connection form submitted: {connection_name}")
                if not connection_name or not host or not database or not username or not password:
                    app_logger.warning("Form validation failed: missing required fields")
                    st.error("Please fill in all required fields.")
                    return None
                
                app_logger.info(f"Creating connection object: {connection_name}, host={host}, port={port}, db={database}")
                connection = DatabaseConnection(
                    name=connection_name,
                    host=host,
                    port=port,
                    database=database,
                    username=username,
                    password="******",  # Log masked password
                    use_ssl=use_ssl
                )
                
                # Create actual connection with real password
                real_connection = DatabaseConnection(
                    name=connection_name,
                    host=host,
                    port=port,
                    database=database,
                    username=username,
                    password=password,
                    use_ssl=use_ssl
                )
                
                if test:
                    app_logger.info(f"Testing connection: {connection_name}")
                    with st.spinner("Testing connection..."):
                        success = self._test_connection(real_connection)
                        if not success:
                            app_logger.error(f"Connection test failed: {connection_name}")
                            st.error("Failed to connect to the database. Please check your connection details.")
                            return None
                        app_logger.info(f"Connection test successful: {connection_name}")
                        st.success("Connection successful!")
                
                if save:
                    app_logger.info(f"Saving connection: {connection_name}")
                    self._save_connection(real_connection)
                    st.success(f"Connection '{connection_name}' saved.")
                
                app_logger.info(f"Returning new connection: {connection_name}")
                return real_connection
                
        app_logger.debug("Connection form rendered, no submission")
        return None
    
    @log_exception
    def render_connection_selector(self) -> Optional[DatabaseConnection]:
        """
        Render a selector for choosing from saved connections.
        
        Returns:
            Selected DatabaseConnection or None if no selection
        """
        app_logger.debug("Rendering connection selector")
        if not self.connections:
            app_logger.info("No saved connections available")
            st.info("No saved connections. Create a new connection to get started.")
            return None
        
        st.subheader("Saved Connections")
        app_logger.debug(f"Available connections: {list(self.connections.keys())}")
        
        connection_names = list(self.connections.keys())
        selected_name = st.selectbox(
            "Select a connection", 
            options=connection_names,
            key=f"{self.key}_saved_selector"
        )
        app_logger.debug(f"Selected connection: {selected_name}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            connect = st.button("Connect", key=f"{self.key}_connect_btn")
            app_logger.debug(f"Connect button clicked: {connect}")
        with col2:
            test = st.button("Test", key=f"{self.key}_test_btn")
            app_logger.debug(f"Test button clicked: {test}")
        with col3:
            delete = st.button("Delete", key=f"{self.key}_delete_btn")
            app_logger.debug(f"Delete button clicked: {delete}")
        
        if not selected_name:
            app_logger.info("No connection selected")
            return None
        
        selected_connection = self.connections.get(selected_name)
        app_logger.debug(f"Retrieved connection details for: {selected_name}")
        
        if test:
            app_logger.info(f"Testing connection: {selected_name}")
            with st.spinner(f"Testing connection to {selected_name}..."):
                success = self._test_connection(selected_connection)
                if success:
                    app_logger.info(f"Connection test successful: {selected_name}")
                    st.success("Connection successful!")
                else:
                    app_logger.error(f"Connection test failed: {selected_name}")
                    st.error("Connection failed. Please check your connection details.")
        
        if delete:
            app_logger.info(f"Deleting connection: {selected_name}")
            if st.session_state.get(f"{self.key}_current_connection") == selected_name:
                app_logger.info(f"Removing current connection reference: {selected_name}")
                st.session_state[f"{self.key}_current_connection"] = None
                self.current_connection = None
                self.connector = None
            
            del self.connections[selected_name]
            self._save_connections_to_session()
            st.success(f"Connection '{selected_name}' deleted.")
            st.rerun()
        
        if connect:
            app_logger.info(f"Connecting to: {selected_name}")
            with st.spinner(f"Connecting to {selected_name}..."):
                try:
                    app_logger.debug(f"Attempting connection to: {selected_name}")
                    success = self._connect(selected_connection)
                    app_logger.debug(f"Connection attempt result: {success}")
                    
                    if success:
                        app_logger.info(f"Successfully connected to: {selected_name}")
                        st.session_state[f"{self.key}_current_connection"] = selected_name
                        self.current_connection = selected_connection
                        st.success(f"Connected to {selected_name}")
                        return selected_connection
                    else:
                        app_logger.error(f"Failed to connect to: {selected_name}")
                        st.error("Failed to connect. Please check your connection details.")
                except Exception as e:
                    app_logger.exception(f"Exception during connection: {str(e)}")
                    st.error(f"Connection error: {str(e)}")
        
        # Check if we already have an active connection
        current_conn_name = st.session_state.get(f"{self.key}_current_connection")
        app_logger.debug(f"Current connection in session state: {current_conn_name}")
        
        if current_conn_name == selected_name:
            app_logger.info(f"Already connected to: {selected_name}")
            st.success(f"Currently connected to {selected_name}")
            self.current_connection = selected_connection
            return selected_connection
        
        app_logger.debug("Connection selector rendered, no connection made")
        return None
    
    @log_exception
    def render_connection_status(self) -> None:
        """Render the current connection status."""
        app_logger.debug("Rendering connection status")
        
        current_name = st.session_state.get(f"{self.key}_current_connection")
        app_logger.debug(f"Current connection name: {current_name}")
        
        if not self.current_connection and current_name and current_name in self.connections:
            app_logger.info(f"Reconnecting to saved connection: {current_name}")
            self.current_connection = self.connections[current_name]
            try:
                self._connect(self.current_connection)
            except Exception as e:
                app_logger.exception(f"Error reconnecting: {str(e)}")
        
        if self.current_connection:
            app_logger.debug(f"Showing connection status for: {self.current_connection.name}")
            st.sidebar.success(f"Connected to: {self.current_connection.name}")
            
            # Show connection details
            with st.sidebar.expander("Connection Details"):
                st.write(f"**Host**: {self.current_connection.host}")
                st.write(f"**Port**: {self.current_connection.port}")
                st.write(f"**Database**: {self.current_connection.database}")
                st.write(f"**User**: {self.current_connection.username}")
            
            if st.sidebar.button("Disconnect", key=f"{self.key}_disconnect_btn"):
                app_logger.info(f"Disconnecting from: {self.current_connection.name}")
                self._disconnect()
                st.session_state[f"{self.key}_current_connection"] = None
                st.rerun()
        else:
            app_logger.debug("No active connection")
            st.sidebar.warning("Not connected to any database")
    
    def get_current_connector(self) -> Optional[PostgreSQLConnector]:
        """Get the current database connector."""
        if self.connector and self.connector.is_connected():
            app_logger.debug(f"Returning active connector: {self.current_connection.name if self.current_connection else 'Unknown'}")
            return self.connector
        app_logger.debug("No active connector available")
        return None
    
    @log_exception
    def _connect(self, connection: DatabaseConnection) -> bool:
        """
        Connect to a database.
        
        Args:
            connection: Database connection details
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            app_logger.info(f"Creating connector for: {connection.name}, {connection.host}:{connection.port}/{connection.database}")
            self.connector = PostgreSQLConnector(connection)
            app_logger.debug("Attempting connection...")
            success = self.connector.connect()
            app_logger.info(f"Connection result: {success}")
            
            if success:
                self.current_connection = connection
                app_logger.info(f"Successfully connected to: {connection.name}")
            else:
                app_logger.warning(f"Failed to connect to: {connection.name}")
            
            return success
        except Exception as e:
            app_logger.exception(f"Connection error: {str(e)}")
            st.error(f"Error connecting to database: {str(e)}")
            return False
    
    @log_exception
    def _disconnect(self) -> None:
        """Disconnect from the current database."""
        if self.connector:
            app_logger.info("Disconnecting from database")
            try:
                self.connector.disconnect()
                app_logger.info("Successfully disconnected")
            except Exception as e:
                app_logger.exception(f"Error during disconnect: {str(e)}")
        else:
            app_logger.debug("No active connector to disconnect")
            
        self.connector = None
        self.current_connection = None
    
    @log_exception
    def _test_connection(self, connection: DatabaseConnection) -> bool:
        """
        Test a database connection.
        
        Args:
            connection: Database connection details
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            app_logger.info(f"Testing connection to: {connection.name}, {connection.host}:{connection.port}/{connection.database}")
            connector = PostgreSQLConnector(connection)
            success = connector.connect()
            app_logger.info(f"Test connection result: {success}")
            
            if success:
                app_logger.debug("Disconnecting test connection")
                connector.disconnect()
                
            return success
        except Exception as e:
            app_logger.exception(f"Test connection error: {str(e)}")
            return False
    
    @log_exception
    def _save_connection(self, connection: DatabaseConnection) -> None:
        """
        Save a connection to the session state.
        
        Args:
            connection: Database connection to save
        """
        app_logger.info(f"Saving connection: {connection.name}")
        self.connections[connection.name] = connection
        self._save_connections_to_session()
        app_logger.debug(f"Connection saved: {connection.name}")
    
    @log_exception
    def _save_connections_to_session(self) -> None:
        """Save all connections to session state."""
        app_logger.debug(f"Saving {len(self.connections)} connections to session state")
        # Convert connection objects to dictionaries for storage
        connections_dict = {
            name: conn.dict(exclude={"id"}) for name, conn in self.connections.items()
        }
        st.session_state[f"{self.key}_saved_connections"] = connections_dict
        app_logger.debug("Connections saved to session state")
    
    @log_exception
    def _load_saved_connections(self) -> Dict[str, DatabaseConnection]:
        """
        Load saved connections from session state.
        
        Returns:
            Dictionary of connection name to DatabaseConnection object
        """
        app_logger.debug("Loading saved connections from session state")
        connections_dict = st.session_state.get(f"{self.key}_saved_connections", {})
        connections = {
            name: DatabaseConnection(**conn_dict) 
            for name, conn_dict in connections_dict.items()
        }
        app_logger.debug(f"Loaded {len(connections)} saved connections")
        return connections