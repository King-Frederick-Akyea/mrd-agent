"""
Real-money gambling vertical module.
Demonstrates modularity - can be swapped for SaaS or other verticals.
"""

from typing import Dict, List, Optional
import asyncio
from datetime import datetime

from src.models.research import ResearchPlan, ResearchTask, TaskPriority
from src.models.mrd import MRDOutput, Claim, DataSource
from src.modules.base import BaseResearchModule

class GamblingResearchModule(BaseResearchModule):
    """Real-money skill gaming vertical"""
    
    def __init__(self):
        self.vertical = "real_money_gaming"
        self.region_specific_rules = {
            "EU": {"age_limit": 18, "license_required": True},
            "UK": {"age_limit": 18, "license_required": True, "gambling_commission": True},
            "US": {"state_by_state": True, "age_limit": 21}
        }
    
    async def create_research_plan(self, user_prompt: str) -> ResearchPlan:
        """Create research plan for gambling/gaming vertical"""
        
        # Parse user intent
        target_region = self._extract_region(user_prompt)
        target_demo = self._extract_demographic(user_prompt)
        
        # Define research tasks specific to gambling
        tasks = [
            ResearchTask(
                id="market_analysis_gambling",
                question="Why is Triumph succeeding where public companies (like Skillz) are failing?",
                required_tools=["search_sensor_tower", "analyze_app_store_reviews"],
                priority=TaskPriority.CRITICAL,
                vertical_specific={"metric_focus": ["arpu", "retention", "ltv"]}
            ),
            ResearchTask(
                id="audience_tiktok_analysis",
                question="How are they using TikTok/Influencers for user acquisition?",
                required_tools=["scrape_social_media", "analyze_sentiment"],
                priority=TaskPriority.HIGH,
                vertical_specific={"platforms": ["tiktok", "instagram", "youtube"]}
            ),
            ResearchTask(
                id="gap_analysis_io_games",
                question="What IO games exist that Triumph doesn't offer yet?",
                required_tools=["search_competitor_features", "analyze_trends"],
                priority=TaskPriority.MEDIUM
            ),
            ResearchTask(
                id="regulatory_check_eu_uk",
                question=f"Is this model legal in {target_region}?",
                required_tools=["check_regulatory_compliance", "legal_database"],
                priority=TaskPriority.CRITICAL,
                vertical_specific={"regions": [target_region]}
            ),
            ResearchTask(
                id="payment_processing",
                question="What payment processors support real-money gaming in target region?",
                required_tools=["search_payment_providers"],
                priority=TaskPriority.HIGH,
                vertical_specific={"region": target_region}
            )
        ]
        
        return ResearchPlan(
            id=f"gambling_{datetime.now().timestamp()}",
            original_prompt=user_prompt,
            vertical=self.vertical,
            target_region=target_region,
            target_demographic=target_demo,
            tasks=tasks
        )
    
    async def synthesize_mrd(self, research_data: Dict) -> Dict:
        """Synthesize gambling-specific MRD"""
        
        # This is where you'd use an LLM to structure the data
        # For this example, return structured mock data
        
        return {
            "original_prompt": research_data.get("original_prompt", ""),
            "vertical": self.vertical,
            "executive_summary": "Triumph succeeds through viral TikTok marketing and simplified gameplay, while Skillz struggles with high user acquisition costs.",
            "market_analysis": [
                {
                    "metric_name": "Market Size",
                    "value": "€15B",
                    "unit": "EUR",
                    "period": "2024",
                    "trend": "up",
                    "source": {
                        "source_type": "market_research",
                        "source_name": "Statista 2024",
                        "timestamp": datetime.now().isoformat(),
                        "confidence_score": 0.9
                    }
                }
            ],
            "competitor_analysis": [
                {
                    "name": "Skillz",
                    "strengths": [
                        {
                            "statement": "Publicly traded company with established infrastructure",
                            "data_sources": [{"source_type": "financial", "source_name": "SEC Filings", "timestamp": datetime.now().isoformat(), "confidence_score": 0.9}],
                            "category": "competitor"
                        }
                    ],
                    "weaknesses": [
                        {
                            "statement": "High user acquisition costs (>$50 per user)",
                            "data_sources": [{"source_type": "sensor_tower", "source_name": "Sensor Tower Q3 2024", "timestamp": datetime.now().isoformat(), "confidence_score": 0.8}],
                            "category": "competitor"
                        }
                    ],
                    "key_differentiators": ["B2B focus", "Tournament platform"],
                    "threat_level": "medium"
                }
            ],
            "feature_recommendations": [
                {
                    "name": "TikTok Live Integration",
                    "description": "Allow players to stream gameplay directly to TikTok",
                    "priority": "P0",
                    "estimated_impact": 0.85,
                    "development_effort": "m",
                    "market_gap_source": {
                        "statement": "No major skill gaming app has direct TikTok Live integration",
                        "data_sources": [{"source_type": "social_analysis", "source_name": "TikTok API", "timestamp": datetime.now().isoformat(), "confidence_score": 0.8}],
                        "category": "gap"
                    }
                }
            ],
            "swot_analysis": {
                "strengths": {"items": []},
                "weaknesses": {"items": []},
                "opportunities": {"items": []},
                "threats": {"items": []}
            },
            "all_claims": [],
            "regulatory_analysis": [],
            "target_audience": [],
            "data_sources_summary": {"market_research": 1},
            "confidence_score": 0.8
        }
    
    def get_required_tools(self) -> List[str]:
        return [
            "search_sensor_tower",
            "analyze_sentiment", 
            "check_regulatory_compliance",
            "scrape_social_media",
            "search_payment_providers"
        ]
    
    def _extract_region(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "eu" in prompt_lower or "europe" in prompt_lower:
            return "EU"
        elif "uk" in prompt_lower or "britain" in prompt_lower:
            return "UK"
        elif "us" in prompt_lower or "usa" in prompt_lower:
            return "US"
        return "EU"
    
    def _extract_demographic(self, prompt: str) -> Dict:
        return {
            "age_range": "18-35",
            "gender": "male",
            "interests": ["gaming", "social_competition"]
        }
