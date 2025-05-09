from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class RecommendationType(str, Enum):
    """Types of recommendations that can be provided."""
    INDEX = "index"
    TABLE = "table"
    QUERY = "query"
    CONFIG = "config"

class RecommendationStatus(str, Enum):
    """Status of a recommendation."""
    PENDING = "pending"
    IMPLEMENTED = "implemented"
    DISMISSED = "dismissed"
    SCHEDULED = "scheduled"

class Recommendation(BaseModel):
    """Model for representing optimization recommendations."""
    recommendation_id: str
    type: RecommendationType
    title: str
    description: str
    impact_score: float  # 0-100 score indicating potential impact
    sql_script: Optional[str] = None
    status: RecommendationStatus = RecommendationStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    implemented_at: Optional[datetime] = None
    related_objects: Optional[List[str]] = None  # Tables, indexes, etc. affected
    estimated_improvement: Optional[str] = None  # Human-readable improvement estimate
    before_metrics: Optional[Dict[str, Any]] = None
    after_metrics: Optional[Dict[str, Any]] = None
    source_queries: Optional[List[str]] = None  # Query IDs that triggered this recommendation
    
    def dismiss(self):
        """Mark recommendation as dismissed."""
        self.status = RecommendationStatus.DISMISSED
        self.updated_at = datetime.now()
    
    def implement(self):
        """Mark recommendation as implemented."""
        self.status = RecommendationStatus.IMPLEMENTED
        self.updated_at = datetime.now()
        self.implemented_at = datetime.now()
    
    def schedule(self):
        """Mark recommendation as scheduled for implementation."""
        self.status = RecommendationStatus.SCHEDULED
        self.updated_at = datetime.now()