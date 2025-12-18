"""
Autonomous MRD Agent - Production Entry Point
"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass

from src.core.agent import MRDAgent
from src.models.mrd import MRDOutput, ErrorMRD
from src.modules.gambling import GamblingResearchModule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
	"""Configuration for the agent"""
	enable_human_validation: bool = True
	max_retries: int = 3
	timeout_seconds: int = 300
	llm_provider: str = "openai"  # Can be swapped

class AutonomousProductAgent:
	"""
	Main orchestrator for the autonomous MRD generation.
	
	This is the high-level interface that coordinates the entire MRD generation process.
	It handles the workflow: Parse → Plan → Research → Synthesize → Validate.
	
	Key Responsibilities:
	1. Parse user prompts into structured research plans (via vertical modules)
	2. Coordinate human-in-the-loop validation points
	3. Execute research with retry logic
	4. Synthesize research data into MRD structure
	5. Handle failures gracefully (return partial results when possible)
	
	Design Decisions:
	- Modular Vertical Support: Uses BaseResearchModule pattern, allowing easy swapping
	  of verticals (Gambling → SaaS → any domain)
	- Human-in-the-Loop: Explicit validation points before expensive operations
	- Graceful Degradation: Returns ErrorMRD (not exception) when things go wrong,
	  allowing downstream systems to handle partial results
	- Configuration-Driven: AgentConfig allows tuning retry logic, timeouts, etc.
	
	Example Usage:
	    agent = AutonomousProductAgent()
	    mrd = await agent.generate_mrd(
	        "Build skill-based gambling app for European market"
	    )
	"""
    
	def __init__(self, config: Optional[AgentConfig] = None):
		self.config = config or AgentConfig()
		self.agent = MRDAgent()
		self.current_module = GamblingResearchModule()
        
	async def generate_mrd(self, user_prompt: str) -> MRDOutput:
		"""
		Generate a complete Market Requirements Document from user prompt.
		
		This is the main entry point. It orchestrates the entire MRD generation process:
		
		1. Parse & Plan: User prompt → ResearchPlan (via vertical module)
		2. Human Validation: Optional approval of research plan (if enabled)
		3. Execute Research: Run all research tasks with retry logic
		4. Synthesize: Transform research data into MRD structure
		5. Validate: Ensure MRD meets quality standards
		
		Error Handling:
		- If a critical step fails, returns ErrorMRD (not exception)
		- ErrorMRD includes partial data and recovery suggestions
		- Allows downstream systems to handle partial results gracefully
		
		Args:
			user_prompt: Natural language request (e.g., "Build skill-based gambling app")
			
		Returns:
			MRDOutput: Structured, validated MRD (or ErrorMRD if generation failed)
			
		Design Note:
			We return ErrorMRD instead of raising exceptions because:
			- Partial MRDs are better than no MRDs
			- Downstream systems can decide how to handle errors
			- Allows for graceful degradation in production
		"""
		logger.info(f"Starting MRD generation for: {user_prompt}")
        
		try:
			# Step 1: Parse user prompt into structured research plan
			# This is vertical-specific: Gambling module creates different tasks than SaaS module
			# The module knows what research is needed for its domain
			research_plan = await self.current_module.create_research_plan(user_prompt)
            
			# Step 2: Human validation point (if enabled)
			# Rationale: Research plans can trigger expensive API calls
			# Human approval prevents wasted resources and ensures plan makes sense
			if self.config.enable_human_validation:
				if not await self._validate_with_human(research_plan):
					raise ValueError("Research plan rejected by human validator")
            
			# Step 3: Execute research tasks with retry logic
			# The agent orchestrates tool calls, handles failures, tracks state
			# Returns dictionary of task_id -> result
			research_data = await self._execute_research_with_retries(research_plan)
            
			# Step 4: Synthesize research data into MRD structure
			# This is where vertical-specific logic transforms raw research into strategic document
			# Module knows how to structure data for its domain (gambling vs SaaS)
			mrd_draft = await self.current_module.synthesize_mrd({**research_data, "original_prompt": research_plan.original_prompt})
            
			# Step 5: Final validation (Pydantic + business rules)
			# Ensures MRD structure is correct and meets quality standards
			# This is the last gate before returning to user
			validated_mrd = await self.agent.validate_and_finalize(mrd_draft)
            
			logger.info("MRD generation completed successfully")
			return validated_mrd
            
		except Exception as e:
			# Error handling: Don't crash, return partial results
			# Rationale: Partial MRDs are better than no MRDs
			# Downstream systems can decide how to handle errors
			logger.error(f"MRD generation failed: {e}")
			return await self._handle_failure(e)
    
	async def _execute_research_with_retries(self, research_plan):
		"""Execute research with exponential backoff retry logic"""
		for attempt in range(self.config.max_retries):
			try:
				return await self.agent.execute_research(research_plan)
			except Exception as e:
				if attempt == self.config.max_retries - 1:
					raise
				wait_time = 2 ** attempt  # Exponential backoff
				logger.warning(f"Research attempt {attempt + 1} failed, retrying in {wait_time}s")
				await asyncio.sleep(wait_time)
    
	async def _validate_with_human(self, research_plan) -> bool:
		"""Human-in-the-loop validation point"""
		# In production, this would call a human approval workflow
		logger.info("Research plan ready for human validation")
		# For demo, auto-approve
		return True
    
	async def _handle_failure(self, error: Exception):
		"""Graceful degradation - return partial results with error context"""
		# Log detailed error
		logger.error(f"Partial failure handled: {error}")
        
		# Return error structure that can still be processed
		return ErrorMRD(
			error=str(error),
			partial_data=self.agent.get_partial_results(),
			completed_steps=[],
			failed_step=str(error),
			recovery_suggestion="Try refining the research query or check tool availability"
		)

def main():
	"""CLI entry point"""
	import argparse
    
	parser = argparse.ArgumentParser(description="Generate MRD from business intent")
	parser.add_argument("prompt", help="Business intent prompt")
	parser.add_argument("--output", "-o", help="Output file (JSON)", default="mrd_output.json")
    
	args = parser.parse_args()
    
	# Initialize and run
	agent = AutonomousProductAgent()
    
	# For demo, run synchronously
	import asyncio
	result = asyncio.run(agent.generate_mrd(args.prompt))
    
	# Save output
	try:
		with open(args.output, 'w', encoding='utf-8') as f:
			f.write(result.model_dump_json(indent=2))
	except Exception:
		# If partial ErrorMRD returned, write as plain dict
		import json
		with open(args.output, 'w', encoding='utf-8') as f:
			f.write(json.dumps(result.model_dump() if hasattr(result, 'model_dump') else dict(result), indent=2))
    
	print(f"✅ MRD saved to {args.output}")
	try:
		print(f"📊 Contains: {len(result.competitor_analysis)} competitors, {len(result.feature_recommendations)} features")
	except Exception:
		pass

if __name__ == "__main__":
	main()
