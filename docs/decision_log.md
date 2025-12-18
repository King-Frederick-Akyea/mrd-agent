# Design Decision Log

This document explains the "why" behind every major architectural decision. Understanding the rationale helps maintain the system and make informed changes.

---

## Architecture Choice: State Machine with Validation Gates

### Why State Machine Over DAG or Multi-Agent?

**Decision**: Use a deterministic state machine (IDLE → RESEARCHING → VALIDATING → COMPLETED)

**Rationale**:

1. **Predictable Flow**: State machines provide clear, testable transitions. You can always answer "What state is the agent in?" and know exactly what it's doing.

2. **Error Recovery**: Easy to implement retry logic at each state. If a task fails in RESEARCHING state, we can retry without affecting other states.

3. **Human Integration**: Natural points for human validation between states (e.g., approve research plan before moving to RESEARCHING).

4. **Debugging**: Simple to trace where failures occurred. Logs show: "State: RESEARCHING → Task X failed → Transition to FAILED".

5. **Resumability**: If the process crashes, we can resume from the last known state. State can be persisted to Redis/DB.

**Why Not DAG (Directed Acyclic Graph)?**

While DAGs allow parallel execution, they're harder to debug when tools fail:
- Dependencies are implicit (hard to see what depends on what)
- Error propagation is complex (which tasks are affected by a failure?)
- Our research tasks have dependencies anyway (need market size before feature prioritization)
- Sequential execution is easier to reason about and test

**Why Not Multi-Agent Swarm?**

Over-engineering for this use case:
- A single well-orchestrated agent with specialized modules provides sufficient complexity management
- Multi-agent systems introduce coordination overhead
- Harder to debug (which agent is responsible for what?)
- Our use case doesn't require true parallelism (tasks are mostly I/O bound, not CPU bound)

**Production Benefit**: In a distributed system, state can be persisted and agents can resume across server restarts.

---

## Pydantic Integration Strategy

### Why Pydantic at Every Layer?

**Decision**: Use Pydantic models to validate data at three critical boundaries:
1. Input boundary (user prompts → ResearchPlan)
2. Tool boundary (API responses → validated data)
3. Output boundary (final MRD → guaranteed schema)

**Rationale**:

1. **Type Safety**: Pydantic ensures data structure matches schema at runtime. If a field is missing or wrong type, validation fails immediately (no silent errors).

2. **Automatic Documentation**: JSON schemas generated automatically from Pydantic models. This serves as API documentation.

3. **Database-Ready**: Pydantic models serialize directly to JSON:
   ```python
   mrd_json = mrd.model_dump_json()  # Valid JSON, ready for DB
   ```

4. **Hallucination Prevention**: If LLM tries to add a field that doesn't exist in schema, validation fails. This prevents "invented" fields.

5. **Downstream Trust**: Systems consuming the MRD can trust the structure. No need for defensive programming.

**Example of Type Safety:**

```python
# This will fail at runtime if data doesn't match schema
mrd = MRDOutput(**raw_data)  # Raises ValidationError if structure wrong

# Without Pydantic, you'd have to manually check:
if "competitor_analysis" not in raw_data:
    raise ValueError("Missing field")  # Easy to forget!
```

**Production Benefit**: Database writes never fail due to schema mismatches. API responses are always valid JSON.

---

## Hallucination Mitigation

### Multi-Source Verification Strategy

**Decision**: Require 2+ independent sources for high-impact claims.

**Rationale**:

LLMs can invent competitors, metrics, or features that don't exist. To prevent this:

1. **Claim Tracking**: Every statement linked to its data source via `DataSource` objects.

2. **Cross-Validation**: High-impact claims (e.g., competitor weaknesses) require 2+ sources:
   ```python
   sources = [
       search_sensor_tower(competitor_name),
       search_app_store(competitor_name),
       search_web(competitor_name)
   ]
   confirmations = sum(1 for s in sources if s.confidence > 0.7)
   if confirmations < 2:
       raise InsufficientSourcesError()
   ```

3. **Confidence Scoring**: Each source has confidence score (0.0-1.0). Claims are weighted by source confidence.

4. **Human Review**: Low confidence claims (< 0.6) are flagged for human review.

**Production Benefit**: Legal/compliance teams can verify every claim. If a claim is disputed, you can show the original source.

---

## Error Handling Strategy

### Three-Level Error Recovery

**Decision**: Implement error handling at three levels:
1. **Tool Level**: Retry with exponential backoff
2. **Task Level**: Alternative tools or estimation with uncertainty flags
3. **System Level**: Circuit breaker pattern

**Rationale**:

**Tool Level (Retry Logic)**:
- Transient failures (network errors, timeouts) are common
- Exponential backoff (2s, 4s, 8s) prevents overwhelming failing services
- Most failures are transient and resolve on retry

**Task Level (Graceful Degradation)**:
- If Sensor Tower fails, try alternative market research tool
- If that fails, mark metric as "estimated" with low confidence
- Continue with other tasks (don't let one failure stop everything)

**System Level (Circuit Breaker)**:
- If tools are consistently failing, retrying forever wastes resources
- Circuit breaker opens after 3 consecutive failures
- Requests fail fast (no retries) when circuit is open
- Automatic recovery after 60s timeout

**Example Flow**:
```
Sensor Tower fails → Retry 3x → Still fails → 
Try alternative market research tool → 
If that fails → Mark metric as "estimated" with low confidence →
Continue with other tasks →
If 70%+ tasks completed → Generate partial MRD with error context
```

**Production Benefit**: System remains available even when external APIs are down. Partial MRDs are better than no MRDs.

---

## Modularity for Vertical Swapping

### Strategy: Abstract Base Class Pattern

**Decision**: Use abstract base class (`BaseResearchModule`) for all verticals.

**Rationale**:

1. **Clear Interface Contract**: All verticals must implement:
   - `create_research_plan(prompt)`: Parse user intent into research tasks
   - `synthesize_mrd(data)`: Transform research data into MRD structure
   - `get_required_tools()`: List tools needed for this vertical

2. **Easy Testing**: Each module can be tested independently.

3. **Parallel Development**: New verticals can be developed in parallel without affecting existing ones.

4. **Configuration-Driven**: Can swap verticals at runtime:
   ```python
   agent.current_module = SaaSModule()  # Instead of GamblingModule()
   ```

**Why This Works**:

- **Separation of Concerns**: Domain logic (gambling vs SaaS) is isolated
- **No Code Duplication**: Common orchestration logic stays in `MRDAgent`
- **Easy Extension**: Adding a new vertical is just implementing the base class

**Production Benefit**: Can A/B test different research strategies. Can deploy new verticals without touching core code.

---

## Human-in-the-Loop Design

### Critical Intervention Points

**Decision**: Four explicit validation gates where humans can intervene:
1. Research Plan Approval (before expensive API calls)
2. Low Confidence Claims (when confidence < 0.6)
3. Regulatory Analysis (always requires human review)
4. Final MRD Review (quality gate before delivery)

**Rationale**:

1. **Cost Control**: Research plans can trigger expensive API calls. Human approval prevents wasted resources.

2. **Legal Compliance**: Regulatory analysis always requires human review (AI can't provide legal advice).

3. **Quality Assurance**: Low confidence claims may be incorrect. Human review catches errors.

4. **Business Context**: Humans know business priorities that AI can't know (e.g., "Don't recommend features that conflict with our brand").

**Implementation**:

```python
if confidence_score < 0.6 or "legal" in claim.category:
    await request_human_review(claim)
```

**Production Benefit**: Prevents costly mistakes. Builds trust with stakeholders.

---

## Production Readiness Features

### Why These Patterns Matter

**Circuit Breakers**:
- Prevents cascade failures when external services are down
- Fast failure (no retries) when circuit is open
- Automatic recovery when services come back

**Rate Limiting**:
- Respect external API limits (don't get banned)
- Can be implemented at tool level or system level

**Cost Tracking**:
- Monitor LLM and tool usage costs
- Can set budgets per MRD generation
- Helps optimize which tools to use

**Audit Trail**:
- Full traceability of every claim
- Can answer "Why did we recommend this feature?" with source data
- Important for compliance and debugging

**Performance Metrics**:
- Track timing, success rates, confidence scores
- Helps identify bottlenecks
- Can optimize based on real data

**Health Checks**:
- Monitor tool availability
- Can proactively switch to alternative tools
- Prevents failures before they happen

---

## Trade-offs Made

### Speed vs Accuracy

**Decision**: Prioritize accuracy with multiple validations.

**Rationale**: Product strategy decisions have real business consequences. It's better to be slow and correct than fast and wrong.

**Trade-off**: MRD generation takes longer (multiple validation steps), but results are more reliable.

---

### Completeness vs Time

**Decision**: May return partial MRD with error flags.

**Rationale**: Partial MRDs are better than no MRDs. Downstream systems can decide how to handle partial data.

**Trade-off**: Some MRDs may be incomplete, but system remains available.

---

### Automation vs Human Review

**Decision**: Critical points require human oversight.

**Rationale**: AI can't know everything. Human judgment is needed for:
- Legal compliance
- Business priorities
- Low confidence claims

**Trade-off**: Slower (human review takes time), but more reliable.

---

### Flexibility vs Structure

**Decision**: Strict schemas enable automation but reduce flexibility.

**Rationale**: Structured data is easier to:
- Store in databases
- Use in downstream systems
- Validate automatically

**Trade-off**: Can't easily add new fields without schema changes, but guarantees data quality.

---

## Summary

This architecture prioritizes **reliability over speed** and **structure over flexibility**. Every design decision was made to ensure:

1. **No Silent Failures**: Errors are explicit and traceable
2. **No Hallucinations**: Every claim has a source
3. **No Data Loss**: Partial results are preserved
4. **No Vendor Lock-in**: Modular design allows swapping components

The result is a system that can be trusted in production, where mistakes have real business consequences.
