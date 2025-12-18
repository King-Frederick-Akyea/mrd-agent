# Architecture Overview

## System Architecture

The Autonomous MRD Agent uses a **state machine with validation gates** to ensure data quality at each step. Every claim in the final MRD is traceable to its data source.

## Core Components

### 1. Entry Point (`src/main.py`)
- `AutonomousProductAgent`: Main orchestrator
- Handles high-level workflow: Parse → Plan → Research → Synthesize → Validate
- Implements retry logic and human-in-the-loop validation points

### 2. Core Orchestration (`src/core/`)
- `agent.py`: `MRDAgent` - Executes research plans with state management
- `state_machine.py`: Defines valid state transitions
- `validator.py`: Human validation workflows

### 3. Data Models (`src/models/`)
- `mrd.py`: Complete MRD structure with Pydantic validation
- `research.py`: Research plans and tasks
- `validation.py`: Validation utilities

### 4. Vertical Modules (`src/modules/`)
- `base.py`: Abstract base class for all verticals
- `gambling.py`: Real-money gaming vertical implementation
- `saas.py`: Example SaaS vertical (demonstrates modularity)

### 5. Tools (`src/tools/`)
- Mock implementations of external tools:
  - `sensor_tower.py`: Market data
  - `sentiment.py`: Sentiment analysis
  - `regulatory.py`: Compliance checking

## Data Flow

```
User Prompt
    ↓
Research Plan Creation (Module-specific)
    ↓
Human Validation (Optional)
    ↓
Research Execution (Agent with retry logic)
    ↓
Data Synthesis (Module-specific)
    ↓
Pydantic Validation
    ↓
MRD Output
```

## State Machine

```
IDLE → RESEARCHING → VALIDATING → COMPLETED
  ↓         ↓            ↓
FAILED ← FAILED ← FAILED
```

## Key Design Patterns

1. **Validation First**: Every data point validated through Pydantic
2. **Source Tracking**: All claims include provenance metadata
3. **Modular Swapping**: Domain logic in pluggable modules
4. **Graceful Degradation**: System continues with partial data when possible
5. **Circuit Breaker**: Prevents cascade failures

