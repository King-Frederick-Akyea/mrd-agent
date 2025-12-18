from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseResearchModule(ABC):
    """Base class for all vertical modules"""
    
    @abstractmethod
    async def create_research_plan(self, user_prompt: str):
        pass
    
    @abstractmethod
    async def synthesize_mrd(self, research_data: Dict[str, Any]):
        pass
    
    @abstractmethod
    def get_required_tools(self) -> List[str]:
        pass
