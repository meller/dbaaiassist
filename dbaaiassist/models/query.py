from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class Query(BaseModel):
    """Model for representing a SQL query extracted from logs."""
    query_text: str
    execution_time_ms: float
    timestamp: Optional[datetime] = None
    normalized_query: Optional[str] = None
    tables_accessed: Optional[List[str]] = None
    frequency: int = 1
    database_name: Optional[str] = None
    username: Optional[str] = None
    client_ip: Optional[str] = None
    query_id: Optional[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        # Generate a simple hash as query_id if not provided
        if self.query_id is None:
            import hashlib
            self.query_id = hashlib.md5(self.query_text.encode()).hexdigest()[:10]