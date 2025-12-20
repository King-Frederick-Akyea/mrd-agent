"""
Pydantic models for MRD structure and validation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

# ========== CORE DATA MODELS ==========

class DataSource(BaseModel):
    """Tracks provenance of every claim"""
    source_type: str = Field(..., description="Tool or API used")
    source_name: str = Field(..., description="Specific source identifier")
    timestamp: datetime = Field(default_factory=datetime.now)
    confidence_score: float = Field(ge=0.0, le=1.0, default=1.0)
    raw_data: Optional[Dict] = Field(None, description="Original data for audit")
    
    @field_validator('confidence_score')
    @classmethod
    def validate_confidence(cls, v):
        if v < 0.5:
            raise ValueError("Low confidence data requires human review")
        return v

class Claim(BaseModel):
    """A single backed claim in the MRD"""
    statement: str = Field(..., description="The claim being made")
    data_sources: List[DataSource] = Field(..., description="Sources backing this claim")
    category: str = Field(..., description="market|audience|regulation|competitor")
    
    model_config = ConfigDict(validate_assignment=True)
    
    @field_validator('data_sources')
    @classmethod
    def must_have_source(cls, v):
        if not v:
            raise ValueError("Every claim must have at least one data source")
        return v

# ========== MARKET ANALYSIS ==========

class MarketMetric(BaseModel):
    metric_name: str
    value: Any
    unit: str
    period: str
    trend: Optional[str] = None
    source: DataSource

class CompetitorAnalysis(BaseModel):
    name: str
    market_share: Optional[MarketMetric] = None
    strengths: List[Claim]
    weaknesses: List[Claim]
    key_differentiators: List[str]
    threat_level: str = Field(..., pattern="^(low|medium|high|critical)$")
    
    @field_validator('threat_level')
    @classmethod
    def validate_threat(cls, v):
        allowed = {"low", "medium", "high", "critical"}
        if v not in allowed:
            raise ValueError(f"Threat level must be one of {allowed}")
        return v

# ========== SWOT ANALYSIS ==========

class SWOTCategory(BaseModel):
    items: List[Claim]
    
    def add_item(self, statement: str, source: DataSource):
        self.items.append(Claim(
            statement=statement,
            data_sources=[source],
            category="swot"
        ))

class SWOTAnalysis(BaseModel):
    strengths: SWOTCategory
    weaknesses: SWOTCategory
    opportunities: SWOTCategory
    threats: SWOTCategory
    
    def to_dict(self) -> Dict:
        return {
            "strengths": [item.statement for item in self.strengths.items],
            "weaknesses": [item.statement for item in self.weaknesses.items],
            "opportunities": [item.statement for item in self.opportunities.items],
            "threats": [item.statement for item in self.threats.items]
        }

# ========== FEATURE RECOMMENDATIONS ==========

class FeaturePriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

class FeatureRecommendation(BaseModel):
    name: str
    description: str
    priority: FeaturePriority
    estimated_impact: float = Field(ge=0.0, le=1.0)
    development_effort: str = Field(..., pattern="^(xs|s|m|l|xl)$")
    market_gap_source: Optional[Claim] = None
    competitor_reference: Optional[List[str]] = None
    
    @field_validator('estimated_impact')
    @classmethod
    def validate_impact(cls, v):
        if v > 0.8:
            # High impact features require multiple validation sources
            # This would be enforced in business logic
            pass
        return v

# ========== FINAL MRD STRUCTURE ==========

class MRDOutput(BaseModel):
    """
    Complete Market Requirements Document structure.
    
    Final output of the agent. All fields are validated by Pydantic.
    Can be serialized directly to JSON for database storage.
    """
    id: str = Field(default_factory=lambda: f"MRD_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    generated_at: datetime = Field(default_factory=datetime.now)
    original_prompt: str
    vertical: str
    executive_summary: str
    market_analysis: List[MarketMetric]
    competitor_analysis: List[CompetitorAnalysis]
    swot_analysis: SWOTAnalysis
    feature_recommendations: List[FeatureRecommendation]
    regulatory_analysis: List[Claim]
    target_audience: List[Claim]
    all_claims: List[Claim] = Field(..., description="All claims for audit trail")
    data_sources_summary: Dict[str, int] = Field(..., description="Count of claims by source type")
    confidence_score: float = Field(ge=0.0, le=1.0)
    processing_time_seconds: Optional[float] = None
    agent_version: str = "1.0.0"
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "MRD_20241215_143022",
                "original_prompt": "Build skill-based gambling app for Europe",
                "vertical": "real_money_gaming",
                "confidence_score": 0.85
            }
        }
    )
    
    @model_validator(mode='after')
    def calculate_confidence(self):
        """Calculate confidence based on data sources"""
        if self.all_claims:
            total_confidence = sum(
                source.confidence_score 
                for claim in self.all_claims 
                for source in claim.data_sources
            )
            total_sources = sum(len(claim.data_sources) for claim in self.all_claims)
            if total_sources > 0:
                self.confidence_score = total_confidence / total_sources
        return self

class ErrorMRD(BaseModel):
    error: str
    partial_data: Optional[Dict] = None
    completed_steps: List[str] = []
    failed_step: str
    recovery_suggestion: str
    timestamp: datetime = Field(default_factory=datetime.now)
