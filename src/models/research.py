from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ResearchTask(BaseModel):
    id: str
    question: str
    required_tools: List[str]
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    vertical_specific: Optional[Dict[str, Any]] = None

class ResearchPlan(BaseModel):
    id: str
    original_prompt: str
    vertical: str
    target_region: str
    target_demographic: Optional[Dict[str, Any]] = None
    tasks: List[ResearchTask] = []
