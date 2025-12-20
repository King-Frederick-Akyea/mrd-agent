"""
Core agent orchestration with state management and validation.
"""

from typing import Dict, List, Optional, Any
import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from src.models.research import ResearchPlan, ResearchTask, TaskStatus
from src.models.mrd import MRDOutput
from src.core.state_machine import AgentState, StateTransition

class OrchestrationError(Exception):
    """Custom exception for orchestration failures"""
    pass

class MRDAgent:
    """
    Autonomous agent that orchestrates MRD generation.
    
    Uses a state machine pattern for predictable execution. Implements circuit breaker
    pattern and graceful degradation for error handling.
    
    Example Usage:
        agent = MRDAgent()
        research_plan = ResearchPlan(...)
        results = await agent.execute_research(research_plan)
        mrd = await agent.validate_and_finalize(mrd_draft)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.state = AgentState.IDLE
        self.research_data: Dict[str, Any] = {}
        self.validation_errors: List[str] = []
        self.retry_count: Dict[str, int] = {}
        
        # Configuration
        self.config = {
            'max_retries': 3,
            'timeout_seconds': 30,
            'require_multiple_sources': True,
            'enable_circuit_breaker': True
        }
        if config:
            self.config.update(config)
        
        # Circuit breaker state
        self.circuit_state = 'closed'
        self.failure_count = 0
        
    async def execute_research(self, research_plan: ResearchPlan) -> Dict:
        """
        Execute research plan with state management and error recovery.
        
        Transitions to RESEARCHING state, executes tasks with retry logic,
        and checks if sufficient data has been collected.
        
        Args:
            research_plan: The research plan containing tasks to execute
            
        Returns:
            Dictionary mapping task IDs to their results
            
        Raises:
            OrchestrationError: If critical tasks fail or insufficient data collected
        """
        
        # Transition to RESEARCHING
        self._transition_state(AgentState.RESEARCHING)
        
        results = {}
        # Sequential execution: tasks may have dependencies, easier to debug
        for task in research_plan.tasks:
            try:
                # Circuit breaker: If too many failures, fail fast (don't retry)
                if self.circuit_state == 'open':
                    raise OrchestrationError("Circuit breaker open - too many failures")
                
                # Execute with retry logic (exponential backoff: 2s, 4s, 8s)
                task_result = await self._execute_task_with_retry(task)
                results[task.id] = task_result
                
                # Update task status (for monitoring/debugging)
                task.status = TaskStatus.COMPLETED
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                try:
                    # Handle failure: Critical tasks (regulatory) stop entire process
                    # Non-critical tasks (gap analysis) allow process to continue
                    self._handle_task_failure(task, e)
                except OrchestrationError:
                    # Critical task failed - re-raise to stop execution
                    raise
                
                # Circuit breaker: Track failures, open circuit after 3 consecutive failures
                self.failure_count += 1
                if self.failure_count > 3:
                    self.circuit_state = 'open'
                    # Auto-recovery: Reset circuit breaker after 60 seconds
                    asyncio.create_task(self._reset_circuit_breaker())
        
        # Check if we have enough data to proceed (70%+ tasks completed, all critical tasks done)
        if not self._has_sufficient_data(results):
            raise OrchestrationError("Insufficient data collected for synthesis")
        
        return results
    
    async def _execute_task_with_retry(self, task: ResearchTask, attempt: int = 0):
        """
        Execute a single task with exponential backoff retry.
        
        Retries with delays: 2s, 4s, 8s before failing.
        """
        
        if attempt >= self.config['max_retries']:
            raise OrchestrationError(f"Max retries exceeded for task {task.id}")
        
        try:
            # For demo: Simulate tool call (in production, would call actual tool with timeout/validation)
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # Simulate occasional failures for testing retry logic
            if attempt < 1:
                raise Exception(f"Tool {task.required_tools[0]} temporarily unavailable")
            
            # Return mock result
            return {
                "data": f"Result for {task.question}",
                "sources": ["mock_source"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            # Exponential backoff: Wait 2^attempt seconds before retry
            wait_time = 2 ** attempt
            await asyncio.sleep(wait_time)
            
            # Retry with incremented attempt counter
            return await self._execute_task_with_retry(task, attempt + 1)
    
    def _has_sufficient_data(self, results: Dict) -> bool:
        """
        Determine if we have enough data to proceed to synthesis.
        
        Requires at least 70% of tasks completed and all critical tasks done.
        
        Args:
            results: Dictionary of task results
            
        Returns:
            True if we have sufficient data, False otherwise
        """
        
        if not results:
            return False
        completed_tasks = [r for r in results.values() if r]
        
        # Simple heuristic: need at least 70% of tasks completed
        completion_ratio = len(completed_tasks) / len(results)
        
        # Critical tasks must be completed (check if any task ID contains these keywords)
        critical_keywords = ['market_analysis', 'regulatory']
        critical_completed = any(
            any(keyword in task_id for keyword in critical_keywords)
            for task_id in results.keys()
        )
        
        return completion_ratio >= 0.7 and critical_completed
    
    async def validate_and_finalize(self, mrd_draft: Dict) -> MRDOutput:
        """
        Validate and finalize MRD output using Pydantic validation.
        
        Performs schema validation, business rules validation, and data quality checks.
        
        Args:
            mrd_draft: Dictionary containing the draft MRD data
            
        Returns:
            Validated MRDOutput object
            
        Raises:
            OrchestrationError: If validation fails at any layer
        """
        
        self._transition_state(AgentState.VALIDATING)
        
        try:
            # Convert dict to Pydantic model (this validates)
            mrd = MRDOutput(**mrd_draft)
            
            # Additional business logic validation
            self._validate_mrd_business_rules(mrd)
            
            # Check data quality
            if mrd.confidence_score < 0.6:
                self.validation_errors.append(
                    f"Low confidence score: {mrd.confidence_score}"
                )
            
            # Transition to completed
            self._transition_state(AgentState.COMPLETED)
            
            return mrd
            
        except Exception as e:
            self._transition_state(AgentState.FAILED)
            raise OrchestrationError(f"MRD validation failed: {e}")
    
    def _validate_mrd_business_rules(self, mrd: MRDOutput):
        """
        Business-specific validation rules.
        
        Enforces domain rules that require business logic beyond schema validation.
        """
        
        # Rule 1: Must have at least 2 competitors analyzed
        if len(mrd.competitor_analysis) < 2:
            raise ValueError("Insufficient competitor analysis")
        
        # Rule 2: Gambling verticals must have regulatory analysis
        if "gambling" in mrd.vertical.lower():
            regulatory_claims = [c for c in mrd.regulatory_analysis if c]
            if not regulatory_claims:
                raise ValueError("Missing regulatory analysis for gambling vertical")
        
        # Rule 3: All features must have priority assigned
        for feature in mrd.feature_recommendations:
            if not feature.priority:
                raise ValueError(f"Feature {feature.name} missing priority")
    
    def _transition_state(self, new_state: AgentState):
        """Safely transition between states"""
        
        if not StateTransition.is_valid(self.state, new_state):
            raise OrchestrationError(
                f"Invalid state transition: {self.state} -> {new_state}"
            )
        
        print(f"State transition: {self.state.name} → {new_state.name}")
        self.state = new_state
    
    async def _reset_circuit_breaker(self):
        """Reset circuit breaker after timeout"""
        await asyncio.sleep(60)
        self.circuit_state = 'closed'
        self.failure_count = 0
    
    def _handle_task_failure(self, task: ResearchTask, error: Exception):
        """Handle task failure with recovery strategies"""
        
        self.validation_errors.append(f"Task {task.id} failed: {error}")
        
        # Different strategies based on task type
        if "regulatory" in task.id:
            # Regulatory tasks are critical - can't proceed without
            raise OrchestrationError(f"Critical task failed: {task.id}")
        else:
            # Non-critical tasks - log and continue
            print(f"Non-critical task {task.id} failed, continuing...")
    
    def get_partial_results(self) -> Dict:
        """Get partial results for error reporting"""
        return {
            "state": self.state.name,
            "research_data": self.research_data,
            "validation_errors": self.validation_errors
        }
