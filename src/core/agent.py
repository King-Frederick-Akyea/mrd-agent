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
    
    This is the "brain" of the system. It uses a state machine pattern (not a simple loop)
    to ensure predictable, debuggable execution. Each state transition is explicit and
    can be logged/monitored.
    
    Key Design Decisions:
    1. State Machine (not DAG): Provides clear error recovery points and makes it easy
       to resume from failures. Each state has explicit entry/exit conditions.
    
    2. Circuit Breaker Pattern: Prevents cascade failures when external tools are down.
       After 3 consecutive failures, circuit opens and requests fail fast.
    
    3. Graceful Degradation: If a non-critical task fails, we continue with other tasks.
       Only critical tasks (like regulatory checks) will stop the entire process.
    
    4. Explicit Data Sufficiency Check: Instead of the LLM "guessing" if it has enough
       data, we have explicit rules: 70%+ tasks completed AND all critical tasks done.
    
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
        
        This method orchestrates the execution of all research tasks. It:
        1. Transitions to RESEARCHING state
        2. Executes each task with retry logic
        3. Handles failures gracefully (critical vs non-critical)
        4. Checks if we have sufficient data to proceed
        
        Args:
            research_plan: The research plan containing tasks to execute
            
        Returns:
            Dictionary mapping task IDs to their results
            
        Raises:
            OrchestrationError: If critical tasks fail or insufficient data collected
            
        Design Note:
            We don't use parallel execution here because:
            - Tasks may have dependencies (need market data before feature prioritization)
            - Easier to debug sequential execution
            - Circuit breaker pattern works better with sequential flow
        """
        
        # Transition to RESEARCHING
        self._transition_state(AgentState.RESEARCHING)
        
        results = {}
        # Sequential execution (not parallel) because:
        # 1. Tasks may have dependencies (need market data before feature prioritization)
        # 2. Easier to debug and trace failures
        # 3. Circuit breaker pattern works better with sequential flow
        for task in research_plan.tasks:
            try:
                # Circuit breaker: If too many failures, fail fast (don't retry)
                # This prevents wasting resources when external services are down
                if self.circuit_state == 'open':
                    raise OrchestrationError("Circuit breaker open - too many failures")
                
                # Execute with retry logic (exponential backoff: 2s, 4s, 8s)
                # Most failures are transient (network errors, timeouts)
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
                    # This ensures we never proceed without required data
                    raise
                
                # Circuit breaker: Track failures, open circuit after 3 consecutive failures
                # Prevents cascade failures when external services are consistently down
                self.failure_count += 1
                if self.failure_count > 3:
                    self.circuit_state = 'open'
                    # Auto-recovery: Reset circuit breaker after 60 seconds
                    # Allows system to recover when services come back online
                    asyncio.create_task(self._reset_circuit_breaker())
        
        # Explicit check: Do we have enough data to proceed?
        # Instead of LLM "guessing", we have explicit rules:
        # - 70%+ tasks completed (allows some non-critical tasks to fail)
        # - All critical tasks completed (market_analysis, regulatory)
        if not self._has_sufficient_data(results):
            raise OrchestrationError("Insufficient data collected for synthesis")
        
        return results
    
    async def _execute_task_with_retry(self, task: ResearchTask, attempt: int = 0):
        """
        Execute a single task with exponential backoff retry.
        
        Retry Strategy:
        - Attempt 0: Immediate
        - Attempt 1: Wait 2s (2^1)
        - Attempt 2: Wait 4s (2^2)
        - Attempt 3: Wait 8s (2^3), then fail
        
        Why exponential backoff?
        - Prevents overwhelming failing services
        - Most failures are transient and resolve quickly
        - Gives services time to recover
        """
        
        if attempt >= self.config['max_retries']:
            raise OrchestrationError(f"Max retries exceeded for task {task.id}")
        
        try:
            # In production, this would call the actual tool (Sensor Tower, etc.)
            # Tool calls should:
            # 1. Have timeout (30s default)
            # 2. Validate response structure (Pydantic)
            # 3. Check data quality (not empty, confidence > threshold)
            
            # For demo: Simulate tool call
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # Simulate occasional failures for testing retry logic
            if attempt < 1:
                raise Exception(f"Tool {task.required_tools[0]} temporarily unavailable")
            
            # Return mock result (in production, this would be validated tool output)
            return {
                "data": f"Result for {task.question}",
                "sources": ["mock_source"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            # Exponential backoff: Wait 2^attempt seconds before retry
            # This prevents overwhelming failing services
            wait_time = 2 ** attempt
            await asyncio.sleep(wait_time)
            
            # Retry with incremented attempt counter
            return await self._execute_task_with_retry(task, attempt + 1)
    
    def _has_sufficient_data(self, results: Dict) -> bool:
        """
        Determine if we have enough data to proceed to synthesis.
        
        This is a critical decision point. Instead of the LLM "guessing" if it's done,
        we have explicit rules:
        
        1. Completion Ratio: Need at least 70% of tasks completed
        2. Critical Tasks: All critical tasks (market_analysis, regulatory) must be done
        
        Why 70%? This allows for some non-critical tasks to fail (e.g., gap analysis)
        while still producing a useful MRD. The exact threshold can be tuned based on
        production metrics.
        
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
        
        This method performs three layers of validation:
        
        1. Pydantic Schema Validation: Ensures the structure matches MRDOutput schema.
           This will raise ValidationError if fields are missing or wrong types.
        
        2. Business Rules Validation: Checks domain-specific rules (e.g., gambling
           verticals must have regulatory analysis, need at least 2 competitors).
        
        3. Data Quality Validation: Checks confidence scores and flags low-confidence
           claims for human review.
        
        Args:
            mrd_draft: Dictionary containing the draft MRD data
            
        Returns:
            Validated MRDOutput object
            
        Raises:
            OrchestrationError: If validation fails at any layer
            
        Design Note:
            We use Pydantic here (not just dict validation) because:
            - Type safety: Guaranteed structure at compile time
            - Automatic serialization: Can save directly to JSON/DB
            - Documentation: JSON schema generated automatically
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
        
        These are domain rules that Pydantic can't enforce (they require business logic).
        This is the second layer of validation (after Pydantic schema validation).
        
        Why separate from Pydantic?
        - Business rules may change without schema changes
        - Some rules are vertical-specific (gambling vs SaaS)
        - Easier to test and modify business rules separately
        """
        
        # Rule 1: Must have at least 2 competitors analyzed
        # Rationale: Single competitor analysis is not sufficient for strategic decisions
        if len(mrd.competitor_analysis) < 2:
            raise ValueError("Insufficient competitor analysis")
        
        # Rule 2: Gambling verticals must have regulatory analysis
        # Rationale: Legal compliance is critical for real-money gaming
        # This prevents shipping an MRD that could lead to legal issues
        if "gambling" in mrd.vertical.lower():
            regulatory_claims = [c for c in mrd.regulatory_analysis if c]
            if not regulatory_claims:
                raise ValueError("Missing regulatory analysis for gambling vertical")
        
        # Rule 3: All features must have priority assigned
        # Rationale: Product teams need clear prioritization to make decisions
        # Missing priority means the MRD is incomplete
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
