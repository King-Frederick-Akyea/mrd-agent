# Autonomous Product Strategy Agent

## 🎯 Problem Statement

**The Challenge**: Build an autonomous agent that transforms high-level business intents into rigorous, data-backed Market Requirements Documents (MRDs). Unlike generic "idea generators," this system must act as a technical Product Manager, producing structured strategic documents where every claim is traceable to its source.

**The Goal**: Move from "vibe coding" (generic results, frequent hallucinations) to "structured agentic reasoning" (validated, source-backed analysis).

---

## 🏗️ Architecture Overview

This system uses a **state machine with validation gates** to ensure data quality at each step. Every claim in the final MRD is traceable to its data source.

### Key Architectural Decisions

1. **State Machine (Not DAG, Not Multi-Agent Swarm)**
   - Predictable, testable flow
   - Natural error recovery points
   - Easy to debug and resume

2. **Pydantic at Every Boundary**
   - Input validation (user prompts → structured plans)
   - Tool output validation (API responses → validated data)
   - Output validation (final MRD → guaranteed schema)

3. **Source Tracking & Hallucination Prevention**
   - Every claim includes `DataSource` metadata
   - Multi-source verification for high-impact claims
   - Confidence scoring (0.0-1.0) for each source

4. **Graceful Degradation**
   - Tool failures don't crash the system
   - Partial MRDs are better than no MRDs
   - Clear error messages about what failed

5. **Modular Vertical Swapping**
   - Abstract base class pattern
   - Easy to swap Gambling → SaaS → any vertical
   - Parallel development of new verticals

---

## 🚀 Quick Start

```bash
# Clone and install
git clone <your-repo>
cd autonomous-mrd-agent
pip install -e .

# Run demo
python src/examples/triumph_demo.py
```

---

## 📚 Documentation

- **[ARCHITECTURE_DEEP_DIVE.md](ARCHITECTURE_DEEP_DIVE.md)**: Detailed explanation of how the "brain" works
- **[PRODUCTION_READY.md](PRODUCTION_READY.md)**: Production patterns and deployment considerations
- **[architecture.md](architecture.md)**: System architecture overview
- **[docs/decision_log.md](docs/decision_log.md)**: Design decisions and rationale

---

## 🎨 Key Features

### 1. Structured Agentic Reasoning
Moves from "vibe coding" to validated, source-backed analysis. Every claim in the MRD includes:
- Source metadata (which tool/API provided the data)
- Timestamp (when was this data collected)
- Confidence score (how reliable is this claim)
- Raw data (for audit trails)

### 2. Type-Safe Orchestration
Uses Pydantic models for guaranteed valid outputs at every step:
- `ResearchPlan` validates user prompts are parseable
- `ResearchTask` ensures tasks have required fields
- `MRDOutput` guarantees final structure matches schema

### 3. Modular Design
Easy swap between verticals:
```python
# Swap verticals with one line
agent.current_module = SaaSModule()  # Instead of GamblingModule()
```

### 4. Human-in-the-Loop
Critical validation points for quality control:
- Research plan approval (before expensive API calls)
- Low confidence claims (when confidence < 0.6)
- Regulatory analysis (always requires human review)
- Final MRD review (quality gate before delivery)

### 5. Robust Error Handling
Three-tier error recovery:
- **Tool Level**: Retry with exponential backoff
- **Task Level**: Alternative tools or estimation with uncertainty flags
- **System Level**: Circuit breaker pattern prevents cascade failures

---

## 📊 Example: Triumph Research

**Input Prompt**:
```
"I want to build a skill-based gambling app targeting young men, 
similar to Triumph but for the European market"
```

**What the Agent Does**:
1. **Parse & Plan**: Creates research plan with 5 tasks:
   - Market analysis (why is Triumph succeeding?)
   - TikTok/influencer strategy research
   - Gap analysis (what IO games are missing?)
   - Regulatory compliance check (EU/UK)
   - Payment processor research

2. **Human Validation**: Research plan presented for approval

3. **Execute Research**: 
   - Calls Sensor Tower API for market data
   - Scrapes social media for TikTok strategy
   - Checks regulatory databases
   - (With retry logic if tools fail)

4. **Synthesize**: Transforms research data into structured MRD:
   - Executive summary
   - Competitor analysis (with sources)
   - Feature recommendations (prioritized)
   - Regulatory analysis
   - SWOT analysis

5. **Validate**: Pydantic ensures structure is correct, business rules checked

**Output**: Structured JSON MRD that can be:
- Saved to database
- Used by product teams
- Verified for compliance
- Traced back to original sources

---

## 🔍 How It Prevents Hallucinations

### Multi-Source Verification
Every high-impact claim requires 2+ independent sources:
```python
# Before adding competitor claim:
sources = [
    search_sensor_tower("Skillz"),
    search_app_store("Skillz"),
    search_web("Skillz")
]
# Require at least 2 confirmations
confirmations = sum(1 for s in sources if s.confidence > 0.7)
if confirmations < 2:
    raise InsufficientSourcesError()
```

### Source Tracking
Every claim includes provenance:
```python
claim = Claim(
    statement="Skillz has high CAC (>$50 per user)",
    data_sources=[
        DataSource(
            source_type="sensor_tower",
            source_name="Sensor Tower Q3 2024",
            confidence_score=0.85,
            timestamp="2024-12-15T10:30:00Z",
            raw_data={"cac": 52.3}  # Original data preserved
        )
    ]
)
```

### Confidence Scoring
Low confidence claims are flagged for human review:
```python
if claim.confidence_score < 0.6:
    await request_human_review(claim)
```

---

## 🛠️ Error Handling Examples

### Scenario 1: Sensor Tower API is Down
**What Happens**:
1. Tool call fails → Retry with exponential backoff (2s, 4s, 8s)
2. If still fails → Check: Is task critical?
   - **Critical** (regulatory): Stop process, return error
   - **Non-critical** (gap analysis): Mark as failed, continue
3. Continue with other tasks
4. If 70%+ tasks completed → Generate partial MRD with error context

**Result**: System doesn't crash. Partial MRD generated with clear error messages.

### Scenario 2: Hallucinated Competitor
**Prevention**:
- Every competitor claim requires 2+ independent sources
- If only one source found → Lower confidence score
- Low confidence → Flag for human review

**Detection**:
- Source tracking allows verification
- If disputed → Check raw data

### Scenario 3: Invalid Tool Response
**What Happens**:
1. Tool returns data
2. Pydantic validation checks structure
3. If invalid → Raise `ValidationError`
4. Don't proceed with invalid data
5. Retry or mark task as failed

**Result**: Invalid data never makes it into the MRD.

---

## 🏭 Production Readiness

This architecture includes production-ready patterns:

- **Circuit Breakers**: Prevent cascade failures
- **Retry Logic**: Exponential backoff for transient failures
- **State Persistence**: Can resume from last known state
- **Monitoring Hooks**: Log state transitions, tool calls, confidence scores
- **Graceful Degradation**: Partial results better than no results
- **Database-Ready**: Pydantic models serialize directly to JSON

See [PRODUCTION_READY.md](PRODUCTION_READY.md) for detailed production considerations.

---

## 🧪 Testing

```bash
# Run tests
pytest tests/

# Run demo
python src/examples/triumph_demo.py
```

---

## 📖 Design Philosophy

1. **Validation First**: Every data point must pass Pydantic validation
2. **Source Tracking**: All claims include provenance metadata
3. **Modular Swapping**: Domain logic encapsulated in pluggable modules
4. **Graceful Degradation**: System continues with partial data when possible
5. **Human-in-the-Loop**: Critical points require human judgment

---

## 🎓 Why This Architecture?

### Why State Machine Over DAG?
- **Predictable Flow**: Clear, testable transitions
- **Error Recovery**: Easy to implement retry logic at each state
- **Human Integration**: Natural points for validation between states
- **Debugging**: Simple to trace where failures occurred

### Why Not Multi-Agent Swarm?
- Over-engineering for this use case
- Single well-orchestrated agent with specialized modules provides sufficient complexity management
- Easier to debug and maintain

### Why Pydantic at Every Layer?
1. **Input Validation**: User prompts parsed into structured objects
2. **Tool Output Validation**: Every API response validated before processing
3. **MRD Structure Guarantee**: Final output always matches expected schema
4. **Automatic Documentation**: JSON schemas generated for all interfaces

---

## 📝 License

[Your License Here]

---

## 🤝 Contributing

[Your Contributing Guidelines Here]

---

**Built for production. Designed for reliability. Structured for success.**
