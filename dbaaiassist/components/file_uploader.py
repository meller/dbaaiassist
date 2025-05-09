import streamlit as st
from typing import List, Optional, IO, Any
import tempfile
import os

class FileUploader:
    """Component for handling file uploads."""
    
    def __init__(self, key: str = "file_uploader"):
        """
        Initialize the file uploader component.
        
        Args:
            key: Unique key for the Streamlit component
        """
        self.key = key
    
    def upload_log_files(self, title: str = "Upload PostgreSQL Log Files", 
                       help_text: str = "Upload one or more PostgreSQL log files for analysis") -> List[IO[Any]]:
        """
        Render a file uploader for PostgreSQL log files.
        
        Args:
            title: Title to display above the uploader
            help_text: Help text to display
            
        Returns:
            List of file objects for the uploaded files
        """
        st.subheader(title)
        st.markdown(help_text)
        
        files = st.file_uploader(
            "Select log files", 
            accept_multiple_files=True, 
            type=["log", "txt", "gz"],
            key=f"{self.key}_log_uploader"
        )
        
        if files:
            st.success(f"✅ {len(files)} file(s) uploaded")
            
            # Display file details
            file_details = []
            for file in files:
                size_kb = file.size / 1024
                size_text = f"{size_kb:.2f} KB" if size_kb < 1024 else f"{size_kb/1024:.2f} MB"
                file_details.append(f"- **{file.name}** ({size_text})")
            
            st.markdown("### Uploaded Files\n" + "\n".join(file_details))
        
        return files
    
    def show_sample_logs(self, files: List[IO[Any]], num_lines: int = 5) -> None:
        """
        Show a sample of the uploaded log files.
        
        Args:
            files: List of file objects
            num_lines: Number of lines to sample from each file
        """
        if not files:
            return
        
        with st.expander("🔍 Preview Log Content", expanded=False):
            for file in files:
                st.markdown(f"**{file.name}**")
                
                # Reset file pointer to start
                file.seek(0)
                
                # Read and display first few lines
                lines = []
                for _ in range(num_lines):
                    line = file.readline().decode('utf-8', errors='ignore')
                    if not line:
                        break
                    lines.append(line)
                
                st.code("".join(lines), language="text")
                
                # Reset file pointer for future use
                file.seek(0)