from enum import Enum

class AgentState(Enum):
    IDLE = 0
    RESEARCHING = 1
    VALIDATING = 2
    COMPLETED = 3
    FAILED = 4

class StateTransition:
    """Simple state transition validator"""

    _allowed = {
        AgentState.IDLE: {AgentState.RESEARCHING, AgentState.FAILED},
        AgentState.RESEARCHING: {AgentState.VALIDATING, AgentState.FAILED},
        AgentState.VALIDATING: {AgentState.COMPLETED, AgentState.FAILED},
        AgentState.COMPLETED: {AgentState.IDLE},
        AgentState.FAILED: {AgentState.IDLE}
    }

    @staticmethod
    def is_valid(from_state: AgentState, to_state: AgentState) -> bool:
        return to_state in StateTransition._allowed.get(from_state, set())
