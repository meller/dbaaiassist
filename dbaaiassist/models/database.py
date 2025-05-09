from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class DatabaseConnection(BaseModel):
    """Model for database connection information."""
    name: str
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    use_ssl: bool = False
    id: Optional[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            # Generate a simple ID based on the connection details
            self.id = f"{self.name}_{self.host}_{self.database}"